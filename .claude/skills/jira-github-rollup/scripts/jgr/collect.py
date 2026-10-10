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


class Collector:
    def __init__(self, jira_key, gh=None, cache=None, max_children=200):
        self.jira_key = jira_key
        self.gh = gh or Gh()
        self.cache = cache or Cache(jira_key)
        self.max_children = max_children
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
        result = self.gh.sub_issues(repo, number)
        if not result.ok:
            # A repo without the sub-issues feature 404s on this endpoint. That
            # is not an access failure for the repository itself, so it is only
            # recorded when the epic body also failed to load.
            return []
        refs = []
        for item in result.data or []:
            url = item.get("repository_url") or ""
            owner_repo = "/".join(url.split("/")[-2:]) if url else repo
            refs.append(f"{owner_repo}#{item.get('number')}")
        return refs

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
                    child_ref, {"ref": child_ref, "epics": [], "discoveredVia": via}
                )
                if ref not in record["epics"]:
                    record["epics"].append(ref)

        child_entries = []
        for child_ref, record in sorted(children.items()):
            data = self._issue(child_ref, "child issue")
            entry = {
                "ref": child_ref,
                "epics": record["epics"],
                "discoveredVia": record["discoveredVia"],
                "accessible": data is not None,
                "title": None,
                "state": None,
                "stateReason": None,
                "closedAt": None,
                "updatedAt": None,
                "url": None,
                "crossRepo": child_ref.split("#")[0] not in {e.split("#")[0] for e in record["epics"]},
                "nested": False,
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
            child_repo, _ = split_ref(child_ref)
            if _epic_label(data.get("labels")) or len(self._children_from_body(child_repo, body)) >= 2:
                entry["nested"] = True
                self.notes.append(
                    f"{child_ref} looks like a nested epic; it was recorded but not traversed."
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

        return self._manifest(epic_entries, child_entries, dependency_entries, stage="inventory")

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
        manifest["traversalNotes"] = (manifest.get("traversalNotes") or []) + self.notes
        manifest["inventoryHash"] = _inventory_hash(manifest)
        return manifest

    def _access_list(self, existing=None):
        merged = {entry["ref"]: entry for entry in (existing or [])}
        merged.update(self.access)
        return sorted(merged.values(), key=lambda entry: entry["ref"])

    def _manifest(self, epics, children, dependencies, stage):
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
            # True whenever at least one epic was read. An epic that 404s
            # leaves nothing observed, and the child count must then be
            # `unknown` rather than a zero nobody counted.
            "observed": any(epic["accessible"] for epic in epics),
            "unobservedReason": None
            if any(epic["accessible"] for epic in epics)
            else "no linked epic could be read",
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


def empty_manifest(jira_key, reason="no upstream mapping recorded on the Jira issue"):
    """What the pipeline carries when there is no epic to traverse.

    `observed: False` is the load-bearing field. It is what makes the child
    count render `unknown` rather than `0/0`, which would be a claim that a
    measurement happened.
    """
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
        "unobservedReason": reason,
        "inventoryHash": util.sha256({"empty": reason}),
        "ghCalls": 0,
    }
