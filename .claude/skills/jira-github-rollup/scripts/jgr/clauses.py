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

What stays judgement: which clauses a criterion has, which source would settle
one, and what a source establishes when read. None of that is here.
"""

from __future__ import annotations

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
                "nextAction": None, "limitation": None, "revision": None}
    clause = clause or {}
    return {
        "text": str(clause.get("text") or "").strip(),
        "kind": clause.get("kind") or "evidence-gap",
        "inspected": list(clause.get("inspected") or []),
        "evidence": list(clause.get("evidence") or []),
        "nextAction": (clause.get("nextAction") or "").strip() or None,
        "limitation": (clause.get("limitation") or "").strip() or None,
        "revision": (clause.get("revision") or "").strip() or None,
    }


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
    return found


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
