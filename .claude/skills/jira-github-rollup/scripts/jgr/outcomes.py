"""Outcome classification: four mutually exclusive buckets that sum to the total.

The four coverage assessments answer "what did the evidence establish". The four
*outcomes* answer the question a reader of the Jira actually asks: how many of
the things we committed to are met. They are not the same question, and the
mapping between them is deliberately lossy in one direction only.

    Evidence found      -> met
    Partial evidence    -> partial
    Unable to assess    -> unverified
    No evidence found   -> unverified          (the default, always)
                        -> confirmed-unmet     only on an explicit, evidenced call

That last line is the whole point of this module. "We looked and found nothing"
and "we looked and found that it does not work" are different findings, and
collapsing them is the single most damaging thing this report could do: it turns
an untracked requirement into a failed one, and sends a reader to argue with a
team that may have shipped the work somewhere nobody linked.

So `confirmed-unmet` is never inferred. It requires the model to say so
explicitly *and* to cite the evidence that refutes the criterion, and this
module rejects the claim otherwise. Missing evidence stays `unverified`
forever, however much of it is missing.

`met` is guarded from the other side. A criterion is a conjunction of clauses,
and evidence that the work *exists* is routinely mistaken for evidence that
every clause of it holds. So `met` requires that no clause was left undecided
(`unresolvedClauses`) and none was left unsupported (`uncoveredClauses`).
Naming those clauses is a judgement and stays with the model; refusing to call
the result `met` is mechanical, and lives here.
"""

from __future__ import annotations

from . import clauses as clauses_mod

# Order matters: it is the column order in every rendering, and the order the
# counts are reported in. Worst-understood last.
OUTCOMES = ("met", "partial", "confirmed-unmet", "unverified")

# Column headings on the count table. "Outcomes met" reads as a heading over a
# number; it reads wrong in a cell describing one criterion, which is what
# ROW_LABELS is for.
LABELS = {
    "met": "Outcomes met",
    "partial": "Partial",
    "confirmed-unmet": "Confirmed unmet",
    "unverified": "Unverified",
}

ROW_LABELS = dict(LABELS, met="Met")

# What the counts are a count *of*. Printed next to them, every time, because
# "3 of 9 met" invites exactly one wrong reading.
CAPTION = "Upstream evidence assessment, not release completion."

_FROM_ASSESSMENT = {
    "Evidence found": "met",
    "Partial evidence": "partial",
    "No evidence found": "unverified",
    "Unable to assess": "unverified",
}


def classify(requirement):
    """The outcome for one requirement. Never raises; see `problems` to validate."""
    assessment = requirement.get("assessment")
    base = _FROM_ASSESSMENT.get(assessment)
    if base is None:
        return "unverified"
    if requirement.get("outcome") == "confirmed-unmet" and _refutation_holds(requirement):
        return "confirmed-unmet"
    return base


def _refutation_holds(requirement):
    """A confirmed-unmet claim is only honoured when it is actually supported.

    Two conditions, both necessary. The criterion must not already be partly
    supported - "some clauses work" and "it is confirmed not to work" cannot
    both be true - and there must be something to point at.
    """
    if requirement.get("assessment") != "No evidence found":
        return False
    return bool(requirement.get("refutingEvidence") or requirement.get("evidence"))


def open_clauses(requirement):
    """Clauses standing between this criterion and `met`, undecided or unsupported."""
    return (
        list(requirement.get("unresolvedClauses") or []),
        list(requirement.get("uncoveredClauses") or []),
    )


def problems(requirements):
    """Why a claim was refused. Reported, never silently dropped."""
    found = []
    for requirement in requirements or []:
        found.extend(_clause_problems(requirement))
        # Why each open clause is open, which is three findings and not one.
        # Same shape of rule as `confirmed-unmet` below, at clause scope.
        found.extend(clauses_mod.problems(requirement, label_of(requirement)))
        if requirement.get("outcome") is None:
            continue
        where = f"{requirement.get('id')} ({requirement.get('sourceKey')})"
        if requirement["outcome"] not in OUTCOMES:
            found.append(f"{where}: outcome {requirement['outcome']!r} is not one of {OUTCOMES}")
            continue
        if requirement["outcome"] != "confirmed-unmet":
            found.append(
                f"{where}: outcome {requirement['outcome']!r} is derived from the assessment and "
                "must not be set by hand; only 'confirmed-unmet' may be declared"
            )
            continue
        if requirement.get("assessment") != "No evidence found":
            found.append(
                f"{where}: confirmed-unmet declared on {requirement.get('assessment')!r}; "
                "a criterion with supporting evidence cannot also be confirmed unmet"
            )
        elif not (requirement.get("refutingEvidence") or requirement.get("evidence")):
            found.append(
                f"{where}: confirmed-unmet declared with nothing cited. It requires affirmative "
                "evidence that the outcome is not satisfied; absence of evidence is 'unverified'"
            )
    return found


def _clause_problems(requirement):
    """`Evidence found` is a claim about the whole criterion, and is checked as one.

    Refusing rather than quietly downgrading to `Partial evidence`: the
    downgrade would be the safe number but the wrong row, because the detail
    column would still read as though the criterion were fully established.
    The model has to say which clauses are open, and then say so in the prose.
    """
    if requirement.get("assessment") != "Evidence found":
        return []
    unresolved, uncovered = open_clauses(requirement)
    if not (unresolved or uncovered):
        return []
    where = f"{requirement.get('id')} ({requirement.get('sourceKey')})"
    detail = []
    if unresolved:
        detail.append(f"undecided: {'; '.join(str(c) for c in unresolved)}")
    if uncovered:
        detail.append(
            "unsupported by evidence: "
            + "; ".join(clauses_mod.normalize(c)["text"] or str(c) for c in uncovered)
        )
    return [
        f"{where}: 'Evidence found' claims every clause of the criterion holds, but "
        + ", ".join(detail)
        + ". Assess it 'Partial evidence' (or 'No evidence found' if nothing is "
        "covered); a criterion with an open clause is not met"
    ]


def tally(requirements):
    """Counts per outcome, plus the ids in each. Guaranteed to sum to the total.

    The sum is asserted rather than assumed. A reader who adds the four numbers
    and gets a different total has every reason to distrust the rest of the
    report, and this is cheap insurance against the kind of filtering bug that
    produces exactly that.
    """
    counts = {name: 0 for name in OUTCOMES}
    ids = {name: [] for name in OUTCOMES}
    for requirement in requirements or []:
        outcome = classify(requirement)
        counts[outcome] += 1
        ids[outcome].append(label_of(requirement))
    total = len(requirements or [])
    if sum(counts.values()) != total:  # pragma: no cover - structurally impossible
        raise AssertionError(f"outcome counts {counts} do not sum to {total}")
    return {"counts": counts, "ids": ids, "total": total, "caption": CAPTION}


def label_of(requirement):
    """`SC6 (RHOAIENG-1234)` - how a criterion is named when there is no anchor for it."""
    key = requirement.get("sourceKey")
    return f"{requirement.get('id')} ({key})" if key else str(requirement.get("id"))


def confidence(assembly, requirements, tallied):
    """Delivery confidence, or an honest refusal to state one.

    Deliberately not a function of the counts. Nine criteria met says nothing
    about whether the thing ships: that depends on a release target, on
    dependencies nobody has linked, and on qualification evidence this skill
    does not inspect. Where those are missing the answer is "Not assessed",
    and no amount of green in the table changes it.
    """
    supplied = (assembly.get("deliveryConfidence") or {}).get("value")
    reason = (assembly.get("deliveryConfidence") or {}).get("reason")

    blockers = []
    if not (assembly.get("jira") or {}).get("fixVersions"):
        blockers.append("no release target recorded on the Jira issue")
    downstream_unknown = sum(
        1
        for requirement in requirements or []
        if ((requirement.get("downstream") or {}).get("state") or "unknown") == "unknown"
    )
    if downstream_unknown:
        blockers.append(
            f"{downstream_unknown} of {tallied['total']} criteria have no downstream "
            "qualification evidence"
        )
    if tallied["counts"]["unverified"]:
        blockers.append(
            f"{tallied['counts']['unverified']} unverified, including work that may be "
            "tracked outside the linked epic"
        )

    if blockers:
        return {
            "value": "Not assessed",
            "reason": "; ".join(blockers),
            "refused": bool(supplied and supplied != "Not assessed"),
            "supplied": supplied,
        }
    return {"value": supplied or "Not assessed", "reason": reason, "refused": False, "supplied": supplied}
