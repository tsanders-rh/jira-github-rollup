"""The Jira summary draft: the scannable half of the same assessment.

This is not a shortened report. It is a second rendering of the *same*
structured assessment, and the contract is that a reader cannot find a
classification or a count here that disagrees with the full assessment -
`assemble` checks that rather than trusting it.

What it must not become is a progress bar. The counts are an upstream evidence
assessment, the caption says so, and delivery confidence is computed from
release targets and qualification evidence rather than from how much of the
table is green.

The audience is engineering management, so the bullets carry *narrative* the
model wrote, not a list of criterion ids. Narrative is the only part of either
output that is free text, and it is the part most able to be wrong, so every
claim in it names the assessment rows it rests on and those rows are checked to
exist before anything is rendered. That check proves traceability, not truth:
whether the evidence actually establishes the claim is a judgement, and it
stays with the model.

Three rules keep the prose readable at 49 criteria as well as at 9:

* A criterion is named explicitly in at most one bullet. The second mention is
  a count, because a reader who sees the same eight ids under three headings
  stops reading all three.
* At most `MAX_REFS_PER_BULLET` explicit references per bullet; the remainder
  collapse to counts grouped by the Jira issue that owns them.
* Every reference is qualified with its source key. `AC1` is ambiguous across
  six Jira issues; `RHOAIENG-2201 AC1` is not.
"""

from __future__ import annotations

import re

from . import clauses as clauses_mod
from . import links as links_mod
from . import outcomes as outcomes_mod
from . import util

# The budget covers the whole draft, including the overall assessment. It was
# 150-250 when the draft was four bullets; a required 60-100 word paragraph in
# front of them moves the whole range rather than squeezing the bullets.
WORD_FLOOR = 210
WORD_CEILING = 350

# What the budget came out as, named rather than left as a boolean.
#
# The distinction that matters is not "did it fit" but "can anything here make
# it fit", and the answer to the second is no. Nothing in this module shortens
# model prose, and the one lever it does have - naming fewer criteria per
# bullet - is worth a handful of words at any scale, because the collapsed
# tail that replaces a name is about as long as the name. So `over-ceiling` is
# a condition the model has to act on by rewriting, and it is reported where
# the person about to approve the draft will see it rather than only in a
# field of `result.json`.
WITHIN_BUDGET = "within-budget"
UNDER_FLOOR = "under-floor"
OVER_CEILING = "over-ceiling"

# The overall assessment paragraph. Reported rather than enforced, like the
# draft budget: truncating the model's prose to hit a number would damage the
# one part of the document that carries the position.
OVERALL_FLOOR = 60
OVERALL_CEILING = 100

# At most this many artifact links per bullet. The brief asks for targeted
# links, and a bullet carrying six of them is an inventory, not a pointer -
# the full inventory lives in the detailed assessment.
LINKS_PER_BULLET = 2

# At most this many explicit criterion references per bullet. Past three the
# enumeration stops being a pointer and starts being the content, which is the
# thing the narrative is there to replace.
MAX_REFS_PER_BULLET = 3

# The four bullets, in order. The slug is what `assembly["narrative"]` tags a
# claim with; the label is what the reader sees.
BULLETS = (
    ("evidence-established", "Evidence established"),
    ("remaining-work", "Remaining work"),
    ("decisions-needed", "Decisions needed"),
    ("next-actions", "Next actions"),
)
BULLET_SLUGS = tuple(slug for slug, _ in BULLETS)

# What a claim should point at, strongest first. Which order applies depends on
# what is being claimed, and getting this backwards produces a link that argues
# against its own sentence.
#
#   For a met or partly-met criterion: the artifact that landed the work.
#   For anything else: the issue that *owns* the work. A merged PR attached to
#   "SC5 in progress" reads as though SC5 shipped, and the one merged PR in a
#   criterion's evidence is often the least relevant thing in it.
_SUPPORTING = {("pr", "merged"): 0, ("issue", "closed"): 1, ("pr", "open"): 2,
               ("pr", "draft"): 3, ("issue", "open"): 4}
_OWNING = {("issue", "open"): 0, ("pr", "open"): 1, ("pr", "draft"): 2,
           ("issue", "closed"): 3, ("pr", "merged"): 4}


def _rank(item, table):
    return table.get(((item.get("kind") or "").lower(), (item.get("state") or "").lower()), 9)


def strongest(requirement, limit=2, supporting=None):
    """The artifact a claim about this criterion should point at."""
    if supporting is None:
        supporting = outcomes_mod.classify(requirement) in ("met", "partial")
    table = _SUPPORTING if supporting else _OWNING
    evidence = sorted(requirement.get("evidence") or [], key=lambda item: _rank(item, table))
    return evidence[:limit]


def evidence_links(requirement, limit=2, supporting=None):
    return [
        links_mod.describe(item.get("ref"), item.get("kind"))
        for item in strongest(requirement, limit, supporting)
        if item.get("ref")
    ]


def refuting_links(requirement, limit=2):
    """What a `confirmed-unmet` claim points at: the thing that refutes it.

    `refutingEvidence` first, because that is the artifact the claim was made
    on. Falling back to `evidence` rather than going silent - the assembler
    accepts either as the citation, so the summary has to render either.
    """
    items = requirement.get("refutingEvidence") or requirement.get("evidence") or []
    return [
        links_mod.describe(item.get("ref"), item.get("kind"))
        for item in items[:limit]
        if item.get("ref")
    ]


def _id_key(requirement):
    """Sort SC9 before SC10, and keep criteria from one Jira together."""
    text = str(requirement.get("id") or "")
    match = re.match(r"^([A-Za-z]*)(\d*)", text)
    return (requirement.get("sourceKey") or "", match.group(1), int(match.group(2) or 0), text)


def _ordered(requirements):
    return sorted(requirements, key=_id_key)


def qualified(requirement):
    """`RHOAIENG-2201 AC1`. Never a bare `AC1`: six Jira issues here have one."""
    key = requirement.get("sourceKey")
    return f"{key} {requirement.get('id')}" if key else str(requirement.get("id"))


def criterion_ref(requirement, site=None):
    """How a criterion is pointed at when it has no anchor of its own."""
    return links_mod.jira_link(
        requirement.get("sourceKey"), site=site, criterion=requirement.get("id")
    )


def counts_by_source(requirements):
    """`4 on RHOAIENG-2202, 3 on RHOAIENG-2203` - the tail of a collapsed enumeration."""
    groups = {}
    for requirement in requirements:
        groups.setdefault(requirement.get("sourceKey") or "an unrecorded issue", 0)
        groups[requirement.get("sourceKey") or "an unrecorded issue"] += 1
    return ", ".join(f"{count} on {key}" for key, count in sorted(groups.items()))


def crit(count):
    return util.pluralize(count, "criterion", "criteria")


def word_count(text):
    """Words, excluding URLs and the outcome table.

    The budget is about how much a reader has to read. A URL is not read, and
    the table is scanned rather than read, so neither is counted - which is
    what the brief asks for and also the only way the number means anything.
    """
    stripped = re.sub(r"\]\([^)]*\)", "]", text or "")
    stripped = re.sub(r"https?://\S+", "", stripped)
    stripped = "\n".join(
        line for line in stripped.splitlines() if not line.lstrip().startswith("|")
    )
    return len(re.findall(r"[A-Za-z0-9][\w'’/#.-]*", stripped))


def _group(requirements):
    grouped = {name: [] for name in outcomes_mod.OUTCOMES}
    for requirement in requirements or []:
        grouped[outcomes_mod.classify(requirement)].append(requirement)
    return grouped


class _Ledger:
    """Names each criterion once across the whole summary, counts it after.

    The duplication this prevents is not cosmetic. The same eight ids under
    "Remaining work" and again under "Next actions" reads as sixteen problems,
    and the bullet that was supposed to say what to *do* says nothing a reader
    did not already have.
    """

    def __init__(self, site=None, limit=MAX_REFS_PER_BULLET):
        self.site = site
        self.limit = limit
        self.named = set()

    @staticmethod
    def _identity(requirement):
        return (requirement.get("sourceKey"), requirement.get("id"))

    def refs(self, requirements, link=True):
        """Up to `limit` explicit qualified references, the rest as counts."""
        ordered = _ordered(requirements)
        if not ordered:
            return ""
        unnamed = [r for r in ordered if self._identity(r) not in self.named]
        shown = unnamed[: self.limit]
        shown_ids = {self._identity(r) for r in shown}
        for requirement in shown:
            self.named.add(self._identity(requirement))
        rest = [r for r in ordered if self._identity(r) not in shown_ids]

        head = ", ".join(
            (criterion_ref(r, self.site) if link else qualified(r)) for r in shown
        )
        if not rest:
            return head
        # No parentheses in the tail: the whole suffix is already parenthesised
        # by the caller, and nested brackets are the one thing that makes a
        # collapsed enumeration harder to read than the list it replaced.
        breakdown = counts_by_source(rest)
        if head:
            return f"{head}, and {len(rest)} more — {breakdown}"
        # Nothing new to name - every criterion here was named by an earlier
        # bullet - so "more" has no antecedent and the count stands alone. A
        # single-source breakdown is already that count, and printing both
        # gives "1 criterion - 1 on RHOAIENG-7001".
        if len({r.get("sourceKey") or "an unrecorded issue" for r in rest}) == 1:
            return breakdown
        return f"{crit(len(rest))} — {breakdown}"


class _Budget:
    """Hands out at most `LINKS_PER_BULLET` artifact links, then goes quiet.

    Counting rather than slicing, because the links are spread across several
    clauses of one bullet and the cap is on the bullet.
    """

    def __init__(self, limit=LINKS_PER_BULLET):
        self.left = limit

    def spend(self, requirement, refuting=False):
        if self.left <= 0:
            return ""
        pointers = refuting_links(requirement, 1) if refuting else evidence_links(requirement, 1)
        if not pointers:
            return ""
        self.left -= 1
        return f" ({pointers[0]})"


# --- narrative -----------------------------------------------------------


def _requirement_index(requirements):
    return {(r.get("sourceKey"), r.get("id")): r for r in requirements or []}


def narrative_problems(narrative, requirements):
    """Structural checks on model prose. Not a check that the prose is true.

    What is verifiable here is that every claim is attached to rows that exist,
    that each cited link is carried by one of those rows, and that a claim filed
    under "Evidence established" does not rest on a row nothing supports. Those
    are the ways a narrative can be untraceable. Whether the evidence actually
    establishes what the sentence says is a judgement and is not checked.
    """
    index = _requirement_index(requirements)
    problems = []
    for position, entry in enumerate(narrative or [], start=1):
        where = f"narrative claim {position}"
        if not isinstance(entry, dict):
            problems.append(f"{where}: expected an object, got {type(entry).__name__}")
            continue
        slug = entry.get("bullet")
        if slug not in BULLET_SLUGS:
            problems.append(f"{where}: bullet {slug!r} is not one of {BULLET_SLUGS}")
        if not str(entry.get("text") or "").strip():
            problems.append(f"{where}: has no text")

        cited = []
        for ref in entry.get("refs") or []:
            identity = (ref.get("sourceKey"), ref.get("id")) if isinstance(ref, dict) else (None, ref)
            requirement = index.get(identity)
            if requirement is None:
                problems.append(
                    f"{where}: cites {identity[1]!r} on {identity[0]!r}, which is not an "
                    "assessed requirement in this run"
                )
                continue
            cited.append(requirement)
        if not cited and not problems[-1:]:
            problems.append(
                f"{where}: cites no assessment row. Every substantive claim has to name the "
                "rows it rests on"
            )

        if slug == "evidence-established":
            unsupported = [
                qualified(r) for r in cited if outcomes_mod.classify(r) == "unverified"
            ]
            if unsupported:
                problems.append(
                    f"{where}: filed under 'Evidence established' but rests on "
                    + ", ".join(unsupported)
                    + ", which nothing inspected supports. An unverified row cannot "
                    "establish a capability"
                )

        carried = {
            item.get("ref")
            for requirement in cited
            for item in (requirement.get("evidence") or [])
            + (requirement.get("refutingEvidence") or [])
        }
        for link in entry.get("links") or []:
            if link not in carried:
                problems.append(
                    f"{where}: links {link}, which is not evidence on any row it cites"
                )
    return problems


def _claim_suffix(entry, requirements, ledger, budget):
    """The traceability tail on one narrative sentence: rows, then links."""
    index = _requirement_index(requirements)
    cited = [
        index[(ref.get("sourceKey"), ref.get("id"))]
        for ref in entry.get("refs") or []
        if isinstance(ref, dict) and (ref.get("sourceKey"), ref.get("id")) in index
    ]
    parts = []
    refs = ledger.refs(cited)
    if refs:
        parts.append(refs)
    for link in (entry.get("links") or [])[:LINKS_PER_BULLET]:
        if budget.left <= 0:
            break
        budget.left -= 1
        parts.append(links_mod.describe(link, _kind_of(link, cited)))
    return f" ({'; '.join(parts)})" if parts else ""


def _kind_of(ref, requirements):
    for requirement in requirements:
        for item in (requirement.get("evidence") or []) + (
            requirement.get("refutingEvidence") or []
        ):
            if item.get("ref") == ref:
                return item.get("kind")
    return None


def _narrative_bullet(slug, narrative, requirements, ledger):
    entries = [e for e in narrative or [] if isinstance(e, dict) and e.get("bullet") == slug]
    if not entries:
        return None
    budget = _Budget()
    sentences = []
    for entry in entries:
        text = str(entry.get("text") or "").strip().rstrip(".")
        sentences.append(text + _claim_suffix(entry, requirements, ledger, budget) + ".")
    return " ".join(sentences)


# --- overall assessment --------------------------------------------------
#
# One paragraph saying where the requirement stands, so a reader does not have
# to assemble that from the rows themselves. It is the model's judgement and
# stays the model's judgement; what is checked here is that the judgement is
# pinned to rows that can carry it.
#
# The three ref lists are the reason this is checkable at all. "The evidence
# establishes it", "something inspected contradicts it" and "nothing inspected
# settles it" are the distinctions the whole report exists to keep apart, and
# free prose is exactly where they collapse into each other. Each list is
# checked against the outcome its rows actually have, so a paragraph can be
# wrong about what the evidence *means* - that is judgement - but it cannot be
# wrong about which bucket a row is in.

OVERALL_REF_FIELDS = (
    (
        "establishes",
        ("met", "partial"),
        "nothing inspected supports it, so it cannot be what the evidence establishes",
    ),
    (
        "unmet",
        ("confirmed-unmet",),
        "a confirmed absence is a row something inspected contradicts. A row nothing "
        "covers is missing evidence and belongs under `unverified`",
    ),
    (
        "unverified",
        ("unverified",),
        "the evidence supports it, so it is not unverified",
    ),
)
OVERALL_FIELDS = tuple(name for name, _, _ in OVERALL_REF_FIELDS)

# A percentage in this paragraph is always one of two things: criterion counts
# restated as completion, or a figure nothing in the pipeline computed. The
# ratios live in the full assessment with the caption that scopes them.
_PERCENTAGE = re.compile(r"\d\s*%|\bpercent(?:age)?\b", re.I)

# Readiness and schedule language. Nothing inspected here establishes any of
# it: the pipeline reads issues and pull requests, which say what was built,
# never when something ships or who committed to it.
_FORECAST = re.compile(
    r"(?ix)\b(?: on \s+ track | release[- ]ready | ready \s+ (?:for|to) \s+ (?:release|ship|GA)"
    r" | will \s+ (?:ship|land|complete|be \s+ (?:done|complete|ready))"
    r" | expected \s+ (?:by|in) | due \s+ (?:by|in) | ETA | by \s+ (?:Q[1-4]|end \s+ of))\b"
)


def _criterion_ids(requirements):
    """Ids distinctive enough to recognise in prose. `AC1`, never a bare `1`."""
    found = set()
    for requirement in requirements or []:
        identifier = str(requirement.get("id") or "").strip()
        if len(identifier) > 1 and re.search(r"[A-Za-z]", identifier):
            found.add(identifier)
    return found


def overall_problems(overall, requirements):
    """Structural checks on the overall assessment. Not a check that it is true.

    Four things are verifiable: the rows it rests on exist, each is in the
    bucket the paragraph files it under, every cited link is carried by one of
    those rows, and the prose stays inside what this pipeline can observe.
    Whether the paragraph characterises the work correctly is judgement and is
    not checked here.
    """
    if overall is None:
        return []
    if not isinstance(overall, dict):
        return [f"the overall assessment: expected an object, got {type(overall).__name__}"]

    where = "the overall assessment"
    body = str(overall.get("text") or "").strip()
    if not body:
        return [f"{where}: has no text"]

    index = _requirement_index(requirements)
    problems = []
    cited = []
    for field, allowed, why in OVERALL_REF_FIELDS:
        for ref in overall.get(field) or []:
            identity = (ref.get("sourceKey"), ref.get("id")) if isinstance(ref, dict) else (None, ref)
            requirement = index.get(identity)
            if requirement is None:
                problems.append(
                    f"{where}: {field} cites {identity[1]!r} on {identity[0]!r}, which is not "
                    "an assessed requirement in this run"
                )
                continue
            cited.append(requirement)
            outcome = outcomes_mod.classify(requirement)
            if outcome not in allowed:
                problems.append(
                    f"{where}: {qualified(requirement)} is filed under {field!r} but is "
                    f"{outcomes_mod.ROW_LABELS[outcome].lower()} — {why}"
                )

    if not cited:
        problems.append(
            f"{where}: names no assessment row. The paragraph has to be attached to the rows "
            f"it is drawn from, under {', '.join(OVERALL_FIELDS)}"
        )

    carried = {
        item.get("ref")
        for requirement in cited
        for item in (requirement.get("evidence") or [])
        + (requirement.get("refutingEvidence") or [])
    }
    for link in overall.get("links") or []:
        if link not in carried:
            problems.append(f"{where}: links {link}, which is not evidence on any row it names")

    named = sorted(identifier for identifier in _criterion_ids(requirements)
                   if re.search(rf"\b{re.escape(identifier)}\b", body))
    if named:
        problems.append(
            f"{where}: names {', '.join(named)}. The paragraph groups criteria into capability "
            "areas; the per-criterion enumeration is the bullets' job and the table's"
        )
    if _PERCENTAGE.search(body):
        problems.append(
            f"{where}: carries a percentage. Criterion counts are an upstream evidence "
            "assessment, not completion, and the ratios belong in the full assessment where "
            "the caption scopes them"
        )
    forecast = _FORECAST.search(body)
    if forecast:
        problems.append(
            f"{where}: {forecast.group(0).strip()!r} claims readiness or a date. Nothing this "
            "run inspects establishes either"
        )
    return problems


_TYPE_AREA = {
    "AC": "acceptance criteria",
    "SC": "success criteria",
    "DoD": "definition-of-done items",
}


def capability_areas(requirements):
    """Criteria grouped the way a reader thinks about them, not by id.

    `heading` is the section the criterion was quoted from, which is the
    closest thing the source gives to a capability name. With none, the type is
    the honest fallback: it says what kind of commitment the row is and claims
    nothing about what it covers.
    """
    areas = {}
    for requirement in requirements or []:
        name = (requirement.get("heading") or "").strip() or _TYPE_AREA.get(
            requirement.get("type"), "other criteria"
        )
        areas.setdefault(name, []).append(requirement)
    return areas


def _area_names(requirements, limit=3):
    areas = capability_areas(requirements)
    names = sorted(areas, key=lambda name: (-len(areas[name]), name))
    shown = names[:limit]
    rest = len(names) - len(shown)
    if len(shown) > 1 and not rest:
        listed = ", ".join(shown[:-1]) + " and " + shown[-1]
    else:
        listed = ", ".join(shown)
    return listed + (f", and {rest} more" if rest else "")


def overall_fallback(requirements, tallied):
    """The paragraph when the model wrote none. Says less, and is never wrong.

    Every sentence here is a restatement of the tally in words, with the
    capability areas named so the reader gets more than the table already
    gives. It deliberately reaches no conclusion about what the work means -
    that is the judgement nobody supplied.
    """
    grouped = _group(requirements)
    counts = tallied["counts"]
    total = tallied["total"]
    supported = grouped["met"] + grouped["partial"]

    # Named only when there is more than one, because with a single area the
    # name is the requirement type, the Scope line already gives it, and
    # "1 criterion in acceptance criteria" is a worse sentence than "1
    # criterion".
    multiple = len(capability_areas(requirements)) > 1

    def area(subset, lead, limit=3):
        return f" {lead} {_area_names(subset, limit)}" if multiple else ""

    sentences = []
    if supported:
        sentences.append(
            f"Of {crit(total)}, inspected upstream evidence fully supports {counts['met']} and "
            f"partly supports {counts['partial']}{area(supported, 'across')}"
        )
    else:
        sentences.append(
            f"Nothing inspected upstream supports any of the {crit(total)}"
            f"{area(requirements, 'across')}"
        )
    if grouped["confirmed-unmet"]:
        sentences.append(
            f"{crit(counts['confirmed-unmet']).capitalize()}"
            f"{area(grouped['confirmed-unmet'], 'in', 2)} "
            f"{'is' if counts['confirmed-unmet'] == 1 else 'are'} contradicted by something "
            "inspected, which is a finding rather than a gap in the reading"
        )
    if grouped["unverified"]:
        sentences.append(
            f"{crit(counts['unverified']).capitalize()} "
            f"{'is' if counts['unverified'] == 1 else 'are'} unverified in the traversed set"
            f"{area(grouped['unverified'], 'mostly in', 2)}; that is absent evidence, not "
            "established absence"
        )
    sentences.append(
        "Resolving those needs the owning upstream work linked and downstream qualification "
        "cited. No overall position was written for this run, so none is claimed here beyond "
        "what the rows say"
    )
    return ". ".join(sentences) + "."


def overall_text(assembly, requirements, tallied):
    """The paragraph both renderings carry, model-written or mechanical."""
    overall = assembly.get("overall")
    if isinstance(overall, dict):
        body = str(overall.get("text") or "").strip()
        if body:
            return body
    return overall_fallback(requirements, tallied)


# --- mechanical fallbacks ------------------------------------------------
#
# Used when the model supplied no narrative for a bullet. They say less than
# prose would, and they are never wrong, which is the right trade for a bullet
# nobody wrote.


def _established(grouped, ledger):
    items = _ordered(grouped["met"] + grouped["partial"])
    if not items:
        return "No criterion is yet supported by landed upstream evidence in the sources inspected."
    met, partial = grouped["met"], grouped["partial"]
    clauses = []
    if met:
        clauses.append(f"{len(met)} fully supported: {ledger.refs(met)}")
    if partial:
        clauses.append(f"{len(partial)} partly supported: {ledger.refs(partial)}")
    return "; ".join(clauses) + "."


def _remaining(grouped, ledger):
    """Implementation or qualification work that is identified and outstanding.

    `confirmed-unmet` is deliberately not here. "Tracked and incomplete" is the
    right sentence for work still in flight and the wrong one for a criterion
    something was found to violate; it reads as a schedule item rather than a
    finding. Those go to Decisions needed, which is where a reader looks for
    things that change a decision.
    """
    tracked = [r for r in grouped["unverified"] if r.get("evidence")]
    untracked = [r for r in grouped["unverified"] if not r.get("evidence")]
    uncovered = [r for r in grouped["partial"] if r.get("uncoveredClauses")]
    clauses = []
    if uncovered:
        clauses.append(
            f"{crit(len(uncovered))} {'holds' if len(uncovered) == 1 else 'hold'} in part only, "
            # Not "nothing inspected supports it": an inspection limitation is
            # a clause nothing was inspected *for*, which is the opposite
            # claim. The kinds below say which of the two it is.
            f"with at least one clause still open: {ledger.refs(uncovered)}"
            # Counts only, and no second list of ids: the distinction between
            # "the code is missing it" and "we could not read what would say"
            # changes who acts, and is worth a clause here; repeating which
            # criteria they are would make this bullet the coverage table.
            + _kind_tail(uncovered)
        )
    if tracked:
        clauses.append(f"{crit(len(tracked))} tracked and incomplete: {ledger.refs(tracked)}")
    if untracked:
        clauses.append(
            f"{crit(len(untracked))} {'has' if len(untracked) == 1 else 'have'} no upstream "
            f"work in the traversed set: {ledger.refs(untracked)}"
        )
    if not clauses:
        return "No outstanding upstream work was identified in the sources inspected."
    return "; ".join(clauses) + "."


def _kind_tail(requirements):
    """Why those clauses are open, as counts. No ids; the full assessment has them.

    The material distinction the draft has to carry. Three criteria "partly
    covered" is one sentence to a reader whether the missing part is a bug, an
    unlinked repo, or a file nobody could open - and those are three different
    meetings.
    """
    counted = clauses_mod.counts(requirements)
    parts = []
    for kind in clauses_mod.ORDER:
        if counted[kind]:
            label = clauses_mod.LABELS[kind].lower()
            parts.append(util.pluralize(counted[kind], label, label + "s"))
    if not parts:
        return ""
    return " (" + ", ".join(parts) + ")"


def _clause_phrase(requirement):
    """The open decision itself, not the fact that one exists.

    "A decision is open on SC3" sends the reader back to the full assessment to
    find out which. Naming the clause is the difference between an item they
    can act on and an item they have to research first.
    """
    clauses = [str(c).strip() for c in requirement.get("unresolvedClauses") or [] if str(c).strip()]
    if not clauses:
        return ""
    first = clauses[0]
    if len(first) > 90:
        first = first[:89].rsplit(" ", 1)[0] + "…"
    return f" — {first}" + (f" (and {len(clauses) - 1} more)" if len(clauses) > 1 else "")


def _decisions(grouped, requirements, ledger):
    """Findings and open questions, each stated as the question it raises.

    A `confirmed-unmet` row is deliberately *not* turned into "reopen the work
    or revise the criterion". That phrasing picks one of two answers before
    anyone has asked the question, and the question - does the criterion still
    describe what we intend to ship - is the thing a reader can actually answer.
    """
    refuted = _ordered(grouped["confirmed-unmet"])
    open_decisions = _ordered([r for r in requirements or [] if r.get("unresolvedClauses")])

    budget, parts = _Budget(), []
    if refuted:
        pointer = budget.spend(refuted[0], refuting=True)
        parts.append(
            f"{crit(len(refuted))} {'is' if len(refuted) == 1 else 'are'} contradicted by "
            f"something inspected rather than merely unevidenced ({ledger.refs(refuted)})"
            f"{pointer} — confirm whether each still describes intended behaviour before any "
            "work is scheduled against it"
        )
    for requirement in open_decisions[: MAX_REFS_PER_BULLET]:
        parts.append(
            f"a decision is open on {ledger.refs([requirement])}"
            f"{_clause_phrase(requirement)}{budget.spend(requirement)}"
        )
    extra = open_decisions[MAX_REFS_PER_BULLET:]
    if extra:
        parts.append(f"{len(extra)} further open decisions ({counts_by_source(extra)})")
    if not parts:
        return "None identified beyond the work listed above."
    return "; ".join(parts) + "."


def _next(grouped, requirements, ledger):
    """Concrete actions. Owners and dates appear only where a source established one."""
    untracked = [r for r in grouped["unverified"] if not r.get("evidence")]
    open_decisions = [r for r in requirements or [] if r.get("unresolvedClauses")]
    pending = [
        r
        for r in grouped["met"] + grouped["partial"]
        if ((r.get("downstream") or {}).get("state") or "unknown") != "confirmed"
    ]
    actions = []
    if grouped["confirmed-unmet"]:
        actions.append(
            f"review the {crit(len(grouped['confirmed-unmet']))} contradicted by inspected "
            "evidence with the requirement owner and record whether each stands as written"
        )
    if untracked:
        actions.append(
            f"identify and link the owning upstream work for {crit(len(untracked))} "
            f"({counts_by_source(untracked)})"
        )
    if open_decisions:
        actions.append(f"record the open decisions on {ledger.refs(open_decisions)}")
    # Before the downstream action, because it is an action on the assessment
    # rather than on the work: until it is done, nobody knows whether the
    # clause under it is a gap at all.
    blocked = clauses_mod.incomplete(requirements)
    if blocked:
        actions.append(
            # No internal semicolon: the actions are joined with one, and a
            # second clause here would read as a separate action.
            f"finish the inspection on {crit(len(blocked))} where a named source could not "
            "be read, leaving those clauses unresolved rather than negative"
        )
    if pending:
        actions.append(
            f"run or cite downstream qualification for the {crit(len(pending))} that upstream "
            "evidence supports"
        )
    if not actions:
        return "No action identified from the sources inspected."
    return (
        "; ".join(actions)
        + ". No owner or date for these is recorded in the sources inspected."
    )


# --- trend ---------------------------------------------------------------


def trend_line(assembly, tallied):
    """One sentence of movement since the previous comparable snapshot.

    "Comparable" is the load-bearing word. If the criteria set or the collection
    scope changed, the two tallies are not measuring the same thing, and the
    line says that instead of printing a delta that would read as progress.
    """
    diff = assembly.get("diff") or {}
    baseline = diff.get("baseline")
    snapshot = assembly.get("baselineSnapshot") or {}
    if not baseline or not snapshot.get("requirements"):
        return "Baseline established."

    before = outcomes_mod.tally(snapshot["requirements"])
    when = util.date_only(baseline.get("generatedAt"))
    # "Draft snapshot" is this tool's vocabulary, not the reader's, and the two
    # baselines answer different questions: movement since the last thing posted
    # here, or movement since the last time anyone assessed. Say which.
    kind = (
        f"last update posted here on {when}"
        if baseline.get("publication") == "published"
        else f"last assessment on {when}, which was not posted here"
    )

    changes = diff.get("requirementChanges") or {}
    added, removed = changes.get("added") or [], changes.get("removed") or []
    scope_changed = bool(added or removed or changes.get("textChanged"))
    inventory = diff.get("inventoryChanges") or {}
    access_changed = bool(inventory.get("accessLost") or inventory.get("accessRestored"))

    # A criteria set that grew makes the four raw counts incomparable, and
    # printing "unverified 4→21" beside "since the last assessment" reads as
    # twenty-one things going wrong. Report the scope change instead, and leave
    # the like-for-like movement to the full assessment, which has room to
    # qualify it.
    if before["total"] != tallied["total"]:
        parts = []
        if added:
            parts.append(f"{crit(len(added))} added")
        if removed:
            parts.append(f"{len(removed)} removed")
        detail = ", ".join(parts) or "the criteria set changed"
        return (
            f"Since the {kind}, {detail} ({before['total']}→{tallied['total']}). The outcome "
            "counts are not comparable across a scope change and no movement is claimed from "
            "them; the full assessment reports movement over the criteria present in both runs."
        )

    moved = [
        f"{outcomes_mod.LABELS[name].lower()} {before['counts'][name]}→{tallied['counts'][name]}"
        for name in outcomes_mod.OUTCOMES
        if before["counts"][name] != tallied["counts"][name]
    ]
    body = (
        f"no outcome changed since the {kind}"
        if not moved
        else f"since the {kind}, " + ", ".join(moved)
    )

    notes = []
    if scope_changed:
        notes.append("criterion text changed, so these are not like-for-like")
    if access_changed:
        notes.append(
            "source access changed this run, so some movement is newly visible rather than newly done"
        )
    return body + (". " + "; ".join(notes).capitalize() + "." if notes else ".")


def _scope_caveat(manifest):
    """Collection limits, stated wherever one materially affects the assessment.

    Prominent rather than tucked away: a rollup that silently omits a branch of
    the tree reads as a complete picture, and every "no evidence found" row in
    it inherits the omission.
    """
    inaccessible = [a for a in manifest.get("access") or [] if a.get("status") != "readable"]
    clauses = []
    if inaccessible:
        refs = ", ".join(a.get("ref", "?") for a in inaccessible[:3])
        clauses.append(
            f"{util.pluralize(len(inaccessible), 'source')} could not be read ({refs})"
        )
    # Only the structured list. This used to fall back to counting traversal
    # notes that mentioned "nested epic", which cannot tell a branch that was
    # traversed from one that was not - and now that some are traversed, that
    # fallback would report covered work as a gap.
    untraversed = manifest.get("untraversed") or []
    if untraversed:
        refs = ", ".join(links_mod.link(entry.get("ref")) for entry in untraversed[:3])
        clauses.append(
            f"{util.pluralize(len(untraversed), 'nested epic')} "
            f"{'was' if len(untraversed) == 1 else 'were'} recorded but not traversed ({refs})"
        )
    if not manifest.get("traversalComplete", True):
        clauses.append("traversal did not complete")
    if not clauses:
        return None
    return (
        "**Scope:** " + "; ".join(clauses) + ". Criteria owned by that work would not appear "
        "here, so an unverified row is not evidence that the work is missing."
    )


def _mix_line(requirements):
    """AC, SC and DoD counted and named separately, never summed into one number."""
    from . import render as render_mod  # imported late: render imports this module

    counts = render_mod.type_counts(requirements or [])
    if not counts:
        return None
    return f"_Scope: {render_mod.describe_mix(counts)}, counted separately._"


# --- top level -----------------------------------------------------------


def render(assembly, tallied, confidence, trend=None, full_assessment_url=None):
    """The Jira summary draft, as Markdown. See `draft` for what it came out at."""
    return draft(assembly, tallied, confidence, trend, full_assessment_url)["text"]


def draft(assembly, tallied, confidence, trend=None, full_assessment_url=None):
    """The Jira summary draft, and what the word budget came out as.

    `full_assessment_url` is included only when the caller can name a durable,
    reader-accessible location. A local path is not one, and `links.py`
    refuses it.

    The budget is reported, never met by force. This used to re-render the
    whole document at three, two and one reference per bullet hoping one of
    them would fit; measured on a 49-criterion draft the three versions span
    four words, and the one-reference version is the *longest* of them,
    because "and 9 more - 4 on RHOAIENG-2204, 3 on RHOAIENG-2205" costs more
    than the two names it replaced. The cap is a readability rule and is
    applied once as one. What makes a draft long is the prose, and shortening
    that is the model's judgement; what this returns is the fact that it has
    to.
    """
    trend = trend or trend_line(assembly, tallied)
    jira = assembly.get("jira") or {}
    site = jira.get("site")
    manifest = assembly.get("manifest") or {}
    requirements = assembly.get("requirements") or []
    narrative = assembly.get("narrative") or []
    grouped = _group(requirements)
    mappings = assembly.get("mappings") or []

    name = jira.get("summary") or jira.get("key")
    title = f"### {name} — Upstream rollup"

    source = (
        ", ".join(links_mod.epic_link(m) for m in mappings)
        if mappings
        else "No upstream epic is linked on this issue."
    )
    confidence_line = f"**Delivery confidence:** {confidence['value']}"
    if confidence.get("reason"):
        confidence_line += f" — {confidence['reason']}"

    counts = tallied["counts"]
    table = [
        "| " + " | ".join(outcomes_mod.LABELS[name] for name in outcomes_mod.OUTCOMES) + " |",
        "| " + " | ".join("---" for _ in outcomes_mod.OUTCOMES) + " |",
        "| " + " | ".join(str(counts[name]) for name in outcomes_mod.OUTCOMES) + " |",
    ]

    # Never drops a bullet outright - a summary missing "Decisions needed" is
    # a different document, not a shorter one - and never truncates narrative:
    # it is the model's claim, and a half-sentence claim is worse than a long
    # one.
    overall = overall_text(assembly, requirements, tallied)

    ledger = _Ledger(site, limit=MAX_REFS_PER_BULLET)
    bullets = []
    for slug, label in BULLETS:
        text = _narrative_bullet(slug, narrative, requirements, ledger)
        if text is None:
            text = _FALLBACK[slug](grouped, requirements, ledger)
        bullets.append(f"- **{label}:** {text}")
    body = _assemble(
        title, source, confidence_line, tallied, table, bullets,
        assembly, trend, manifest, requirements, full_assessment_url, overall,
    )

    words = word_count(body)
    condition = budget_condition(words)
    return {
        "text": body,
        "words": words,
        "floor": WORD_FLOOR,
        "ceiling": WORD_CEILING,
        # Kept beside `condition` because callers and a stored `result.json`
        # already read it, and derived from it so the two cannot disagree.
        "within": condition == WITHIN_BUDGET,
        "condition": condition,
        "refsPerBullet": MAX_REFS_PER_BULLET,
        # Split out because it is the half the model can do something about,
        # and because "the draft is long" and "what you wrote is long" lead to
        # different next moves.
        "authored": {
            "narrative": word_count(
                " ".join(
                    str(entry.get("text") or "")
                    for entry in narrative
                    if isinstance(entry, dict) and entry.get("bullet") in BULLET_SLUGS
                )
            ),
            "overall": word_count(overall),
        },
    }


def budget_condition(words):
    """Which of the three the draft is. `over-ceiling` is the one to act on."""
    if words > WORD_CEILING:
        return OVER_CEILING
    if words < WORD_FLOOR:
        return UNDER_FLOOR
    return WITHIN_BUDGET


def budget_notice(state):
    """What to tell the person about to approve an over-budget draft, or None.

    Only the ceiling gets a notice. Under the floor usually means the bullets
    are a list of ids rather than a status, which a reader can see for
    themselves in the draft in front of them; over the ceiling is the one that
    is invisible at a glance and that nothing downstream will fix.
    """
    if state.get("condition") != OVER_CEILING:
        return None
    authored = state.get("authored") or {}
    narrative = authored.get("narrative") or 0
    overall = authored.get("overall") or 0
    # Everything the renderer owns: the header lines, the caption, the
    # collapsed reference suffixes, the trend and the scope caveat. Derived
    # rather than stated as a constant because it grows with the run, and the
    # number the model needs is how much room is left in *this* draft.
    fixed = max(state.get("words", 0) - narrative - overall, 0)
    room = WORD_CEILING - overall - fixed
    notice = (
        f"the Jira summary draft is {state['words']} words against a {WORD_CEILING}-word "
        f"ceiling. Nothing here can shorten it: a claim is never truncated, and naming "
        f"fewer criteria per bullet is worth a handful of words. The four bullets are "
        f"{narrative} words of your prose; beside an overall assessment of {overall} and "
        f"{fixed} words of header, trend and reference lines, they have "
    )
    notice += (
        f"{room} to work with. "
        if room > 0
        else "nothing to work with - the overall assessment and the fixed lines fill the "
             "ceiling on their own, so shorten the overall assessment too. "
    )
    return notice + (
        "Rewrite them and assemble again before showing the draft for approval. At this "
        "scale a bullet gives the shape of the finding and sends the reader to the full "
        "assessment rather than enumerating it."
    )


_FALLBACK = {
    "evidence-established": lambda grouped, requirements, ledger: _established(grouped, ledger),
    "remaining-work": lambda grouped, requirements, ledger: _remaining(grouped, ledger),
    "decisions-needed": lambda grouped, requirements, ledger: _decisions(
        grouped, requirements, ledger
    ),
    "next-actions": lambda grouped, requirements, ledger: _next(grouped, requirements, ledger),
}


def _assemble(
    title, source, confidence_line, tallied, table, bullets,
    assembly, trend, manifest, requirements, full_assessment_url, overall,
):
    lines = [
        title,
        "",
        f"**Updated:** {util.date_only(assembly.get('generatedAt'))}",
        f"**Source:** {source}",
        confidence_line,
        "",
        *table,
        "",
        f"_{tallied['caption']} {tallied['total']} criteria in total._",
    ]
    mix = _mix_line(requirements)
    if mix:
        lines += ["", mix]
    # Before the bullets, and a paragraph rather than a fifth bullet: at 60-100
    # words it is the position the other four are the detail of, and a bullet
    # that long stops being scannable and takes the list down with it.
    lines += ["", f"**Overall assessment:** {overall}"]
    lines += ["", *bullets, "", f"**Trend:** {trend or 'Baseline established.'}"]
    caveat = _scope_caveat(manifest)
    if caveat:
        lines += ["", caveat]
    # Only an absolute http(s) URL. `unpublishable` catches `file://` and home
    # directories, but a bare `full-assessment.html` passed it and rendered as
    # a link that resolves against the Jira host - a 404 for every reader
    # except the person who generated the file. The HTML report written by
    # `--html` is a local file and is not this.
    if full_assessment_url and links_mod.safe_url(full_assessment_url):
        lines += ["", f"[Full assessment]({full_assessment_url})"]
    return "\n".join(lines).rstrip() + "\n"
