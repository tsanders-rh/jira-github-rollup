"""Join a cited evidence ref to what the run already collected.

Which artifact is evidence for a criterion is a judgement, and it stays with
the model. What that artifact *is* - a pull request or an issue, merged or
open, and when it landed - is a mechanical fact the collector fetched and the
manifest carries. Asking the model to type those in beside the ref makes it a
transcription layer for its own input, and the transcription drifts.

It drifts somewhere load-bearing. `at` is what the trend section compares
against the baseline to decide whether a changed assessment is implementation
progress or evidence that was there all along and has only now been found. A
merge time rounded to the minute flips that classification, and nothing
downstream can notice.

So an assessment cites `{"ref": ...}` and this module fills the rest in:

* `owner/repo#123` is looked up in the manifest - an epic, a child, a child's
  pull request, or a declared dependency.
* `owner/repo@revision:path` is looked up in the follow-up reads this run
  made: a source read that actually happened.
* Anything else is not a traversed artifact at all - a CI job name is the
  usual case - and states its own `kind`, because there is nothing to join it
  to.

A ref that resolves to nothing is an error naming it: today it would be
accepted with whatever fields came with it, which is how a typo becomes a
table cell. A supplied field that disagrees with the collected one is also an
error, rather than one side quietly winning - a disagreement means either the
model mistyped or the manifest is not the document it thought it was reading,
and both are worth stopping for.
"""

from __future__ import annotations

import re

from . import util

# The fields the pipeline owns. Supplying one is allowed only where it agrees
# with what was collected; it is never the source of truth.
JOINED = ("kind", "state", "at")

# Both lists an assessment can cite. `refutingEvidence` carries the artifacts
# behind a `confirmed-unmet` call, which is the claim in this report with the
# least room for a mistyped ref.
EVIDENCE_FIELDS = ("evidence", "refutingEvidence")

# `owner/name#123`, the only shape the manifest indexes.
ARTIFACT_REF = re.compile(r"^[\w.-]+/[\w.-]+#\d+$")
# `owner/name@revision:path`, the shape `followup.source_ref` writes.
SOURCE_REF = re.compile(r"^[\w.-]+/[\w.-]+@[^:]+:.+$")

SOURCE_KIND = "source"
MANIFEST_KINDS = ("issue", "pr")


def index(manifest):
    """Every traversed artifact, by ref, with the three joined fields.

    `at` is the moment the artifact became the evidence it is: a pull request
    merged, an issue closed, or - for anything still open - created.
    Deliberately not `updatedAt`, which a comment moves: dating an open PR by
    it would tell the trend section that work happened this week whenever
    somebody replied to a review.
    """
    entries = {}
    # Children first: they carry more than the same ref does anywhere else.
    for child in manifest.get("children") or []:
        _put(entries, child.get("ref"), "issue", child.get("state"),
             child.get("closedAt") or child.get("createdAt"))
        for pull_request in child.get("prs") or []:
            _put(entries, pull_request.get("ref"), "pr", pull_request.get("state"),
                 pull_request.get("mergedAt") or pull_request.get("createdAt"))
    for epic in manifest.get("epics") or []:
        _put(entries, epic.get("ref"), "issue", epic.get("state"),
             epic.get("closedAt") or epic.get("createdAt"))
    for dependency in manifest.get("dependencies") or []:
        _put(entries, dependency.get("ref"), "issue", dependency.get("state"),
             dependency.get("closedAt") or dependency.get("createdAt"))
    return entries


def _put(entries, ref, kind, state, at):
    if not ref or ref in entries:
        return
    # Lowercased because the collector stores an issue state as `CLOSED` and a
    # PR state as `merged`, and the two render side by side in one list.
    entries[ref] = {"kind": kind, "state": (state or "").strip().lower() or None, "at": at or None}


def resolve(items, known_refs, source_reads, where):
    """One cited list, joined. Returns the items and everything refused."""
    reads = set(source_reads or [])
    resolved, problems = [], []
    for item in items or []:
        if not isinstance(item, dict):
            problems.append(f"{where}: an evidence item is {item!r}, not an object with a ref")
            continue
        ref = str(item.get("ref") or "").strip()
        if not ref:
            problems.append(f"{where}: an evidence item has no ref")
            continue
        collected, problem = _lookup(ref, item, known_refs, reads)
        if problem:
            problems.append(f"{where}: {problem}")
            continue
        merged = dict(item, ref=ref)
        if collected is None:
            # Self-described: nothing collected describes it, so what the
            # model wrote is all there is.
            resolved.append(merged)
            continue
        for field in JOINED:
            disagreement = _conflict(field, item.get(field), collected.get(field), ref)
            if disagreement:
                problems.append(f"{where}: {disagreement}")
                continue
            value = collected.get(field)
            if value is None:
                # An absent key, not a null one: "nothing collected records
                # this" is how every reader of these items already spells it.
                merged.pop(field, None)
            else:
                merged[field] = value
        resolved.append(merged)
    return resolved, problems


def _lookup(ref, item, known_refs, reads):
    """What the run collected about this ref, or why nothing does.

    The declared `kind` decides where to look, and the ref's shape decides
    when none is declared. Declaring `pr` on something the manifest has never
    heard of is an error rather than an escape hatch - otherwise the one way
    to cite an untraversed artifact would also be the one way to smuggle one
    in.
    """
    declared = (item.get("kind") or "").strip().lower() or None
    if declared in MANIFEST_KINDS or (declared is None and ARTIFACT_REF.match(ref)):
        collected = known_refs.get(ref)
        if collected is None:
            return None, (
                f"evidence {ref!r} is not an artifact this run traversed, so nothing can be "
                "said about it. Cite a ref the manifest carries, or - for a CI check or "
                "anything else outside the traversal - give the item its own `kind`"
            )
        return collected, None
    if declared == SOURCE_KIND or (declared is None and SOURCE_REF.match(ref)):
        if ref not in reads:
            return None, (
                f"evidence {ref!r} names a source read this run did not make. Read it with "
                "`rollup.py source` before citing it, or cite the artifact it came from"
            )
        # No `at`. The ledger records when the file was read, which is now;
        # dating the evidence by it would report every follow-up read as
        # implementation progress since the baseline.
        return {"kind": SOURCE_KIND, "state": None, "at": None}, None
    if declared is None:
        return None, (
            f"evidence {ref!r} is neither an `owner/repo#number` ref nor a source read, so "
            "nothing collected this run describes it. Give it a `kind` - `check` for a CI "
            "job - or correct the ref"
        )
    return None, None


def _conflict(field, supplied, collected, ref):
    if supplied is None or _agrees(field, supplied, collected):
        return None
    if collected is None:
        return (
            f"evidence {ref!r} states {field}={supplied!r}, but nothing collected for it "
            f"records a value for {field}. Leave the field out rather than supplying one"
        )
    return (
        f"evidence {ref!r} states {field}={supplied!r} but what was collected says "
        f"{collected!r}. Leave the field out; the assembler fills it in"
    )


def _agrees(field, supplied, collected):
    """Equal as the field means it, which for `at` is as an instant.

    A timestamp rounded to the minute is the drift this whole module is for,
    so `2026-09-24T15:16:00Z` must not pass against `…T15:16:34Z`. Parsing
    both still lets the same instant through in another notation, which is a
    difference nobody acted on.
    """
    if field == "at":
        first, second = util.parse_iso(supplied), util.parse_iso(collected)
        if first and second:
            return first == second
    return str(supplied).strip().lower() == str(collected or "").strip().lower()


def resolve_assessments(assessments, manifest, source_reads):
    """Every fresh assessment's cited lists, joined. Returns them and the refusals."""
    known_refs = index(manifest or {})
    out, problems = [], []
    for record in assessments or []:
        if not isinstance(record, dict):
            out.append(record)
            continue
        updated = dict(record)
        where = f"{record.get('id')} ({record.get('sourceKey')})"
        for field in EVIDENCE_FIELDS:
            if record.get(field) is None:
                continue
            items, refused = resolve(record[field], known_refs, source_reads, where)
            updated[field] = items
            problems.extend(refused)
        out.append(updated)
    return out, problems
