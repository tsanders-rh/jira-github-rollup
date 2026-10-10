"""Compare this run against the baseline snapshot and decide what to reassess.

Two jobs:

1. Match requirements across runs on content, never on ID, and classify every
   difference by kind so the trend section can keep causes apart.
2. Work out which requirements an LLM actually has to look at again. The rest
   are reused with the evidence provenance and assessment timestamp they were
   given, and still appear in full in the report.

The bias throughout is toward reassessment. Where the link between a changed
artifact and a requirement is uncertain, the requirement goes in the reassess
set; a wasted assessment costs tokens, a wrongly reused one costs the report
its credibility.
"""

from __future__ import annotations

from . import scope as scope_mod
from . import util

NEAR_MATCH_THRESHOLD = 0.62


def _key(requirement):
    return (
        requirement.get("sourceKey"),
        requirement.get("type"),
        util.normalize_text(requirement.get("text")),
    )


def match_requirements(previous, current):
    """Three-pass match: exact, near, leftovers."""
    matches, added, removed, ambiguous = [], [], [], []

    prev_left = list(previous)
    cur_left = list(current)

    # Pass 1 - exact on (sourceKey, type, normalized text).
    index = {}
    for item in prev_left:
        index.setdefault(_key(item), []).append(item)
    still_current = []
    for item in cur_left:
        bucket = index.get(_key(item))
        if bucket:
            previous_item = bucket.pop(0)
            matches.append({"previous": previous_item, "current": item, "status": "matched"})
        else:
            still_current.append(item)
    prev_left = [item for bucket in index.values() for item in bucket]
    cur_left = still_current

    # Pass 2 - near match inside one (sourceKey, type) group, unique both ways.
    groups = {}
    for item in prev_left:
        groups.setdefault((item.get("sourceKey"), item.get("type")), {"prev": [], "cur": []})["prev"].append(item)
    for item in cur_left:
        groups.setdefault((item.get("sourceKey"), item.get("type")), {"prev": [], "cur": []})["cur"].append(item)

    paired_prev, paired_cur = set(), set()
    for group in groups.values():
        # Pair only where exactly one candidate remains on each side. Two
        # plausible pairings are worse than one honest non-match: a wrong pair
        # reports an edit that never happened and reuses the wrong assessment.
        forward, backward = {}, {}
        for p_index, previous_item in enumerate(group["prev"]):
            for c_index, current_item in enumerate(group["cur"]):
                ratio = util.similarity(previous_item.get("text", ""), current_item.get("text", ""))
                if ratio >= NEAR_MATCH_THRESHOLD:
                    forward.setdefault(p_index, []).append((c_index, ratio))
                    backward.setdefault(c_index, []).append((p_index, ratio))

        for p_index, candidates in forward.items():
            previous_item = group["prev"][p_index]
            if len(candidates) != 1:
                ambiguous.append({"previous": previous_item, "current": None})
                paired_prev.add(id(previous_item))
                continue
            c_index, ratio = candidates[0]
            current_item = group["cur"][c_index]
            if len(backward.get(c_index, [])) != 1:
                continue  # handled from the current side below
            matches.append(
                {
                    "previous": previous_item,
                    "current": current_item,
                    "status": "text-changed",
                    "similarity": round(ratio, 3),
                }
            )
            paired_prev.add(id(previous_item))
            paired_cur.add(id(current_item))

        for c_index, candidates in backward.items():
            current_item = group["cur"][c_index]
            if id(current_item) in paired_cur:
                continue
            if len(candidates) != 1:
                ambiguous.append({"previous": None, "current": current_item})
                paired_cur.add(id(current_item))

    # Pass 3 - whatever is left. An ambiguous near-match lands here too: it is
    # reported as a removal plus an addition, with the ambiguity stated.
    for item in prev_left:
        if id(item) not in paired_prev:
            removed.append(item)
    for item in cur_left:
        if id(item) not in paired_cur:
            added.append(item)
    for pair in ambiguous:
        if pair["previous"] is not None:
            removed.append(pair["previous"])
        if pair["current"] is not None:
            added.append(pair["current"])

    renumbered = [
        {
            "previousId": match["previous"].get("id"),
            "currentId": match["current"].get("id"),
            "sourceKey": match["current"].get("sourceKey"),
        }
        for match in matches
        if match["previous"].get("id") != match["current"].get("id")
    ]

    return {
        "matched": matches,
        "added": added,
        "removed": removed,
        "ambiguous": ambiguous,
        "renumbered": renumbered,
    }


def _mapping_set(mappings):
    return {(m.get("epic") or m.get("ref"), m.get("linkSource")) for m in mappings or []}


def _access_set(entries):
    return {(entry.get("ref"), entry.get("status")) for entry in entries or []}


def compare_inventory(baseline, manifest):
    """Artifact-level differences between the baseline and this run."""
    previous_children = {
        child["ref"]: child for child in ((baseline or {}).get("scope") or {}).get("children") or []
    }
    current_children = {child["ref"]: child for child in manifest.get("children") or []}

    added = sorted(set(current_children) - set(previous_children))
    removed = sorted(set(previous_children) - set(current_children))
    changed, reopened, hashes_unavailable = [], [], []

    for ref in sorted(set(current_children) & set(previous_children)):
        previous, current = previous_children[ref], current_children[ref]
        previous_hash = previous.get("contentHash")
        if not previous_hash:
            # A schema v1 baseline carries no content hashes. Unknown is not
            # unchanged: everything that touches it gets reassessed.
            hashes_unavailable.append(ref)
        elif previous_hash != current.get("contentHash"):
            changed.append(ref)
        was_closed = (previous.get("state") or "").upper() == "CLOSED"
        is_open = (current.get("state") or "").upper() == "OPEN"
        if (was_closed and is_open) or (current.get("stateReason") or "").upper() == "REOPENED":
            reopened.append(ref)

    previous_access = _access_set((baseline or {}).get("access"))
    current_access = _access_set(manifest.get("access"))
    access_lost = sorted(
        {ref for ref, status in current_access if status in ("unreadable", "forbidden")}
        - {ref for ref, status in previous_access if status in ("unreadable", "forbidden")}
    )
    access_restored = sorted(
        {ref for ref, status in previous_access if status in ("unreadable", "forbidden")}
        - {ref for ref, status in current_access if status in ("unreadable", "forbidden")}
    )

    return {
        "artifactsAdded": added,
        "artifactsRemoved": removed,
        "contentChanged": changed,
        "hashesUnavailable": hashes_unavailable,
        "reopened": reopened,
        "accessLost": access_lost,
        "accessRestored": access_restored,
        "dependenciesChanged": _dependency_changes(baseline, manifest),
    }


def _dependency_changes(baseline, manifest):
    """Declared dependencies whose state or readability moved since the baseline.

    A dependency is not traversed, so nothing about it reaches a child's
    content hash. Without this, a blocking issue could close - or become
    unreadable - between runs and every assessment resting on it would be
    reused unchanged.

    A baseline that predates this field records no states, so every dependency
    present then counts as changed: unknown is not unchanged, the same rule the
    missing-content-hash case follows.
    """
    scope = (baseline or {}).get("scope") or {}
    current = {
        dependency["ref"]: dependency for dependency in manifest.get("dependencies") or []
    }
    stored = scope.get("dependencies")
    if stored is None:
        previously_seen = set(scope.get("otherInspected") or [])
        return sorted(previously_seen & set(current)) if baseline else []

    previous = {dependency["ref"]: dependency for dependency in stored}
    moved = []
    for ref in sorted(set(current) | set(previous)):
        before, after = previous.get(ref), current.get(ref)
        if before is None or after is None:
            moved.append(ref)
            continue
        if any(
            (before.get(field) or None) != (after.get(field) or None)
            for field in ("state", "stateReason", "accessible")
        ):
            moved.append(ref)
    return moved


def _touches(requirement, refs):
    """Does a stored assessment rest on any of these artifacts?"""
    if not refs:
        return False
    targets = set(refs)
    repos = {ref.split("#")[0] for ref in targets}
    for item in requirement.get("evidence") or []:
        ref = item.get("ref") or ""
        if ref in targets or ref.split("#")[0] in repos:
            return True
    return False


def plan(baseline_info, manifest, requirements, mappings, full_refresh=False):
    baseline = (baseline_info or {}).get("snapshot")
    previous_requirements = (baseline or {}).get("requirements") or []
    match = match_requirements(previous_requirements, requirements)
    inventory = compare_inventory(baseline, manifest)

    mapping_changed = bool(baseline) and _mapping_set((baseline or {}).get("mappings")) != _mapping_set(
        [{"epic": m.get("ref") or m.get("epic"), "linkSource": m.get("linkSource")} for m in mappings]
    )

    reasons_for_all = []
    if full_refresh:
        reasons_for_all.append("full refresh requested")
    if not baseline:
        reasons_for_all.append("no baseline snapshot: this run establishes one")
    else:
        from .snapshots import RULES_VERSION

        if baseline.get("rulesVersion") != RULES_VERSION:
            reasons_for_all.append(
                f"assessment rules changed ({baseline.get('rulesVersion') or 'unversioned'} -> {RULES_VERSION})"
            )
        if baseline.get("schemaVersion", 1) < 2:
            reasons_for_all.append("baseline predates content hashing, so reuse cannot be verified")
        if mapping_changed:
            reasons_for_all.append("the upstream mapping changed")

    observed = manifest.get("observed", bool(manifest.get("epics")))
    if not observed:
        reasons_for_all.append(
            manifest.get("unobservedReason") or "no upstream source was inspected this run"
        )

    changed_refs = set(
        inventory["contentChanged"]
        + inventory["artifactsRemoved"]
        + inventory["hashesUnavailable"]
        + inventory["reopened"]
        + inventory["accessLost"]
        + inventory["accessRestored"]
        + inventory["dependenciesChanged"]
    )
    new_evidence_available = bool(
        inventory["artifactsAdded"] or inventory["contentChanged"] or inventory["accessRestored"]
    )

    previous_by_key = {}
    for match_entry in match["matched"]:
        previous_by_key[id(match_entry["current"])] = match_entry

    reassess, reuse = [], []
    for requirement in requirements:
        entry = previous_by_key.get(id(requirement))
        reason = None
        if reasons_for_all:
            reason = reasons_for_all[0]
        elif entry is None:
            reason = "requirement is new since the baseline"
        elif entry["status"] == "text-changed":
            reason = "requirement text changed; the previous assessment does not carry over"
        elif _touches(entry["previous"], changed_refs):
            reason = "evidence it rests on changed, was removed, or changed access"
        elif entry["previous"].get("assessment") != "Evidence found" and new_evidence_available:
            reason = "upstream artifacts changed and this requirement was not previously covered"
        elif entry["previous"].get("assessment") is None:
            reason = "the baseline carries no assessment for it"
        elif (entry["previous"].get("downstream") or {}).get("state") == "pending":
            # Downstream artifacts are outside the traversal, so no hash this
            # differ computes can ever contradict a stored `pending`. Reusing it
            # would republish "qualification outstanding" indefinitely, long
            # after it stopped being something anyone checked. `unknown` is left
            # reusable: nobody looked then, nobody looked now, and saying so
            # again is still true.
            reason = (
                "downstream qualification was outstanding at the baseline and is not "
                "observable from the upstream traversal"
            )

        if reason:
            reassess.append(
                {
                    "id": requirement.get("id"),
                    "sourceKey": requirement.get("sourceKey"),
                    "type": requirement.get("type"),
                    "reason": reason,
                }
            )
        else:
            carried = dict(entry["previous"])
            carried.update(
                {
                    "id": requirement.get("id"),
                    "sourceKey": requirement.get("sourceKey"),
                    "type": requirement.get("type"),
                    "text": requirement.get("text"),
                    "heading": requirement.get("heading"),
                    "reused": True,
                    "assessedAt": entry["previous"].get("assessedAt")
                    or (baseline or {}).get("generatedAt"),
                    "assessedFromSnapshot": (baseline_info or {}).get("path"),
                }
            )
            reuse.append(carried)

    return {
        "baseline": {
            "path": (baseline_info or {}).get("path"),
            "generatedAt": (baseline or {}).get("generatedAt"),
            "publication": (baseline_info or {}).get("publication"),
            "schemaVersion": (baseline or {}).get("schemaVersion"),
            "rulesVersion": (baseline or {}).get("rulesVersion"),
        }
        if baseline
        else None,
        "baselineProblem": (baseline_info or {}).get("problem"),
        "fullRefresh": bool(full_refresh),
        "reassessAll": reasons_for_all,
        "requirementChanges": {
            "added": [
                {"id": r.get("id"), "sourceKey": r.get("sourceKey"), "type": r.get("type"), "text": r.get("text")}
                for r in match["added"]
            ],
            "removed": [
                {
                    "id": r.get("id"),
                    "sourceKey": r.get("sourceKey"),
                    "type": r.get("type"),
                    "text": r.get("text"),
                    "assessment": r.get("assessment"),
                }
                for r in match["removed"]
            ],
            "textChanged": [
                {
                    "id": m["current"].get("id"),
                    "previousId": m["previous"].get("id"),
                    "sourceKey": m["current"].get("sourceKey"),
                    "type": m["current"].get("type"),
                    "similarity": m.get("similarity"),
                }
                for m in match["matched"]
                if m["status"] == "text-changed"
            ],
            "ambiguous": [
                {
                    "previousId": (a["previous"] or {}).get("id"),
                    "currentId": (a["current"] or {}).get("id"),
                }
                for a in match["ambiguous"]
            ],
            "renumbered": match["renumbered"],
        },
        "mappingChanged": mapping_changed,
        "previousMappings": [m.get("epic") for m in (baseline or {}).get("mappings") or []],
        "inventoryChanges": inventory,
        "reassess": reassess,
        "reuse": reuse,
        "autoFill": None if observed else scope_mod.AUTO_FILL,
        # The action an auto-filled row asks for depends on why nothing was
        # observed: add a link, or get read access to the one already there.
        "autoFillGap": None if observed else scope_mod.gap(manifest.get("unobservedKind")),
        # `sourceKey` is not decoration. A rollup over six Jira issues has five
        # criteria called AC1, so a pair keyed on the id alone silently matches
        # one Jira's criterion against another's.
        "matchedPairs": [
            {
                "sourceKey": m["current"].get("sourceKey"),
                "previousSourceKey": m["previous"].get("sourceKey"),
                "currentId": m["current"].get("id"),
                "previousId": m["previous"].get("id"),
                "previousAssessment": m["previous"].get("assessment"),
                "previousDownstream": (m["previous"].get("downstream") or {}).get("state"),
                "textChanged": m["status"] == "text-changed",
            }
            for m in match["matched"]
        ],
    }
