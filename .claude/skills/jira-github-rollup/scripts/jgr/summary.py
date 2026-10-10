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
  six Jira issues; `RHAIGW-399 AC1` is not.
"""

from __future__ import annotations

import re

from . import links as links_mod
from . import outcomes as outcomes_mod
from . import util

WORD_FLOOR = 150
WORD_CEILING = 250

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
    """`RHAIGW-399 AC1`. Never a bare `AC1`: six Jira issues here have one."""
    key = requirement.get("sourceKey")
    return f"{key} {requirement.get('id')}" if key else str(requirement.get("id"))


def criterion_ref(requirement, site=None):
    """How a criterion is pointed at when it has no anchor of its own."""
    return links_mod.jira_link(
        requirement.get("sourceKey"), site=site, criterion=requirement.get("id")
    )


def counts_by_source(requirements):
    """`4 on RHAIGW-400, 3 on RHAIGW-401` - the tail of a collapsed enumeration."""
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
        tail = f"{len(rest)} more — {counts_by_source(rest)}"
        return f"{head}, and {tail}" if head else tail.replace("more", "criteria", 1)


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
            f"with at least one clause nothing inspected supports: {ledger.refs(uncovered)}"
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
    """The Jira summary draft, as Markdown.

    `full_assessment_url` is included only when the caller can name a durable,
    reader-accessible location. A local path is not one, and `links.py`
    refuses it.
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

    # Shrink the named detail until the prose fits the budget, never dropping a
    # bullet outright - a summary missing "Decisions needed" is a different
    # document, not a shorter one. Narrative is never truncated: it is the
    # model's claim, and a half-sentence claim is worse than a long one.
    for cap in (MAX_REFS_PER_BULLET, 2, 1):
        ledger = _Ledger(site, limit=cap)
        bullets = []
        for slug, label in BULLETS:
            text = _narrative_bullet(slug, narrative, requirements, ledger)
            if text is None:
                text = _FALLBACK[slug](grouped, requirements, ledger)
            bullets.append(f"- **{label}:** {text}")
        body = _assemble(
            title, source, confidence_line, tallied, table, bullets,
            assembly, trend, manifest, requirements, full_assessment_url,
        )
        if word_count(body) <= WORD_CEILING:
            break
    return body


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
    assembly, trend, manifest, requirements, full_assessment_url,
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
