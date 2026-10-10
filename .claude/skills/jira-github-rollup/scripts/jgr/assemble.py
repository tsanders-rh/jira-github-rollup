"""Merge fresh assessments with reused ones and emit the report and snapshot.

The merge is where "incremental" stops being visible. A reused assessment is
carried forward whole - its evidence, its provenance, the timestamp it was
made at - and then rendered exactly like a fresh one. The report is always
the complete current picture; nothing downstream of here can tell which rows
were reassessed this run except by reading `reused`.

An assessment that is neither supplied nor reusable is an error, not an
"Unable to assess". Silently filling a gap with a verdict nobody reached is
the one failure this pipeline must not have.
"""

from __future__ import annotations

from . import links as links_mod
from . import metrics as metrics_mod
from . import outcomes as outcomes_mod
from . import render as render_mod
from . import scope as scope_mod
from . import snapshots as snapshots_mod
from . import summary as summary_mod
from . import util

ASSESSMENT_FIELDS = (
    "assessment",
    "coverageDetail",
    "evidence",
    "evidenceState",
    "gap",
    "downstream",
    "unresolvedClauses",
    # Checkable clauses the evidence does not support. Carried for the same
    # reason as `outcome`: dropping it would turn a half-proved criterion into
    # a fully proved one, and would hide the bad claim from `outcomes.problems`.
    "uncoveredClauses",
    "notes",
    # A declared `confirmed-unmet` and what refutes the criterion. Carried here
    # rather than derived: dropping them would turn a finding that something
    # does not work back into "we did not look", and dropping them silently
    # would also hide a bad declaration from `outcomes.problems`.
    "outcome",
    "refutingEvidence",
)

def _key(requirement):
    return (
        requirement.get("sourceKey"),
        requirement.get("type"),
        util.normalize_text(requirement.get("text")),
    )


def _index(entries):
    by_key, by_id = {}, {}
    for entry in entries or []:
        by_key.setdefault(_key(entry), entry)
        if entry.get("id") and entry.get("sourceKey"):
            by_id.setdefault((entry["sourceKey"], entry["id"]), entry)
    return by_key, by_id


def _lookup(requirement, by_key, by_id):
    found = by_key.get(_key(requirement))
    if found is not None:
        return found
    return by_id.get((requirement.get("sourceKey"), requirement.get("id")))


def _validate(record, where):
    problems = []
    if record.get("assessment") not in metrics_mod.ASSESSMENTS:
        problems.append(
            f"{where}: assessment {record.get('assessment')!r} is not one of {metrics_mod.ASSESSMENTS}"
        )
    state = (record.get("downstream") or {}).get("state")
    if state is not None and state not in metrics_mod.DOWNSTREAM:
        problems.append(f"{where}: downstream state {state!r} is not one of {metrics_mod.DOWNSTREAM}")
    for item in record.get("evidence") or []:
        if not item.get("ref"):
            problems.append(f"{where}: an evidence item has no ref")
    if record.get("assessment") in ("Evidence found", "Partial evidence") and not record.get("evidence"):
        problems.append(
            f"{where}: assessed {record['assessment']!r} with no evidence recorded"
        )
    return problems


def merge(requirements, assessments, diff, generated_at):
    """Produce the full requirement list, each with exactly one assessment."""
    fresh_by_key, fresh_by_id = _index(assessments)
    reuse_by_key, reuse_by_id = _index((diff or {}).get("reuse"))
    auto_fill = (diff or {}).get("autoFill")

    merged, missing, problems = [], [], []
    for requirement in requirements:
        record = {
            "id": requirement.get("id"),
            "sourceKey": requirement.get("sourceKey"),
            "type": requirement.get("type"),
            "text": requirement.get("text"),
            "heading": requirement.get("heading"),
            "assessment": None,
            "coverageDetail": None,
            "evidence": [],
            "evidenceState": None,
            "gap": None,
            "downstream": {"state": "unknown", "detail": None},
            "unresolvedClauses": [],
            "uncoveredClauses": [],
            "outcome": None,
            "refutingEvidence": [],
            "reused": False,
            "assessedAt": generated_at,
            "assessedFromSnapshot": None,
        }
        source = _lookup(requirement, fresh_by_key, fresh_by_id)
        if source is not None:
            for field in ASSESSMENT_FIELDS:
                if source.get(field) is not None:
                    record[field] = source[field]
        else:
            carried = _lookup(requirement, reuse_by_key, reuse_by_id)
            if carried is not None:
                for field in ASSESSMENT_FIELDS:
                    if carried.get(field) is not None:
                        record[field] = carried[field]
                record["reused"] = True
                record["assessedAt"] = carried.get("assessedAt")
                record["assessedFromSnapshot"] = carried.get("assessedFromSnapshot")
            elif auto_fill in (scope_mod.AUTO_FILL, scope_mod.LEGACY_AUTO_FILL):
                record["assessment"] = "Unable to assess"
                record["evidenceState"] = "not observed"
                record["gap"] = (diff or {}).get("autoFillGap") or scope_mod.gap(None)
            else:
                missing.append(f"{record['id']} ({record['sourceKey']})")
                merged.append(record)
                continue

        problems.extend(_validate(record, f"{record['id']} ({record['sourceKey']})"))
        merged.append(record)

    return merged, missing, problems


def cross_check(report, summary_text, tallied):
    """The two outputs must not be able to disagree. This is where that is proved.

    They are rendered from one tally, so disagreement would be a bug rather
    than a judgement, which is exactly the kind of thing worth asserting: a
    summary that says 3 met beside a table that says 2 destroys trust in both,
    and nothing downstream would catch it.
    """
    problems = []
    row = "| " + " | ".join(str(tallied["counts"][name]) for name in outcomes_mod.OUTCOMES) + " |"
    for name, text in (("full assessment", report), ("Jira summary", summary_text)):
        if row not in text:
            problems.append(f"the {name} does not carry the outcome row {row}")
    if sum(tallied["counts"].values()) != tallied["total"]:
        problems.append(
            f"outcome counts {tallied['counts']} do not sum to {tallied['total']} criteria"
        )
    leaked = links_mod.unpublishable(summary_text)
    if leaked:
        problems.append(
            "the Jira summary contains paths a reader cannot follow and that should not be "
            "published: " + ", ".join(sorted(set(leaked)))
        )
    return problems


def build(assembly, directory=None, write_snapshot=True, full_assessment_url=None):
    """Render both outputs from one merge, and, unless suppressed, snapshot it.

    One merge, one tally, two renderings. The full assessment and the Jira
    summary are never built from separate passes over the data - that is the
    only way to guarantee the counts in the comment match the counts in the
    evidence table nobody re-reads.
    """
    generated_at = assembly.get("generatedAt") or util.iso(util.utcnow())
    assembly["generatedAt"] = generated_at
    diff = assembly.get("diff") or {}

    merged, missing, problems = merge(
        assembly.get("requirements") or [], assembly.get("assessments") or [], diff, generated_at
    )
    if missing:
        raise ValueError(
            "no assessment supplied or reusable for: "
            + ", ".join(missing)
            + ". Assess them, or pass them in `assessments`."
        )
    if problems:
        raise ValueError("; ".join(problems))

    assembly["requirements"] = merged

    refused = outcomes_mod.problems(merged)
    if refused:
        raise ValueError("; ".join(refused))

    tallied = outcomes_mod.tally(merged)
    confidence = outcomes_mod.confidence(assembly, merged, tallied)

    computed = render_mod.compute_metrics(assembly)
    assembly["metrics"] = computed
    report = render_mod.render(assembly, tallied)
    summary_text = summary_mod.render(
        assembly, tallied, confidence, full_assessment_url=full_assessment_url
    )

    disagreements = cross_check(report, summary_text, tallied)
    if disagreements:
        raise ValueError("; ".join(disagreements))

    snapshot_path = None
    if write_snapshot:
        jira = dict(assembly["jira"])
        jira["rollupStatus"] = render_mod.derive_status(assembly, computed)
        snapshot = snapshots_mod.build(
            jira,
            assembly.get("mappings") or [],
            assembly["manifest"],
            merged,
            {"snapshot": assembly.get("baselineSnapshot"), "publication": (diff.get("baseline") or {}).get("publication")},
            generated_at=generated_at,
            outcomes={"counts": tallied["counts"], "caption": tallied["caption"]},
        )
        snapshot_path = snapshots_mod.save(snapshot, directory=directory)

    return {
        "report": report,
        "summary": summary_text,
        "summaryWords": summary_mod.word_count(summary_text),
        "outcomes": tallied["counts"],
        "deliveryConfidence": confidence,
        "snapshotPath": snapshot_path,
        "metrics": {
            "children": metrics_mod.render_ratio(computed["children"]),
            "coverage": metrics_mod.render_ratio(computed["coverage"]),
            "downstream": metrics_mod.render_ratio(computed["downstream"]),
        },
        "reused": sum(1 for record in merged if record["reused"]),
        "assessed": sum(1 for record in merged if not record["reused"]),
    }
