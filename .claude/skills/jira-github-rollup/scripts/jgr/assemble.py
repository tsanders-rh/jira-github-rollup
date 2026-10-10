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

import re

from . import htmlreport as htmlreport_mod
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


# Claims about the whole world, written from a traversal of part of it.
#
# This is a mechanical check on a judgement, which is usually the wrong shape,
# but the specific error is not a judgement: nothing this pipeline reads can
# establish that an upstream issue does not exist anywhere. It traverses a
# mapped epic and its children. "No upstream issue covers this" is therefore
# not a stronger version of "nothing in the traversed set covers this" - it is
# a claim about repositories that were never opened, and the reader acts on it
# by scheduling work that may already be underway somewhere else.
UNSCOPED_CLAIM = re.compile(
    r"""(?ix)
    \b no \s+ (?:upstream\s+)? (?:issue|pr|work|ticket|epic) \s+ (?:exists|covers)
  | \b there \s+ is \s+ no \s+ (?:upstream\s+)? (?:issue|pr|work|ticket|epic)
  | \b (?:nothing|no\s+work) \s+ (?:exists|has\s+been\s+done) \b
  | \b not \s+ implemented \s+ anywhere \b
    """
)
SCOPED_HINT = (
    "scope the claim to what was actually read - \"no work in the traversed set covers this\" "
    "- or check and say where you checked. A traversal of one epic cannot establish that "
    "something does not exist"
)


def unscoped_claims(text, where):
    """Reject an absolute-existence claim in model prose. See `UNSCOPED_CLAIM`."""
    match = UNSCOPED_CLAIM.search(text or "")
    if not match:
        return []
    return [f"{where}: {match.group(0).strip()!r} claims more than a traversal can show; {SCOPED_HINT}"]


def _validate(record, where):
    problems = []
    for field in ("gap", "coverageDetail", "notes"):
        problems.extend(unscoped_claims(record.get(field), f"{where} {field}"))
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


def cross_check(report, summary_text, tallied, html_text=None, requirements=None):
    """The outputs must not be able to disagree. This is where that is proved.

    They are rendered from one tally, so disagreement would be a bug rather
    than a judgement, which is exactly the kind of thing worth asserting: a
    summary that says 3 met beside a table that says 2 destroys trust in both,
    and nothing downstream would catch it. The HTML is held to the same
    standard for the same reason - it is the copy most likely to be the one
    somebody actually reads.
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
    problems.extend(_count_claims(summary_text, tallied))
    problems.extend(unscoped_claims(summary_text, "the Jira summary"))
    problems.extend(unscoped_claims(report, "the full assessment"))
    problems.extend(_html_problems(html_text, tallied, requirements))
    return problems


def _html_problems(html_text, tallied, requirements):
    """The HTML's counts, against the same tally, plus what it must not carry.

    The by-type check is not a restatement of the totals: the rows come from
    `metrics.by_type` and the totals from `outcomes.tally`, so a type that
    stopped being counted - a new requirement type, a typo in `_TYPE_ORDER` -
    shows up here as rows that no longer sum to the total the Jira comment
    carries.
    """
    if html_text is None:
        return []
    problems = []
    totals = "".join(
        f'<td class="num"><strong>{tallied["counts"][name]}</strong></td>'
        for name in outcomes_mod.OUTCOMES
    )
    if tallied["total"] and totals not in html_text:
        problems.append(
            "the HTML full assessment does not carry the outcome totals the other two outputs do"
        )
    if requirements is not None:
        groups = metrics_mod.by_type(requirements)
        if sum(group["total"] for group in groups) != tallied["total"]:
            problems.append(
                "the HTML per-type rows cover "
                f"{sum(group['total'] for group in groups)} criteria but the tally says "
                f"{tallied['total']}; some requirement type is not being counted"
            )
        for name in outcomes_mod.OUTCOMES:
            across = sum(group["outcomes"][name] for group in groups)
            if across != tallied["counts"][name]:
                problems.append(
                    f"the HTML per-type rows total {across} {name} but the tally says "
                    f"{tallied['counts'][name]}"
                )
    leaked = links_mod.unpublishable(html_text)
    if leaked:
        problems.append(
            "the HTML full assessment contains local paths that should not be shared: "
            + ", ".join(sorted(set(leaked)))
        )
    return problems


# "two of the three met criteria" in prose, where the table says two met.
# Narrative is free text and the counts are not, so a number written beside an
# outcome name is checkable against the tally - and a summary whose sentence
# disagrees with its own table is the specific failure that makes a reader
# stop believing either.
_COUNT_CLAIM = re.compile(
    r"\b(\d+)\s+(?:further\s+|remaining\s+|other\s+)?"
    r"(?:criteria|criterion)?\s*"
    r"(met|partial|unverified|confirmed[- ]unmet)\b",
    re.I,
)
_CLAIM_TO_OUTCOME = {
    "met": "met",
    "partial": "partial",
    "unverified": "unverified",
    "confirmed-unmet": "confirmed-unmet",
    "confirmed unmet": "confirmed-unmet",
}


def _count_claims(summary_text, tallied):
    problems = []
    for claimed, word in _COUNT_CLAIM.findall(summary_text or ""):
        name = _CLAIM_TO_OUTCOME.get(word.lower())
        actual = tallied["counts"].get(name)
        if actual is not None and int(claimed) != actual:
            problems.append(
                f"the Jira summary says {claimed} {word} but the tally both outputs are "
                f"rendered from says {actual}"
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

    # Before anything is rendered: every narrative claim has to name rows that
    # exist in this run. The check is traceability, not truth - whether the
    # evidence supports the sentence is the model's judgement and stays there.
    untraceable = summary_mod.narrative_problems(assembly.get("narrative"), merged)
    if untraceable:
        raise ValueError("; ".join(untraceable))

    tallied = outcomes_mod.tally(merged)
    confidence = outcomes_mod.confidence(assembly, merged, tallied)

    computed = render_mod.compute_metrics(assembly)
    assembly["metrics"] = computed
    report = render_mod.render(assembly, tallied)
    # Computed once and stored, because the baseline it was computed against
    # is not in the snapshot. Re-rendering has no way to derive this line and
    # would silently print "Baseline established." over a summary that said
    # something else when it was reviewed.
    trend = assembly.get("summaryTrend") or summary_mod.trend_line(assembly, tallied)
    summary_text = summary_mod.render(
        assembly, tallied, confidence, trend=trend, full_assessment_url=full_assessment_url
    )
    # Rendered on every run whether or not `--html` asked for it, so that the
    # third rendering is cross-checked every time rather than only on the runs
    # that happen to write it out. It is string building over data already in
    # memory; the caller discards it if it was not asked for.
    html_text = htmlreport_mod.render(assembly, tallied)

    disagreements = cross_check(report, summary_text, tallied, html_text, merged)
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
            narrative=assembly.get("narrative"),
            summaryNarrative=assembly.get("summary"),
            trend=trend,
            prose={
                key: assembly.get(key)
                for key in ("caveats", "risks", "dependencies", "trendNotes", "blocked")
                if assembly.get(key)
            },
        )
        snapshot_path = snapshots_mod.save(snapshot, directory=directory)

    words = summary_mod.word_count(summary_text)
    return {
        "report": report,
        "summary": summary_text,
        "html": html_text,
        "summaryWords": words,
        # Reported, not enforced. Under the floor usually means the bullets are
        # a list of ids rather than a status; over the ceiling means nobody
        # will read the last two bullets. Neither is worth refusing to render
        # over, and truncating the model's prose to hit a number would be.
        "summaryWordBudget": {
            "floor": summary_mod.WORD_FLOOR,
            "ceiling": summary_mod.WORD_CEILING,
            "within": summary_mod.WORD_FLOOR <= words <= summary_mod.WORD_CEILING,
        },
        "narrativeClaims": len(assembly.get("narrative") or []),
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
