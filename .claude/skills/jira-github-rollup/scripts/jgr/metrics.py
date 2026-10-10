"""The three unweighted ratios, their buckets, and movement between two runs.

Every rule that an agent could get quietly wrong lives here as code:

* `unknown` (not observed) and `N/A` (observed zero) are different values and
  are never substituted for one another. A 404 is not a count of zero.
* `Partial evidence` earns no fractional credit. It is a bucket, never a
  numerator term.
* `Unable to assess` and `NOT_PLANNED` stay in their denominators.
* Percentage-point deltas come from unrounded percentages, rounded once.
* Nothing here produces a rate, a velocity, or a projected date, and there is
  no field for one.
"""

from __future__ import annotations

from . import outcomes as outcomes_mod
from . import util

ASSESSMENTS = ("Evidence found", "Partial evidence", "No evidence found", "Unable to assess")
DOWNSTREAM = ("confirmed", "pending", "unknown")

# What each downstream state asserts, in the reader's terms. The distinction
# that matters is between the two that look alike in a table: `unknown` is
# nobody looked, `pending` is somebody looked and found nothing qualifying.
# Collapsing them turns an unopened question into a negative result.
DOWNSTREAM_LABELS = {
    "confirmed": "Verified, with evidence",
    "pending": "Inspected; no qualifying evidence found",
    "unknown": "Not inspected",
}

UNKNOWN = "unknown"
OBSERVED = "observed"
NOT_APPLICABLE = "na"


def ratio(numerator, denominator, observed=True, reason=None):
    if not observed:
        return {
            "state": UNKNOWN,
            "numerator": None,
            "denominator": None,
            "pct": None,
            "reason": reason or "not observed",
        }
    if denominator == 0:
        return {
            "state": NOT_APPLICABLE,
            "numerator": 0,
            "denominator": 0,
            "pct": None,
            "reason": reason or "none were found",
        }
    pct = 100.0 * numerator / denominator
    return {
        "state": OBSERVED,
        "numerator": numerator,
        "denominator": denominator,
        "pct": pct,
        "pctDisplay": util.round_half_up(pct),
        "reason": None,
    }


def render_ratio(value):
    if value["state"] == UNKNOWN:
        return "unknown"
    if value["state"] == NOT_APPLICABLE:
        return "N/A"
    return f"{value['numerator']}/{value['denominator']} ({value['pctDisplay']}%)"


def child_metrics(children, observed=True, reason=None):
    buckets = {
        "completed": 0,
        "notPlanned": 0,
        "noReasonRecorded": 0,
        "open": 0,
        "reopened": 0,
        "unreadable": 0,
    }
    for child in children or []:
        state = (child.get("state") or "").upper()
        state_reason = (child.get("stateReason") or "").upper()
        if child.get("accessible") is False:
            buckets["unreadable"] += 1
            continue
        if state == "CLOSED":
            if state_reason == "COMPLETED":
                buckets["completed"] += 1
            elif state_reason == "NOT_PLANNED":
                buckets["notPlanned"] += 1
            else:
                buckets["noReasonRecorded"] += 1
        else:
            buckets["open"] += 1
            if state_reason == "REOPENED":
                buckets["reopened"] += 1

    total = len(children or [])
    value = ratio(buckets["completed"], total, observed=observed, reason=reason)
    value["buckets"] = buckets
    return value


def by_type(requirements):
    """Outcomes counted separately for AC, SC and DoD, never pooled.

    They are different kinds of claim. An acceptance criterion describes
    behaviour someone can check, a success criterion describes an outcome the
    feature is for, and a definition-of-done item is process. Adding them
    produces a number that looks like feature completion and is not one -
    which is why nothing here divides the sum by anything.
    """
    groups = {}
    for requirement in requirements or []:
        kind = requirement.get("type") or "REQ"
        group = groups.setdefault(
            kind,
            {
                "type": kind,
                "total": 0,
                "outcomes": {name: 0 for name in outcomes_mod.OUTCOMES},
                "downstream": {name: 0 for name in DOWNSTREAM},
            },
        )
        group["total"] += 1
        group["outcomes"][outcomes_mod.classify(requirement)] += 1
        state = ((requirement.get("downstream") or {}).get("state") or "unknown").lower()
        group["downstream"][state if state in DOWNSTREAM else "unknown"] += 1
    return [groups[kind] for kind in sorted(groups, key=_type_rank)]


_TYPE_ORDER = ("AC", "SC", "DoD", "REQ")


def _type_rank(kind):
    return (_TYPE_ORDER.index(kind) if kind in _TYPE_ORDER else len(_TYPE_ORDER), kind)


def requirement_metrics(requirements):
    counts = {name: 0 for name in ASSESSMENTS}
    downstream = {name: 0 for name in DOWNSTREAM}
    mix = {}
    unassessed = []
    for requirement in requirements or []:
        assessment = requirement.get("assessment")
        if assessment in counts:
            counts[assessment] += 1
        else:
            unassessed.append(requirement.get("id"))
        state = ((requirement.get("downstream") or {}).get("state") or "unknown").lower()
        downstream[state if state in downstream else "unknown"] += 1
        mix[requirement.get("type") or "REQ"] = mix.get(requirement.get("type") or "REQ", 0) + 1

    total = len(requirements or [])
    coverage = ratio(counts["Evidence found"], total)
    coverage["buckets"] = counts
    downstream_ratio = ratio(downstream["confirmed"], total)
    downstream_ratio["buckets"] = downstream
    return {
        "coverage": coverage,
        "downstream": downstream_ratio,
        "mix": mix,
        "byType": by_type(requirements),
        "total": total,
        "unassessed": unassessed,
    }


def compute(requirements, children, observed=True, unobserved_reason=None):
    requirement_side = requirement_metrics(requirements)
    return {
        "children": child_metrics(children, observed=observed, reason=unobserved_reason),
        "coverage": requirement_side["coverage"],
        "downstream": requirement_side["downstream"],
        "mix": requirement_side["mix"],
        "byType": requirement_side["byType"],
        "total": requirement_side["total"],
        "unassessed": requirement_side["unassessed"],
    }


def from_snapshot(snapshot):
    """Recompute the baseline's metrics from its own stored facts."""
    scope = snapshot.get("scope") or {}
    observed = scope.get("observed")
    if observed is None:
        observed = bool(snapshot.get("mappings"))
    return compute(
        snapshot.get("requirements") or [],
        scope.get("children") or [],
        observed=observed,
        unobserved_reason=scope.get("unobservedReason"),
    )


def delta(previous, current):
    """Movement between two ratios, in counts and in percentage points."""
    if previous is None or current is None:
        return {"kind": "no-baseline", "text": "-"}
    if previous["state"] == UNKNOWN and current["state"] == UNKNOWN:
        return {"kind": "unknown-both", "text": f"unknown - {current.get('reason') or 'not observed'}"}
    if current["state"] == UNKNOWN:
        return {"kind": "became-unknown", "text": f"unknown - {current.get('reason') or 'not observed'}"}
    if previous["state"] == UNKNOWN:
        return {"kind": "was-unknown", "text": "no comparable previous measurement"}
    if current["state"] == NOT_APPLICABLE or previous["state"] == NOT_APPLICABLE:
        return {"kind": "na", "text": f"N/A - {current.get('reason') or previous.get('reason') or ''}".strip(" -")}

    count_delta = current["numerator"] - previous["numerator"]
    pp = util.round_half_up(current["pct"] - previous["pct"])
    if count_delta == 0 and pp == 0 and current["denominator"] == previous["denominator"]:
        return {"kind": "no-change", "text": "no change", "count": 0, "pp": 0}
    return {
        "kind": "moved",
        "count": count_delta,
        "pp": pp,
        "denominatorMoved": current["denominator"] != previous["denominator"],
    }


def bucket_delta(previous, current, keys):
    parts = []
    for key in keys:
        before = (previous or {}).get(key, 0)
        after = (current or {}).get(key, 0)
        change = after - before
        parts.append("0" if change == 0 else f"{change:+d}".replace("-", "−"))
    return " / ".join(parts)


def _index(requirements):
    """Criteria keyed by `(sourceKey, id)`, which is the only unique key here.

    Criterion ids are unique within a Jira issue and nowhere else: a rollup
    spanning six issues has `AC1` five or six times. Keying on the id alone
    kept one of them and silently compared another issue's criterion against
    it, so the movement numbers were drawn from the wrong rows.
    """
    return {(req.get("sourceKey"), req.get("id")): req for req in requirements or []}


def _resolve(index, pair):
    """The current requirement a matched pair refers to, or None.

    Pairs written before `sourceKey` was recorded carry only an id. Those fall
    back to a unique id match and are skipped when the id is ambiguous: a pair
    that cannot be resolved to one row must not be resolved to an arbitrary
    one.
    """
    key = pair.get("sourceKey")
    if key is not None:
        return index.get((key, pair.get("currentId")))
    candidates = [req for (_, rid), req in index.items() if rid == pair.get("currentId")]
    return candidates[0] if len(candidates) == 1 else None


def like_for_like(matched_pairs, current_requirements):
    """Movement restricted to requirements present and unchanged in both runs.

    This is what a denominator change has to be reported against. Without it a
    percentage that fell because somebody wrote down more of what they wanted
    reads as a project going backwards.
    """
    index = _index(current_requirements)
    previous_found = current_found = total = 0
    for pair in matched_pairs or []:
        if pair.get("textChanged"):
            continue
        current = _resolve(index, pair)
        if current is None:
            continue
        total += 1
        if pair.get("previousAssessment") == "Evidence found":
            previous_found += 1
        if current.get("assessment") == "Evidence found":
            current_found += 1
    if total == 0:
        return None
    return {
        "total": total,
        "previous": ratio(previous_found, total),
        "current": ratio(current_found, total),
    }


def classify_assessment_changes(matched_pairs, current_requirements, baseline_generated_at):
    """Split assessment changes into progress, discovery, and undetermined.

    The test is the evidence's own timestamp against the baseline's generation
    time. Evidence that predates the baseline is work this run could finally
    see, not work that happened this month - reporting it as progress would be
    a false status update produced by an honest pipeline.
    """
    baseline_time = util.parse_iso(baseline_generated_at)
    index = _index(current_requirements)
    rank = {name: position for position, name in enumerate(ASSESSMENTS)}
    results = []

    for pair in matched_pairs or []:
        current = _resolve(index, pair)
        if current is None:
            continue
        before = pair.get("previousAssessment")
        after = current.get("assessment")
        if before == after:
            continue

        evidence = current.get("evidence") or []
        dates = [util.parse_iso(item.get("at")) for item in evidence]
        usable = [date for date in dates if date]
        improved = rank.get(after, 99) < rank.get(before, 99)

        if not improved:
            cause = "regression"
        elif not baseline_time or not usable:
            cause = "undetermined"
        elif any(date > baseline_time for date in usable):
            cause = "implementation-progress"
        else:
            cause = "newly-discovered-evidence"

        results.append(
            {
                "id": current.get("id"),
                "sourceKey": current.get("sourceKey"),
                "from": before,
                "to": after,
                "cause": cause,
                "evidence": [
                    {"ref": item.get("ref"), "at": item.get("at"), "kind": item.get("kind")}
                    for item in evidence
                ],
                "undatedEvidence": len(dates) - len(usable),
            }
        )
    return results
