"""The append-only snapshot store.

A snapshot is the record of one run: what was mapped, what was found, what each
requirement was assessed as, and when. The next run compares against it.

Two rules are enforced in code rather than left to prose, because both have
already been identified as things an agent would plausibly get wrong:

* `save` never overwrites an existing file. If a path is somehow taken, it
  suffixes rather than replacing - the baseline must survive a Jira comment
  being edited in place.
* `select_baseline` prefers the most recent *published* snapshot, falls back to
  the most recent draft and says so, and refuses a snapshot whose schema it
  does not understand instead of half-reading it.
"""

from __future__ import annotations

import os
import re

from . import util
from .cache import snapshot_dir

SCHEMA_VERSION = 2
SUPPORTED_SCHEMAS = (1, 2)

# Bump when a change to the assessment rules invalidates stored assessments.
# A snapshot written under an older rules version forces a full reassessment
# rather than silently reusing judgements made under different instructions.
RULES_VERSION = "2026-10-07"

FILENAME = re.compile(r"^(\d{8}T\d{6}Z)(?:-\d+)?-(draft|published)\.json$")


def list_snapshots(jira_key, directory=None):
    directory = directory or snapshot_dir(jira_key)
    if not os.path.isdir(directory):
        return []
    found = []
    for name in sorted(os.listdir(directory)):
        match = FILENAME.match(name)
        if match:
            found.append(
                {
                    "path": os.path.join(directory, name),
                    "stamp": match.group(1),
                    "publication": match.group(2),
                }
            )
    return sorted(found, key=lambda item: item["stamp"])


def load(path):
    """Read a snapshot. Returns (data, problem). Exactly one is non-None."""
    try:
        data = util.read_json(path)
    except (OSError, ValueError) as exc:
        return None, f"could not be read ({type(exc).__name__})"
    version = data.get("schemaVersion")
    if version not in SUPPORTED_SCHEMAS:
        return None, f"schema version {version!r} is not one this run understands"
    return data, None


def find(jira_key, generated_at, directory=None):
    """The snapshot written at `generated_at`, or None.

    `rerender` needs this: a snapshot records which baseline it was compared
    against but not the baseline's contents, and the trend table cannot be
    rebuilt from a date alone.
    """
    if not generated_at:
        return None
    for candidate in list_snapshots(jira_key, directory):
        data, _ = load(candidate["path"])
        if data is not None and data.get("generatedAt") == generated_at:
            return data
    return None


def select_baseline(jira_key, directory=None):
    """Pick the snapshot this run compares against.

    Returns {"snapshot", "path", "publication", "problem"}. All None/False on a
    first run - which is a baseline-establishing run, not an error.
    """
    candidates = list_snapshots(jira_key, directory)
    if not candidates:
        return {"snapshot": None, "path": None, "publication": None, "problem": None}

    published = [c for c in candidates if c["publication"] == "published"]
    ordered = ([published[-1]] if published else []) + list(reversed(candidates))
    seen = set()
    first_problem = None
    for candidate in ordered:
        if candidate["path"] in seen:
            continue
        seen.add(candidate["path"])
        data, problem = load(candidate["path"])
        if data is None:
            if first_problem is None:
                first_problem = {
                    "path": candidate["path"],
                    "generatedAt": _stamp_to_iso(candidate["stamp"]),
                    "detail": problem,
                }
            continue
        return {
            "snapshot": data,
            "path": candidate["path"],
            "publication": data.get("publication") or candidate["publication"],
            "problem": first_problem,
        }
    return {"snapshot": None, "path": None, "publication": None, "problem": first_problem}


def _stamp_to_iso(stamp):
    return f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}T{stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]}Z"


def save(snapshot, directory=None):
    """Write a new snapshot file. Never overwrites, never deletes."""
    jira_key = snapshot["jiraKey"]
    directory = directory or snapshot_dir(jira_key)
    os.makedirs(directory, exist_ok=True)
    stamp = util.stamp(util.parse_iso(snapshot["generatedAt"]) or util.utcnow())
    publication = snapshot.get("publication") or "draft"
    path = os.path.join(directory, f"{stamp}-{publication}.json")
    counter = 2
    while os.path.exists(path):
        path = os.path.join(directory, f"{stamp}-{counter}-{publication}.json")
        counter += 1
    util.write_json(path, snapshot)
    return path


def promote(path, comment_id, published_at=None, published_text=None):
    """Mark an already-written snapshot as published, after the post succeeded.

    A comment id is the only evidence this process has that a Jira update
    actually happened, so it is required and may not be blank. Promoting on
    intent rather than on a returned id is how a failed post ends up advancing
    the baseline, which silently destroys the next run's comparison.

    `published_text` records *what* was published - the approved summary, not
    the full assessment - as a hash, so a later reader can tell whether the
    comment on the issue is still the text this snapshot was promoted for.
    """
    if comment_id is None or not str(comment_id).strip():
        raise ValueError(
            "a Jira comment id is required to promote a snapshot. If the post failed or was "
            "not made, leave the snapshot a draft: the published baseline must not move."
        )
    data, problem = load(path)
    if data is None:
        raise ValueError(f"{path}: {problem}")
    data["publication"] = "published"
    data["publishedAt"] = published_at or util.iso(util.utcnow())
    data["jiraCommentId"] = str(comment_id)
    if published_text is not None:
        data["published"] = {
            "kind": "summary",
            "words": len(published_text.split()),
            "hash": util.sha256(published_text),
        }
    util.write_json(path, data)
    target = re.sub(r"-draft\.json$", "-published.json", path)
    if target != path and not os.path.exists(target):
        os.rename(path, target)
        return target
    return path


def build(
    jira,
    mappings,
    manifest,
    requirements,
    baseline_info,
    generated_at=None,
    outcomes=None,
    narrative=None,
    summaryNarrative=None,
    trend=None,
    prose=None,
):
    """Assemble the snapshot document for this run.

    Schema v2 is v1 plus additive fields. Every v1 key is still written with
    its v1 meaning, so an older reader sees exactly what it saw before; the new
    keys are what make an incremental run possible.
    """
    generated_at = generated_at or util.iso(util.utcnow())
    children = [
        {
            "ref": child["ref"],
            "title": child.get("title"),
            "state": child.get("state"),
            "stateReason": child.get("stateReason"),
            "closedAt": child.get("closedAt"),
            "epics": child.get("epics") or [],
            "contentHash": child.get("contentHash"),
            "accessible": child.get("accessible", True),
            "prs": [
                {
                    "ref": pr["ref"],
                    "state": pr.get("state"),
                    "mergedAt": pr.get("mergedAt"),
                    "baseRef": pr.get("baseRef"),
                }
                for pr in child.get("prs") or []
            ],
        }
        for child in manifest.get("children") or []
    ]
    baseline = None
    if baseline_info and baseline_info.get("snapshot"):
        baseline = {
            "generatedAt": baseline_info["snapshot"].get("generatedAt"),
            "publication": baseline_info.get("publication"),
        }

    return {
        "schemaVersion": SCHEMA_VERSION,
        "rulesVersion": RULES_VERSION,
        "jiraKey": jira["key"],
        "generatedAt": generated_at,
        "publication": "draft",
        "publishedAt": None,
        "jiraCommentId": None,
        "baseline": baseline,
        "jiraStatus": jira.get("status"),
        "rollupStatus": jira.get("rollupStatus"),
        # The two pieces of Jira context both outputs are rendered with: the
        # issue title in the heading, and the site that turns `AC1
        # (RHOAIENG-1234)` into a link. Neither is derivable from `jiraKey`,
        # and without them a re-render produces a visibly different document
        # from the one that was reviewed.
        "jiraSummary": jira.get("summary"),
        "jiraSite": jira.get("site"),
        # The release target, for the same reason. The HTML report states it
        # when recorded and says so when not; without it stored, re-rendering
        # would turn a recorded fix version into "not recorded on the Jira
        # issue", which is a different and false statement.
        "jiraFixVersions": jira.get("fixVersions") or [],
        "mappings": [
            {
                "epic": mapping["ref"],
                "url": mapping.get("url"),
                "title": mapping.get("title"),
                "linkSource": mapping.get("linkSource"),
            }
            for mapping in mappings
        ],
        "scope": {
            "sourceIssues": jira.get("sourceIssues") or [jira["key"]],
            "children": children,
            "otherInspected": [d["ref"] for d in manifest.get("dependencies") or []],
            # The same dependencies with the state they were in. `otherInspected`
            # records only that they were looked at, which is enough to list them
            # and not enough to notice one closing between runs.
            "dependencies": [
                {
                    "ref": dependency["ref"],
                    "state": dependency.get("state"),
                    "stateReason": dependency.get("stateReason"),
                    "accessible": dependency.get("accessible"),
                }
                for dependency in manifest.get("dependencies") or []
            ],
            "traversalComplete": bool(manifest.get("traversalComplete")),
            "traversalNotes": manifest.get("traversalNotes") or None,
            # The branches the walk stopped at. Without this a later reader
            # cannot tell a rollup that covered everything from one that
            # covered most of it, and the two have identical outcome tables.
            "untraversed": manifest.get("untraversed") or None,
            "observed": manifest.get("observed", bool(manifest.get("epics"))),
            "unobservedKind": manifest.get("unobservedKind"),
            "unobservedReason": manifest.get("unobservedReason"),
        },
        "access": manifest.get("access") or [],
        # The classification both outputs were rendered from. Stored so a later
        # reader can see what was reported without re-deriving it, and so a
        # change in the mapping rules is visible against `rulesVersion`.
        "outcomes": outcomes,
        # The prose that went out, with the assessment rows each claim rests
        # on. Stored for two reasons: re-rendering has to reproduce the summary
        # that was reviewed rather than regenerate a new one, and a later
        # reader needs to be able to get from a sentence back to the rows it
        # was drawn from. It records what was claimed, not that the claim held.
        "narrative": narrative or None,
        "summaryNarrative": summaryNarrative or None,
        # The rendered trend sentence. It is computed against a baseline this
        # document does not contain, so it cannot be recomputed later.
        "summaryTrend": trend or None,
        # The remaining model prose in the full assessment: caveats, risks and
        # declared dependencies. Dropping these on a re-render would quietly
        # remove the limitation reporting, which is the part of the document
        # that must not go missing.
        "prose": prose or None,
        "requirements": requirements,
        "inventory": {
            "collectedAt": manifest.get("collectedAt"),
            "inventoryHash": manifest.get("inventoryHash"),
            "stage": manifest.get("stage"),
            "epics": [
                {"ref": epic["ref"], "childRefs": epic.get("childRefs") or [], "accessible": epic.get("accessible")}
                for epic in manifest.get("epics") or []
            ],
        },
    }
