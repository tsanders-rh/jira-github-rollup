"""Why a clause of a criterion is still open - which is three different things.

A criterion that is not fully met leaves the reader one question: what do I do
about it. The answer depends entirely on *why* the clause is open, and the
three reasons go to three different people:

| Kind | What was established | Who acts |
| --- | --- | --- |
| `implementation-gap` | Something inspected shows the behaviour missing or contradicted | Engineering |
| `evidence-gap` | What was inspected does not establish the behaviour either way | Whoever can point at the work, or a further read |
| `inspection-limitation` | The thing that would settle it could not be read | Whoever can grant access, or the next run |

Collapsing them is the failure this module exists for, and it collapses in a
predictable direction: a question nobody answered gets written up as a feature
nobody built. So two rules are mechanical here, because both are violated
silently and neither is a judgement:

* **An `implementation-gap` has to cite what shows it.** An unread file is not
  proof of missing functionality, and the absence of a test is not proof that
  the implementation is absent. This is the same rule `outcomes` applies to
  `confirmed-unmet`, at clause scope.
* **An `evidence-gap` has to name what was inspected.** "What I read does not
  establish this" is a claim about a read. With nothing named, the honest kind
  is `inspection-limitation` - nothing was looked at - and the difference is
  exactly the one a reader needs. Naming the sources also scopes the absence
  claim, which is the rule the prose has always stated and nothing enforced.

An `evidence-gap` may also carry `nextRead`: the one file that would settle
it, as `{repo, path, revision}`. Optional, and deliberately not required.
Requiring it would be a checker over model prose whose cheapest escape is a
vaguer next action, which is worse for the reader than the unread file it was
meant to catch. Counting it instead makes specificity something the report
gives credit for - see `follow_up_standing`, which prints how many open gaps
name a target beside how many reads are left unspent, and leaves "0 of 22 name
one" visible rather than quietly satisfied.

What stays judgement: which clauses a criterion has, which source would settle
one, and what a source establishes when read. None of that is here.
"""

from __future__ import annotations

from . import followup as followup_mod

KINDS = ("implementation-gap", "evidence-gap", "inspection-limitation")

LABELS = {
    "implementation-gap": "Implementation gap",
    "evidence-gap": "Evidence gap",
    "inspection-limitation": "Inspection limitation",
}

# Said once, in the rendering, after the clause. The reader has to be able to
# act on the distinction without having read this module.
MEANS = {
    "implementation-gap": "something inspected shows this behaviour missing or contradicted",
    "evidence-gap": "what was inspected does not establish this either way",
    "inspection-limitation": "the evidence that would settle this could not be inspected",
}

# The order the kinds are reported in, worst-understood last - the same
# principle as the outcome columns.
ORDER = ("implementation-gap", "evidence-gap", "inspection-limitation")


def normalize(clause):
    """One clause as a dict, whatever shape it arrived in.

    A bare string is accepted and classified `evidence-gap`, because that is
    what the older schema meant and it is the conservative of the three. It is
    then rejected by `problems` for naming nothing inspected, which is the
    point: the upgrade path is an error message that says what to add, not a
    silent reclassification.
    """
    if isinstance(clause, str):
        return {"text": clause.strip(), "kind": "evidence-gap", "inspected": [], "evidence": [],
                "nextAction": None, "nextRead": None, "limitation": None, "revision": None}
    clause = clause or {}
    return {
        "text": str(clause.get("text") or "").strip(),
        "kind": clause.get("kind") or "evidence-gap",
        "inspected": list(clause.get("inspected") or []),
        "evidence": list(clause.get("evidence") or []),
        "nextAction": (clause.get("nextAction") or "").strip() or None,
        "nextRead": _target(clause.get("nextRead")),
        "limitation": (clause.get("limitation") or "").strip() or None,
        "revision": (clause.get("revision") or "").strip() or None,
    }


def _target(value):
    """`nextRead` as the three fields `source` takes, or None.

    Partial shapes are kept rather than dropped so `problems` can say which
    field is missing. A silently discarded target is a gap that looks
    unresolvable and is not.
    """
    if not isinstance(value, dict):
        return None
    target = {
        field: str(value.get(field) or "").strip() or None
        for field in ("repo", "path", "revision")
    }
    return target if any(target.values()) else None


def target_ref(target):
    """The target as the ref `source` writes it, or None while it is incomplete."""
    if not target or not all(target.get(f) for f in ("repo", "path", "revision")):
        return None
    return followup_mod.source_ref(target["repo"], target["path"], target["revision"])


def open_clauses(requirement):
    """The normalized `uncoveredClauses` of one requirement."""
    return [normalize(clause) for clause in requirement.get("uncoveredClauses") or []]


def problems(requirement, where):
    """Everything refused about this requirement's open clauses."""
    found = []
    for index, raw in enumerate(requirement.get("uncoveredClauses") or [], start=1):
        clause = normalize(raw)
        at = f"{where}: uncovered clause {index}"
        if not clause["text"]:
            found.append(f"{at} has no text. A clause the reader cannot read is not a finding")
            continue
        quoted = clause["text"] if len(clause["text"]) <= 60 else clause["text"][:59] + "…"
        at = f"{where}: {quoted!r}"
        if clause["kind"] not in KINDS:
            found.append(
                f"{at} is classified {clause['kind']!r}, which is not one of {KINDS}. The three "
                "are different findings and go to different people"
            )
            continue
        if clause["kind"] == "implementation-gap" and not clause["evidence"]:
            found.append(
                f"{at} is an implementation gap with nothing cited. It requires affirmative "
                "evidence that the behaviour is missing or contradicted: an unread file is not "
                "proof of missing functionality, and an absent test is not proof of an absent "
                "implementation. Cite what shows it, or classify it 'evidence-gap'"
            )
        if clause["kind"] == "evidence-gap" and not clause["inspected"]:
            found.append(
                f"{at} is an evidence gap naming nothing inspected. 'What was read does not "
                "establish this' is a claim about a read; with nothing named it is an "
                "'inspection-limitation' instead. List the sources you inspected while trying "
                "to settle it, or resolve it with a follow-up read"
            )
        if clause["kind"] == "inspection-limitation" and not clause["limitation"]:
            found.append(
                f"{at} is an inspection limitation with no constraint stated. Say what stopped "
                "the read - access, an unavailable revision, the follow-up budget, or another "
                "named constraint - so the reader knows who can lift it"
            )
        if not clause["nextAction"]:
            found.append(
                f"{at} states no next action. An open clause the reader cannot act on is the "
                "finding this report exists to avoid; say what would settle it"
            )
        found.extend(_target_problems(clause, at))
    return found


def _target_problems(clause, at):
    """`nextRead`, if offered, has to be a target `source` could actually take.

    Shape only. Nothing here requires a target - a clause whose answer nobody
    has located is a real thing and says so by having none. What is refused is
    a target that cannot be used: two fields of three, or a re-read of a file
    this clause already names as inspected, which the follow-up rules exclude
    and which would spend budget to learn nothing.
    """
    target = clause["nextRead"]
    if not target:
        return []
    missing = [field for field in ("repo", "path", "revision") if not target.get(field)]
    if missing:
        return [
            f"{at} names a next read missing {', '.join(missing)}. `source` takes all three; "
            "a target it cannot be given is a sentence, not a target"
        ]
    ref = target_ref(target)
    if ref in clause["inspected"]:
        return [
            f"{at} names {ref} as its next read and already lists it as inspected. A second "
            "read of one file at one revision returns the same bytes; either the clause is "
            "settled by what you have, or the question needs a different file"
        ]
    return []


def follow_up_standing(requirements, budget=None):
    """Open evidence gaps, how many name a file, and how much budget is left.

    Three numbers rather than one, because the dodge the middle number closes
    is the point. "22 open, 5 name a target, 8 reads unspent" says a question
    was left unanswered that could have been answered. "22 open, 0 name a
    target" says no question was ever localized, which is its own finding and
    is exactly what would happen if naming one were made compulsory.
    """
    gaps = [clause for _, clause in by_kind(requirements)["evidence-gap"]]
    targets = [target_ref(clause["nextRead"]) for clause in gaps]
    standing = {
        "openEvidenceGaps": len(gaps),
        "namingATarget": sum(1 for ref in targets if ref),
        "targets": sorted({ref for ref in targets if ref}),
        "limit": (budget or {}).get("limit"),
        "spent": (budget or {}).get("spent"),
        "remaining": (budget or {}).get("remaining"),
    }
    standing["condition"] = _standing_condition(standing)
    return standing


# No gap left open that a read could have closed.
SETTLED = "no-open-evidence-gaps"
# Gaps remain and so does budget: the run stopped before it had to.
READS_UNSPENT = "reads-unspent"
# Gaps remain and the budget does not. Reported because it is the evidence
# for calling what is left an inspection limitation rather than a gap.
BUDGET_SPENT = "budget-spent"
# Gaps remain and nobody knows the budget - a re-render of a snapshot written
# before this was stored. Saying nothing beats guessing at it.
UNKNOWN_BUDGET = "budget-unknown"


def _standing_condition(standing):
    if not standing["openEvidenceGaps"]:
        return SETTLED
    if standing["remaining"] is None:
        return UNKNOWN_BUDGET
    return READS_UNSPENT if standing["remaining"] > 0 else BUDGET_SPENT


def standing_line(standing):
    """One sentence both renderings carry verbatim, or None when there is none.

    Built once and asserted into each output for the same reason the overall
    assessment is: two renderings of the same arithmetic drift on the first
    edit, and the drift is invisible because each still looks right alone.

    A caller that never computed one - a renderer exercised directly on an
    assembly - gets silence rather than a guess.
    """
    if not standing or standing.get("condition") in (None, SETTLED):
        return None
    gaps = standing["openEvidenceGaps"]
    named = standing["namingATarget"]
    opening = (
        f"{gaps} open evidence {'gap' if gaps == 1 else 'gaps'}, "
        f"{named} of which {'names' if named == 1 else 'name'} a file to read"
    )
    if standing["condition"] == UNKNOWN_BUDGET:
        return f"{opening}. The follow-up budget for that run is not recorded."
    left = standing["remaining"]
    if standing["condition"] == BUDGET_SPENT:
        return (
            f"{opening}, and all {standing['limit']} follow-up reads are spent. What is still "
            "open is limited by the budget, not by what was asked."
        )
    return (
        f"{opening}, and {left} of the run's {standing['limit']} follow-up reads "
        f"{'is' if left == 1 else 'are'} unspent."
    )


def standing_notice(standing):
    """What to tell the model before it finalizes, or None if nothing is owed."""
    if not standing or standing.get("condition") != READS_UNSPENT:
        return None
    gaps, named, left = (
        standing["openEvidenceGaps"], standing["namingATarget"], standing["remaining"]
    )
    budget = (
        f"{left} of {standing['limit']} follow-up reads {'is' if left == 1 else 'are'} unspent"
    )
    if not named:
        return (
            f"{gaps} evidence {'gap is' if gaps == 1 else 'gaps are'} open, none of "
            f"{'which' if gaps == 1 else 'them'} names a file to read, and {budget}. A gap "
            "whose answer nobody has located is a different finding from one nobody looked "
            "for: resolve what you can to a path - a PR's changed-file list is in scope and is "
            "how a named subsystem becomes a file - read it, and reassess. What genuinely "
            "cannot be located is an inspection limitation, not a gap."
        )
    return (
        f"{named} of {gaps} open evidence {'gap' if gaps == 1 else 'gaps'} "
        f"{'names' if named == 1 else 'name'} a file to read, and {budget}. Read "
        f"{'it' if named == 1 else 'them'} and reassess before finalizing: a clause left open "
        "over a file nobody opened reports a missing read as missing work."
    )


def by_kind(requirements):
    """Clauses grouped by kind, each tagged with the requirement it came from.

    The grouping the renderings count from, so the full assessment and the
    summary cannot disagree about how many of each there are.
    """
    grouped = {kind: [] for kind in KINDS}
    for requirement in requirements or []:
        for clause in open_clauses(requirement):
            if clause["kind"] in grouped:
                grouped[clause["kind"]].append((requirement, clause))
    return grouped


def counts(requirements):
    return {kind: len(items) for kind, items in by_kind(requirements).items()}


def criteria_with(requirements, kind):
    """Requirements carrying at least one clause of this kind, in input order."""
    found = []
    for requirement in requirements or []:
        if any(clause["kind"] == kind for clause in open_clauses(requirement)):
            found.append(requirement)
    return found


def incomplete(requirements):
    """Criteria whose investigation is explicitly unfinished.

    An inspection limitation is the one kind that says the assessment itself
    is incomplete rather than the work. The report states that in its own
    words rather than leaving a reader to infer it from a clause list.
    """
    return criteria_with(requirements, "inspection-limitation")
