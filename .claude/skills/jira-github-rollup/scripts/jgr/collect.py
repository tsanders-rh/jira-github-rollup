"""Bounded, staged traversal of the linked GitHub epics.

Stage 1 (`inventory`) walks the epics, their children, and those children's
pull requests, writing every raw response to the cache and returning a compact
manifest: identifiers, originating epics, states, timestamps, content hashes,
access failures, and cache paths. No bodies, no timelines, no logs.

Stage 2 (`evidence`) fetches changed files and CI checks for named pull
requests only - the ones the LLM has decided are candidates for a requirement.

The reachable set is fixed: the linked epic(s), their children, those
children's PRs, and dependencies those artifacts reference directly. There is
no code path here that searches GitHub by title or keyword.
"""

from __future__ import annotations

import re

from . import scope
from . import util
from .cache import Cache
from .ghclient import Gh

ISSUE_FIELDS = [
    "number",
    "title",
    "state",
    "stateReason",
    "body",
    "labels",
    "assignees",
    "url",
    "closedAt",
    "updatedAt",
]
PR_FIELDS = [
    "number",
    "title",
    "state",
    "isDraft",
    "mergedAt",
    "author",
    "url",
    "baseRefName",
    "reviewDecision",
    "updatedAt",
]
PR_EVIDENCE_FIELDS = ["files", "changedFiles", "closingIssuesReferences"]

TASK_REF = re.compile(r"(?:^|\s)(?:-\s*\[[ xX]\]\s*)?([\w.-]+/[\w.-]+)#(\d+)")
TASK_URL = re.compile(r"https?://github\.com/([\w.-]+)/([\w.-]+)/issues/(\d+)", re.I)
LOCAL_TASK = re.compile(r"^\s*-\s*\[[ xX]\]\s*#(\d+)\s*$", re.M)
DEPENDENCY = re.compile(
    r"(?:depends on|blocked by|requires)\s+(?:https?://github\.com/([\w.-]+)/([\w.-]+)/issues/(\d+)|([\w.-]+/[\w.-]+)#(\d+))",
    re.I,
)
TEST_PATH = re.compile(r"(^|/)(tests?|spec|e2e|integration|__tests__)(/|$)|_test\.|test_|\.spec\.", re.I)
DOC_PATH = re.compile(r"(^|/)(docs?|site|man)(/|$)|\.md$|\.rst$|\.adoc$", re.I)


def split_ref(ref):
    repo, _, number = ref.partition("#")
    return repo, number


def _epic_label(labels):
    names = {(label.get("name") or "").lower() for label in labels or []}
    return bool(names & {"epic", "feature", "initiative"})


# Relations strong enough to traverse a nested epic through.
#
# `sub-issue` is GitHub's own parent-child link and `task-list` is the epic
# author writing the child down; both are someone declaring membership. A
# `timeline-cross-reference` is only that something, somewhere, mentioned the
# epic - a duplicate, a "see also", a bot. Descending through a mention would
# pull unrelated trees into the scope and report their criteria as this issue's
# work, so a nested epic found that way is recorded and left alone.
DECLARED_RELATIONS = ("sub-issue", "task-list")


class Collector:
    def __init__(self, jira_key, gh=None, cache=None, max_children=200, max_depth=1):
        self.jira_key = jira_key
        self.gh = gh or Gh()
        self.cache = cache or Cache(jira_key)
        self.max_children = max_children
        # One level, matching the documented boundary. Depth is still tracked
        # rather than assumed, so raising it is a parameter change and not a
        # rewrite - and so the stop is reported with the depth that caused it.
        self.max_depth = max_depth
        self.access = {}
        self.notes = []
        self.complete = True

    # --- access bookkeeping ---------------------------------------------

    def _fail(self, ref, result, what):
        status = result.status or "error"
        repo = ref.split("#")[0]
        key = repo if status in ("unreadable", "forbidden") else ref
        self.access[key] = {
            "ref": key,
            "status": status,
            "detail": f"{what}: {result.error}",
            "observedAt": util.iso(util.utcnow()),
        }
        self.complete = False

    # --- discovery ------------------------------------------------------

    def _children_from_body(self, repo, body):
        found = []
        for org_repo, number in TASK_REF.findall(body or ""):
            found.append(f"{org_repo}#{number}")
        for org, repo_name, number in TASK_URL.findall(body or ""):
            found.append(f"{org}/{repo_name}#{number}")
        for number in LOCAL_TASK.findall(body or ""):
            found.append(f"{repo}#{number}")
        return found

    def _dependencies_from_body(self, body):
        found = []
        for org, repo_name, number, short, short_number in DEPENDENCY.findall(body or ""):
            if org:
                found.append(f"{org}/{repo_name}#{number}")
            elif short:
                found.append(f"{short}#{short_number}")
        return found

    def _sub_issues(self, repo, number):
        return self._sub_issue_refs(repo, number)[0]

    def _sub_issue_refs(self, repo, number):
        """`(refs, answered)`. `answered` is False when GitHub could not say.

        A repo without the sub-issues feature 404s on this endpoint. That is
        not an access failure for the repository itself, so it is only recorded
        when the epic body also failed to load - but it is also not an answer
        of zero, and callers that classify on the count must not read it as
        one.
        """
        result = self.gh.sub_issues(repo, number)
        if not result.ok:
            # A 403 is not "this repo has no sub-issues feature". It is a
            # branch of the tree that exists and was refused, and swallowing
            # it turned real children into an absence of children - every
            # criterion they own then reads as untracked work.
            if result.status == "forbidden":
                self._fail(f"{repo}#{number}", result, "sub-issue list")
            return [], False
        refs = []
        for item in result.data or []:
            url = item.get("repository_url") or ""
            owner_repo = "/".join(url.split("/")[-2:]) if url else repo
            refs.append(f"{owner_repo}#{item.get('number')}")
        return refs, True

    def _timeline_refs(self, repo, number):
        """Issues and PRs cross-referenced from an issue's timeline."""
        result = self.gh.timeline(repo, number)
        if not result.ok:
            return [], []
        issues, prs = [], []
        for event in result.data or []:
            if event.get("event") not in ("cross-referenced", "connected"):
                continue
            source = (event.get("source") or {}).get("issue") or {}
            url = source.get("html_url") or ""
            match = re.search(r"github\.com/([\w.-]+)/([\w.-]+)/(issues|pull)/(\d+)", url)
            if not match:
                continue
            org, repo_name, kind, num = match.groups()
            ref = f"{org}/{repo_name}#{num}"
            (prs if kind == "pull" or source.get("pull_request") else issues).append(ref)
        return issues, prs

    # --- fetch ----------------------------------------------------------

    def _issue(self, ref, what):
        repo, number = split_ref(ref)
        cached = self.cache.get("issue", ref)
        if cached is not None:
            return cached
        result = self.gh.issue_view(repo, number, ISSUE_FIELDS)
        if not result.ok:
            self._fail(ref, result, what)
            return None
        self.cache.put("issue", ref, result.data)
        return result.data

    def _pr(self, ref):
        repo, number = split_ref(ref)
        cached = self.cache.get("pr", ref)
        if cached is not None:
            return cached
        result = self.gh.pr_view(repo, number, PR_FIELDS)
        if not result.ok:
            self._fail(ref, result, "pull request")
            return None
        self.cache.put("pr", ref, result.data)
        return result.data

    def _prs_for_child(self, ref):
        repo, number = split_ref(ref)
        _, prs = self._timeline_refs(repo, number)
        if not prs:
            result = self.gh.search_prs(f"{repo}#{number}")
            if result.ok:
                for item in result.data or []:
                    repo_name = (item.get("repository") or {}).get("nameWithOwner")
                    if repo_name:
                        prs.append(f"{repo_name}#{item.get('number')}")
        seen, ordered = set(), []
        for pr_ref in prs:
            if pr_ref not in seen:
                seen.add(pr_ref)
                ordered.append(pr_ref)
        return ordered

    # --- classification -------------------------------------------------

    def _nested_via(self, child_ref, repo, number, data, epic_refs):
        """How this child was judged a nested epic, or None if it is a leaf.

        Counting issue references in the body was the original test and it is
        wrong in the common direction: a leaf issue that names its own parent
        and a sibling scores two and gets reported as untraversed work. Every
        such false positive subtracts from what the report claims to have
        covered, so the error shows up as an overstated gap.

        GitHub's own sub-issue list is the answer where there is one. The body
        is the fallback for repos that 404 the endpoint, and there it has to
        drop references that point up - the issue itself, and the epics being
        traversed - before counting.
        """
        if _epic_label(data.get("labels")):
            return "label"
        sub_refs, answered = self._sub_issue_refs(repo, number)
        if answered:
            return "sub-issues" if len(sub_refs) >= 2 else None
        upward = {child_ref} | set(epic_refs)
        body_refs = {
            ref for ref in self._children_from_body(repo, data.get("body")) if ref not in upward
        }
        return "body-references" if len(body_refs) >= 2 else None

    def _declared_children(self, parent_ref, data):
        """A nested epic's own children, by declared relation only.

        No timeline pass here, unlike the top-level epics. At depth zero a
        cross-reference is a cheap hint worth following up; at depth one it is
        a mention of a mention, and following it would attach whatever happens
        to link to a nested epic to this Jira issue's criteria.
        """
        repo, _, number = parent_ref.partition("#")
        discovered = {}
        for ref in self._sub_issues(repo, number):
            discovered.setdefault(ref, "sub-issue")
        for ref in self._children_from_body(repo, data.get("body")):
            discovered.setdefault(ref, "task-list")
        discovered.pop(parent_ref, None)
        for dep_ref in self._dependencies_from_body(data.get("body")):
            discovered.pop(dep_ref, None)
        return discovered

    def _descend(self, entry, record, data, children, queue, visited, untraversed, epic_refs):
        """Traverse a nested epic one level, or record why it was left alone."""
        child_ref = entry["ref"]
        via = record["discoveredVia"]
        if via not in DECLARED_RELATIONS or record["depth"] >= self.max_depth:
            entry["nestedTraversed"] = False
            reason = (
                f"reached only by {via}, which establishes a mention rather than membership"
                if via not in DECLARED_RELATIONS
                else f"already {util.pluralize(record['depth'], 'level')} below the mapped epic"
            )
            untraversed.append(
                {
                    "ref": child_ref,
                    "title": entry.get("title"),
                    "discoveredVia": via,
                    "nestedVia": entry["nestedVia"],
                    "depth": record["depth"],
                    "reason": reason,
                }
            )
            self.notes.append(
                f"{child_ref} looks like a nested epic ({entry['nestedVia']}) and was recorded "
                f"but not traversed: {reason}. Criteria owned by work beneath it are not in "
                "this rollup."
            )
            return

        added = 0
        for ref, via_child in sorted(self._declared_children(child_ref, data).items()):
            if ref in visited:
                continue
            if len(children) >= self.max_children and ref not in children:
                self.complete = False
                self.notes.append(
                    f"Child traversal stopped at {self.max_children} issues while descending "
                    f"into {child_ref}."
                )
                break
            existing = children.setdefault(
                ref,
                {
                    "ref": ref,
                    "epics": [],
                    "discoveredVia": via_child,
                    "depth": record["depth"] + 1,
                },
            )
            # Attributed to the nested epic that owns it, not to the top-level
            # epic, so a reader can see which branch a criterion came from.
            if child_ref not in existing["epics"]:
                existing["epics"].append(child_ref)
            if ref not in queue:
                queue.append(ref)
            added += 1

        entry["nestedTraversed"] = True
        self.notes.append(
            f"{child_ref} is a nested epic ({entry['nestedVia']}) reached by a declared "
            f"{via} relation; it was traversed one level, adding "
            f"{util.pluralize(added, 'child', 'children')}."
        )

    # --- stages ---------------------------------------------------------

    def inventory(self, epics):
        """Walk the epics and build the manifest."""
        epic_entries = []
        children = {}
        dependencies = {}

        for epic in epics:
            ref = epic["ref"]
            data = self._issue(ref, "epic")
            entry = {
                "ref": ref,
                "url": epic.get("url"),
                "linkSource": epic.get("linkSource"),
                "title": None,
                "state": None,
                "accessible": data is not None,
                "childRefs": [],
            }
            if data is None:
                epic_entries.append(entry)
                continue

            repo, number = split_ref(ref)
            entry["title"] = data.get("title")
            entry["state"] = data.get("state")
            entry["bodyPath"] = self.cache.rel_for("issue", ref)
            entry["bodyHash"] = util.sha256(data.get("body") or "")

            discovered = {}
            for child_ref in self._sub_issues(repo, number):
                discovered.setdefault(child_ref, "sub-issue")
            for child_ref in self._children_from_body(repo, data.get("body")):
                discovered.setdefault(child_ref, "task-list")
            timeline_issues, _ = self._timeline_refs(repo, number)
            for child_ref in timeline_issues:
                discovered.setdefault(child_ref, "timeline-cross-reference")
            discovered.pop(ref, None)

            for dep_ref in self._dependencies_from_body(data.get("body")):
                dependencies.setdefault(dep_ref, {"ref": dep_ref, "referencedBy": []})
                dependencies[dep_ref]["referencedBy"].append(ref)
                discovered.pop(dep_ref, None)

            entry["childRefs"] = sorted(discovered)
            epic_entries.append(entry)

            for child_ref, via in sorted(discovered.items()):
                if len(children) >= self.max_children and child_ref not in children:
                    self.complete = False
                    self.notes.append(
                        f"Child traversal stopped at {self.max_children} issues; "
                        f"{ref} has more children than were inspected."
                    )
                    break
                record = children.setdefault(
                    child_ref, {"ref": child_ref, "epics": [], "discoveredVia": via, "depth": 0}
                )
                if ref not in record["epics"]:
                    record["epics"].append(ref)

        epic_refs = {entry["ref"] for entry in epic_entries}

        # A worklist rather than a loop over a fixed dict: traversing a nested
        # epic adds children while the walk is running. `visited` holds every
        # ref already handled, including the top epics, so a child that points
        # back at its parent - or at a sibling that points back at it - is
        # recorded once and never re-entered.
        child_entries = []
        untraversed = []
        visited = set(epic_refs)
        queue = sorted(children)
        while queue:
            child_ref = queue.pop(0)
            if child_ref in visited:
                continue
            visited.add(child_ref)
            record = children[child_ref]
            data = self._issue(child_ref, "child issue")
            entry = {
                "ref": child_ref,
                "epics": record["epics"],
                "discoveredVia": record["discoveredVia"],
                "depth": record["depth"],
                "accessible": data is not None,
                "title": None,
                "state": None,
                "stateReason": None,
                "closedAt": None,
                "updatedAt": None,
                "url": None,
                "crossRepo": child_ref.split("#")[0] not in {e.split("#")[0] for e in record["epics"]},
                "nested": False,
                "nestedVia": None,
                "nestedTraversed": None,
                "bodyPath": None,
                "bodyHash": None,
                "prs": [],
            }
            if data is None:
                entry["contentHash"] = util.sha256({"ref": child_ref, "accessible": False})
                child_entries.append(entry)
                continue

            body = data.get("body") or ""
            entry.update(
                {
                    "title": data.get("title"),
                    "state": (data.get("state") or "").upper(),
                    # `gh` reports no reason as null; the empty string is its own
                    # bucket and must not be normalized to COMPLETED.
                    "stateReason": (data.get("stateReason") or "").upper(),
                    "closedAt": data.get("closedAt"),
                    "updatedAt": data.get("updatedAt"),
                    "url": data.get("url"),
                    "bodyPath": self.cache.rel_for("issue", child_ref),
                    "bodyHash": util.sha256(body),
                }
            )
            child_repo, child_number = split_ref(child_ref)
            nested_via = self._nested_via(child_ref, child_repo, child_number, data, epic_refs)
            if nested_via:
                entry["nested"] = True
                entry["nestedVia"] = nested_via
                self._descend(
                    entry, record, data, children, queue, visited, untraversed, epic_refs
                )
            for dep_ref in self._dependencies_from_body(body):
                dependencies.setdefault(dep_ref, {"ref": dep_ref, "referencedBy": []})
                dependencies[dep_ref]["referencedBy"].append(child_ref)

            for pr_ref in self._prs_for_child(child_ref):
                pr_data = self._pr(pr_ref)
                if pr_data is None:
                    entry["prs"].append({"ref": pr_ref, "accessible": False, "state": "unknown"})
                    continue
                merged_at = pr_data.get("mergedAt")
                state = (pr_data.get("state") or "").lower()
                if merged_at:
                    state = "merged"
                elif pr_data.get("isDraft"):
                    state = "draft"
                entry["prs"].append(
                    {
                        "ref": pr_ref,
                        "accessible": True,
                        "state": state,
                        "mergedAt": merged_at,
                        "baseRef": pr_data.get("baseRefName"),
                        "isDraft": bool(pr_data.get("isDraft")),
                        "reviewDecision": pr_data.get("reviewDecision"),
                        "updatedAt": pr_data.get("updatedAt"),
                        "url": pr_data.get("url"),
                        "title": pr_data.get("title"),
                        "evidence": None,
                    }
                )
            entry["contentHash"] = self._child_hash(entry)
            child_entries.append(entry)

        dependency_entries = []
        for dep_ref, record in sorted(dependencies.items()):
            data = self._issue(dep_ref, "declared dependency")
            dependency_entries.append(
                {
                    "ref": dep_ref,
                    "referencedBy": record["referencedBy"],
                    "accessible": data is not None,
                    "title": (data or {}).get("title"),
                    "state": ((data or {}).get("state") or "").upper() or None,
                    "stateReason": ((data or {}).get("stateReason") or "").upper() or None,
                }
            )

        child_entries.sort(key=lambda entry: entry["ref"])
        return self._manifest(
            epic_entries,
            child_entries,
            dependency_entries,
            stage="inventory",
            untraversed=untraversed,
        )

    def _child_hash(self, entry):
        """Everything about a child that can change an assessment.

        Deliberately not `updatedAt`: a PR merging, a check flipping, or a
        review landing changes the evidence without touching the issue.
        """
        return util.sha256(
            {
                "state": entry["state"],
                "stateReason": entry["stateReason"],
                "closedAt": entry["closedAt"],
                "body": entry["bodyHash"],
                "accessible": entry["accessible"],
                "prs": sorted(
                    [
                        {
                            "ref": pr["ref"],
                            "state": pr.get("state"),
                            "mergedAt": pr.get("mergedAt"),
                            "baseRef": pr.get("baseRef"),
                            "reviewDecision": pr.get("reviewDecision"),
                            "evidence": (pr.get("evidence") or {}).get("hash"),
                        }
                        for pr in entry["prs"]
                    ],
                    key=lambda item: item["ref"],
                ),
            }
        )

    def evidence(self, manifest, pr_refs):
        """Stage 2: changed files and CI checks for named pull requests only."""
        wanted = set(pr_refs)
        for child in manifest["children"]:
            for pr in child["prs"]:
                if pr["ref"] not in wanted or not pr.get("accessible", True):
                    continue
                repo, number = split_ref(pr["ref"])
                digest = {"files": None, "checks": None, "limitations": []}

                files_result = self.gh.pr_view(repo, number, PR_EVIDENCE_FIELDS)
                if files_result.ok and files_result.data:
                    self.cache.put("pr-files", pr["ref"], files_result.data)
                    files = [f.get("path") for f in (files_result.data.get("files") or []) if f.get("path")]
                    tests = sorted(p for p in files if TEST_PATH.search(p))
                    docs = sorted(p for p in files if DOC_PATH.search(p))
                    other = sorted(
                        p for p in files if not TEST_PATH.search(p) and not DOC_PATH.search(p)
                    )
                    # Test paths are the ones an assessment reasons about by
                    # name, so they are listed furthest. The rest is counted;
                    # `excerpt --kind pr-files` has the full list when it
                    # matters, and a 300-file PR must not land in the manifest.
                    digest["files"] = {
                        "changedFiles": files_result.data.get("changedFiles") or len(files),
                        "tests": tests[:12],
                        "testCount": len(tests),
                        "docs": docs[:6],
                        "docCount": len(docs),
                        "other": other[:6],
                        "otherCount": len(other),
                        "path": self.cache.rel_for("pr-files", pr["ref"]),
                    }
                    digest["closes"] = [
                        f"{(c.get('repository') or {}).get('nameWithOwner', repo)}#{c.get('number')}"
                        for c in (files_result.data.get("closingIssuesReferences") or [])
                    ]
                else:
                    digest["limitations"].append(f"changed files unavailable: {files_result.error}")

                checks_result = self.gh.pr_checks(repo, number)
                if checks_result.ok and checks_result.data is not None:
                    self.cache.put("pr-checks", pr["ref"], checks_result.data)
                    buckets = {}
                    failing, pending = [], []
                    for check in checks_result.data or []:
                        bucket = (check.get("bucket") or check.get("state") or "unknown").lower()
                        buckets[bucket] = buckets.get(bucket, 0) + 1
                        if bucket in ("fail", "failure", "cancel"):
                            failing.append(check.get("name"))
                        elif bucket in ("pending", "skipping"):
                            pending.append(check.get("name"))
                    # Bucket counts plus the names that are findings. A green
                    # job list is not evidence for any criterion, so printing
                    # forty passing names would cost context and buy nothing.
                    digest["checks"] = {
                        "buckets": buckets,
                        "total": len(checks_result.data or []),
                        "failing": failing[:20],
                        "pending": pending[:20],
                        "path": self.cache.rel_for("pr-checks", pr["ref"]),
                    }
                else:
                    digest["limitations"].append(
                        f"checks unavailable: {checks_result.error or 'no checks reported'}"
                    )
                    self.complete = False

                digest["hash"] = util.sha256(
                    {"files": digest.get("files"), "checks": digest.get("checks")}
                )
                pr["evidence"] = digest
            child["contentHash"] = self._child_hash(child)

        manifest["stage"] = "evidence"
        manifest["collectedAt"] = util.iso(util.utcnow())
        manifest["access"] = self._access_list(manifest.get("access"))
        manifest["traversalComplete"] = manifest["traversalComplete"] and self.complete
        # The evidence stage may run on the same collector that did the
        # inventory, whose notes are already in the manifest. Appending them
        # again doubles every "nested epic" line, and the Jira summary counts
        # those lines to say how much was not traversed.
        existing = manifest.get("traversalNotes") or []
        manifest["traversalNotes"] = existing + [n for n in self.notes if n not in existing]
        manifest["inventoryHash"] = _inventory_hash(manifest)
        return manifest

    def _access_list(self, existing=None):
        merged = {entry["ref"]: entry for entry in (existing or [])}
        merged.update(self.access)
        return sorted(merged.values(), key=lambda entry: entry["ref"])

    def _unobserved_kind(self, epics):
        """Why no epic was read: no link, refused, gone, or simply failed.

        These have different owners. Collapsing them into "mapping missing"
        tells someone to add a link that is already there, and makes a 403
        indistinguishable from work nobody has tracked.
        """
        if not epics:
            return scope.NO_MAPPING
        statuses = set()
        for epic in epics:
            ref = epic["ref"]
            # `_fail` files repo-level failures under the repo, not the ref.
            entry = self.access.get(ref.split("#")[0]) or self.access.get(ref) or {}
            statuses.add(entry.get("status") or "error")
        if statuses == {"forbidden"}:
            return scope.ACCESS_DENIED
        if statuses == {"unreadable"}:
            return scope.NOT_FOUND
        return scope.UNREADABLE

    def _manifest(self, epics, children, dependencies, stage, untraversed=None):
        observed = any(epic["accessible"] for epic in epics)
        kind = None if observed else self._unobserved_kind(epics)
        manifest = {
            "jiraKey": self.jira_key,
            "collectedAt": util.iso(util.utcnow()),
            "stage": stage,
            "cacheDir": self.cache.root,
            "epics": epics,
            "children": children,
            "dependencies": dependencies,
            "access": self._access_list(),
            "traversalComplete": self.complete,
            "traversalNotes": self.notes,
            # Nested epics the walk stopped at, with the relation that
            # found them. Structured rather than left in the notes prose
            # because both renderings have to say it in their own words,
            # and a gap in the scope is not something to read out of a
            # free-text line.
            "untraversed": untraversed or [],
            # True whenever at least one epic was read. An epic that 404s
            # leaves nothing observed, and the child count must then be
            # `unknown` rather than a zero nobody counted.
            "observed": observed,
            "unobservedKind": kind,
            "unobservedReason": None if observed else scope.reason(kind),
            "ghCalls": len(self.gh.calls),
        }
        manifest["inventoryHash"] = _inventory_hash(manifest)
        return manifest


def _inventory_hash(manifest):
    return util.sha256(
        {
            "epics": sorted((e["ref"], tuple(e.get("childRefs") or [])) for e in manifest["epics"]),
            "children": sorted((c["ref"], c.get("contentHash")) for c in manifest["children"]),
            "access": sorted((a["ref"], a["status"]) for a in manifest["access"]),
        }
    )


def empty_manifest(jira_key, reason=None, kind=scope.NO_MAPPING):
    """What the pipeline carries when there is no epic to traverse.

    `observed: False` is the load-bearing field. It is what makes the child
    count render `unknown` rather than `0/0`, which would be a claim that a
    measurement happened.
    """
    reason = reason or scope.reason(kind)
    return {
        "jiraKey": jira_key,
        "collectedAt": util.iso(util.utcnow()),
        "stage": "none",
        "cacheDir": None,
        "epics": [],
        "children": [],
        "dependencies": [],
        "access": [],
        "traversalComplete": False,
        "traversalNotes": [reason],
        "observed": False,
        "unobservedKind": kind,
        "unobservedReason": reason,
        "inventoryHash": util.sha256({"empty": reason}),
        "ghCalls": 0,
    }
