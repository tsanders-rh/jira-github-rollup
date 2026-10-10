"""The Jira summary draft: the scannable half of the same assessment.

This is not a shortened report. It is a second rendering of the *same*
structured assessment, and the contract is that a reader cannot find a
classification or a count here that disagrees with the full assessment -
`assemble` checks that rather than trusting it.

What it must not become is a progress bar. The counts are an upstream evidence
assessment, the caption says so, and delivery confidence is computed from
release targets and qualification evidence rather than from how much of the
table is green.
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


def _id_key(requirement):
    """Sort SC9 before SC10, and keep criteria from one Jira together."""
    text = str(requirement.get("id") or "")
    match = re.match(r"^([A-Za-z]*)(\d*)", text)
    return (requirement.get("sourceKey") or "", match.group(1), int(match.group(2) or 0), text)


def _ordered(requirements):
    return sorted(requirements, key=_id_key)


def _ids(requirements):
    return ", ".join(str(r.get("id")) for r in _ordered(requirements))


def criterion_ref(requirement, site=None):
    """How a criterion is pointed at when it has no anchor of its own."""
    return links_mod.jira_link(
        requirement.get("sourceKey"), site=site, criterion=requirement.get("id")
    )


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


class _Budget:
    """Hands out at most `LINKS_PER_BULLET` artifact links, then goes quiet.

    Counting rather than slicing, because the links are spread across several
    clauses of one bullet and the cap is on the bullet.
    """

    def __init__(self, limit=LINKS_PER_BULLET):
        self.left = limit

    def spend(self, requirement):
        if self.left <= 0:
            return ""
        pointers = evidence_links(requirement, 1)
        if not pointers:
            return ""
        self.left -= 1
        return f" ({pointers[0]})"


def _and_others(shown, total, noun="criterion", plural="criteria"):
    extra = total - shown
    if extra <= 0:
        return ""
    return f" and {extra} other {noun if extra == 1 else plural}"


def _progress(grouped, site, cap):
    """Material outcomes supported by evidence, each with its strongest link."""
    items = _ordered(grouped["met"] + grouped["partial"])
    if not items:
        return (
            "Progress: No criterion is yet supported by landed upstream evidence in the "
            "sources inspected."
        )
    budget, parts = _Budget(), []
    for requirement in items[:cap]:
        verdict = "met" if outcomes_mod.classify(requirement) == "met" else "partly supported"
        parts.append(f"{criterion_ref(requirement, site)} {verdict}{budget.spend(requirement)}")
    return (
        "Progress: "
        + "; ".join(parts)
        + _and_others(len(parts), len(items), "criterion with evidence", "criteria with evidence")
        + "."
    )


def _remaining(grouped, site, cap):
    """Implementation or qualification work that is identified and outstanding."""
    tracked = _ordered(
        [r for r in grouped["unverified"] + grouped["confirmed-unmet"] if r.get("evidence")]
    )
    pending_downstream = _ordered(
        [
            r
            for r in grouped["met"] + grouped["partial"]
            if ((r.get("downstream") or {}).get("state") or "unknown") != "confirmed"
        ]
    )
    budget, parts = _Budget(), []
    for requirement in tracked[:cap]:
        parts.append(
            f"{criterion_ref(requirement, site)} tracked and incomplete{budget.spend(requirement)}"
        )
    if parts:
        parts[-1] += _and_others(len(parts), len(tracked))
    if pending_downstream:
        parts.append(
            "downstream qualification was not inspected for " + _ids(pending_downstream)
        )
    if not parts:
        return "Remaining: No outstanding upstream work was identified in the sources inspected."
    return "Remaining: " + "; ".join(parts) + "."


def _attention(grouped, requirements, site, cap):
    """Decisions, blockers, and tracking clarifications - each with a pointer."""
    untracked = _ordered([r for r in grouped["unverified"] if not r.get("evidence")])
    decisions = _ordered([r for r in requirements or [] if r.get("unresolvedClauses")])

    budget, parts = _Budget(), []
    if untracked:
        # The wording the brief asks for, and the only one that is true: this
        # is a request to find the owner, not a claim that there is none.
        parts.append(
            f"no upstream work in the traversed set is linked to "
            f"{criterion_ref(untracked[0], site)}"
            + (f", {_ids(untracked[1:])}" if len(untracked) > 1 else "")
            + f" — identify and link the work covering {_ids(untracked)}"
        )
    for requirement in decisions[:cap]:
        parts.append(
            f"a decision is open on {criterion_ref(requirement, site)}"
            f"{budget.spend(requirement)}"
        )
    if len(decisions) > cap:
        parts[-1] += _and_others(cap, len(decisions))
    if not parts:
        return "Attention needed: None identified beyond the work listed above."
    return "Attention needed: " + "; ".join(parts) + "."


def _next(grouped, requirements, site, cap):
    """Concrete actions. Owners and dates appear only where a source established one."""
    untracked = _ordered([r for r in grouped["unverified"] if not r.get("evidence")])
    decisions = _ordered([r for r in requirements or [] if r.get("unresolvedClauses")])
    pending = _ordered(
        [
            r
            for r in grouped["met"] + grouped["partial"]
            if ((r.get("downstream") or {}).get("state") or "unknown") != "confirmed"
        ]
    )
    actions = []
    if untracked:
        actions.append("link the owning issue or epic for " + _ids(untracked))
    if decisions:
        actions.append("record the open decision on " + _ids(decisions))
    if pending:
        actions.append("run or cite downstream qualification for " + _ids(pending))
    if not actions:
        return "Next: No action identified from the sources inspected."
    return (
        "Next: "
        + "; ".join(actions)
        + ". No owner or date for these is recorded in the sources inspected."
    )


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
    kind = "published" if baseline.get("publication") == "published" else "draft"

    changes = diff.get("requirementChanges") or {}
    scope_changed = bool(
        changes.get("added") or changes.get("removed") or changes.get("textChanged")
    )
    inventory = diff.get("inventoryChanges") or {}
    access_changed = bool(inventory.get("accessLost") or inventory.get("accessRestored"))

    moved = [
        f"{outcomes_mod.LABELS[name].lower()} {before['counts'][name]}→{tallied['counts'][name]}"
        for name in outcomes_mod.OUTCOMES
        if before["counts"][name] != tallied["counts"][name]
    ]
    if not moved:
        body = f"no outcome changed since the {kind} snapshot of {when}"
    else:
        body = f"since the {kind} snapshot of {when}, " + ", ".join(moved)

    notes = []
    if before["total"] != tallied["total"]:
        notes.append(
            f"the criteria set changed ({before['total']}→{tallied['total']}), so these are "
            "not like-for-like"
        )
    elif scope_changed:
        notes.append("criterion text changed, so these are not like-for-like")
    if access_changed:
        notes.append("source access changed this run, so some movement is newly visible rather than newly done")
    return body + (". " + "; ".join(notes).capitalize() + "." if notes else ".")


def _trend(assembly, line):
    return f"Trend: {line}" if line else "Trend: Baseline established."


def _scope_caveat(manifest):
    """One short sentence, only when a limitation materially affects the assessment."""
    notes = manifest.get("traversalNotes") or []
    inaccessible = [a for a in manifest.get("access") or [] if a.get("status") != "readable"]
    clauses = []
    if inaccessible:
        refs = ", ".join(a.get("ref", "?") for a in inaccessible[:3])
        clauses.append(f"{len(inaccessible)} source(s) could not be read ({refs})")
    nested = [n for n in notes if "nested epic" in n.lower()]
    if nested:
        clauses.append(f"{len(nested)} nested epics were recorded but not traversed")
    if not manifest.get("traversalComplete", True):
        clauses.append("traversal was incomplete")
    if not clauses:
        return None
    return (
        "Scope: " + "; ".join(clauses) + ". Criteria owned by that work would not appear "
        "here, so an unverified row is not evidence that the work is missing."
    )


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
    # bullet outright - a summary missing "Attention needed" is a different
    # document, not a shorter one.
    for cap in (4, 3, 2, 1):
        bullets = [
            "- " + _progress(grouped, site, cap),
            "- " + _remaining(grouped, site, cap),
            "- " + _attention(grouped, requirements, site, cap),
            "- " + _next(grouped, requirements, site, cap),
        ]
        body = _assemble(
            title, jira, source, confidence_line, tallied, table, bullets,
            assembly, trend, manifest, full_assessment_url,
        )
        if word_count(body) <= WORD_CEILING:
            break
    return body


def _assemble(
    title, jira, source, confidence_line, tallied, table, bullets,
    assembly, trend, manifest, full_assessment_url,
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
        "",
        *bullets,
        "",
        _trend(assembly, trend),
    ]
    caveat = _scope_caveat(manifest)
    if caveat:
        lines += ["", caveat]
    if full_assessment_url and not links_mod.unpublishable(full_assessment_url):
        lines += ["", f"[Full assessment]({full_assessment_url})"]
    return "\n".join(lines).rstrip() + "\n"
