"""The HTML rendering of the full assessment.

A third rendering of the *same* assembly the Markdown report and the Jira
summary come from - not a third assessment. Everything here reads fields that
are already merged, tallied and validated by `assemble.build`; nothing in this
module classifies a criterion, decides what evidence shows, or writes prose.
If a sentence in the output is a judgement, it was the model's and it arrived
in the assembly.

That is what makes re-rendering an old snapshot safe: `rollup.py rerender`
rebuilds the assembly from the stored rows and calls this, and no network, no
cache and no new judgement is involved.

Three things this module is strict about:

* **Every string from Jira or GitHub is escaped.** `text()` is the only way
  source content reaches the document, and it goes through `html.escape`.
  There is no embedded JSON payload and no client-side templating, so there is
  no second path to audit.
* **Every URL is scheme-checked.** `safe_url` admits `http` and `https` and
  nothing else, so a `javascript:` or `data:` ref recorded upstream renders as
  inert text rather than as a link.
* **Nothing local is published.** Cache paths, `file://` URLs and home
  directories are caught by `links.unpublishable` before the file is written.
  An HTML report is easier to hand around than a Jira comment, not harder.

Missing data is said to be missing. There is no field in here that falls back
to a plausible value, because the report's whole claim on a reader's attention
is that an absent number means nobody measured it.
"""

from __future__ import annotations

import html as html_mod

from . import htmlassets
from . import links as links_mod
from . import metrics as metrics_mod
from . import outcomes as outcomes_mod
from . import render as render_mod
from . import summary as summary_mod
from . import util

EMDASH = "—"

# The third column header follows the written contract, not the shorthand: a
# column labelled "Unmet" invites a reader to file "we did not look" under it,
# and that conflation is the one this whole tool exists to prevent.
OUTCOME_HEADERS = {
    "met": "Met",
    "partial": "Partial",
    "confirmed-unmet": "Confirmed unmet",
    "unverified": "Unverified",
}
BADGE_CLASS = {
    "met": "badge-met",
    "partial": "badge-partial",
    "confirmed-unmet": "badge-unmet",
    "unverified": "badge-unverified",
}

# What the collection step records, in plain language. `documented` and
# `test present` are not states this pipeline can distinguish - it reads issue
# and PR metadata, changed-file lists and check results, not file contents -
# so they are absent here rather than guessed at. The collection section says
# so in as many words.
EVIDENCE_STATE = {
    "planned": "Planned; not yet implemented",
    "in progress": "Implementation in progress",
    "in review": "Implemented; in review, not merged",
    "merged": "Implemented; change merged",
    "tested": "Test execution verified in CI",
    "not observed": "Not observed",
}

TYPE_PLURAL = {key: label[1].capitalize() for key, label in render_mod.TYPE_LABEL.items()}


# --- escaping and links --------------------------------------------------


def text(value, fallback=""):
    """The only way source content enters the document."""
    if value is None:
        return fallback
    return html_mod.escape(str(value), quote=True)


def attr(value):
    return html_mod.escape(str(value or ""), quote=True)


safe_url = links_mod.safe_url


def anchor(url, label, classes=None):
    """A link when the URL survives `safe_url`, plain escaped text otherwise."""
    safe = safe_url(url)
    body = text(label)
    if not safe:
        return body
    cls = f' class="{attr(classes)}"' if classes else ""
    return f'<a{cls} href="{attr(safe)}" rel="noreferrer noopener">{body}</a>'


def ref_anchor(ref, kind=None, label=None):
    return anchor(links_mod.url_for(ref, kind), label or ref)


def jira_anchor(key, site, label=None):
    return anchor(links_mod.jira_url(site, key), label or key)


# --- small helpers -------------------------------------------------------


def _date(value):
    return util.date_only(value) or ""


def _clause_text(clause):
    return clause if isinstance(clause, str) else (clause or {}).get("text", "")


def _sentence(value):
    """Capitalised, so a reason written as a fragment does not start mid-line.

    These arrive from the collector as sentence fragments meant to follow a
    semicolon. Here they follow a bold label and a full stop.
    """
    cleaned = str(value or "").strip()
    return cleaned[:1].upper() + cleaned[1:] if cleaned else cleaned


def _observed(manifest):
    return manifest.get("observed", bool(manifest.get("epics")))


def needs_attention(requirement):
    """Everything that is not a finished, qualified, fully covered criterion.

    Deliberately broad. A met criterion whose downstream step nobody has
    confirmed is still something a reader filtering for "what do I have to
    deal with" wants to see; leaving it out would make the checkbox quietly
    narrower than its label.
    """
    if outcomes_mod.classify(requirement) != "met":
        return True
    if requirement.get("unresolvedClauses") or requirement.get("uncoveredClauses"):
        return True
    return ((requirement.get("downstream") or {}).get("state") or "unknown") != "confirmed"


def _haystack(requirement, finding):
    """What the search box matches on, lowercased at render time, not in JS."""
    parts = [
        summary_mod.qualified(requirement),
        requirement.get("id"),
        requirement.get("sourceKey"),
        requirement.get("type"),
        render_mod.TYPE_LABEL.get(requirement.get("type"), ("", ""))[0],
        requirement.get("text"),
        requirement.get("heading"),
        finding,
        requirement.get("gap"),
        requirement.get("evidenceState"),
        outcomes_mod.ROW_LABELS[outcomes_mod.classify(requirement)],
        (requirement.get("downstream") or {}).get("detail"),
    ]
    for item in (requirement.get("evidence") or []) + (requirement.get("refutingEvidence") or []):
        parts.append(item.get("ref"))
    for clause in (requirement.get("unresolvedClauses") or []) + (
        requirement.get("uncoveredClauses") or []
    ):
        parts.append(_clause_text(clause))
    return " ".join(str(part) for part in parts if part).lower()


def _finding(requirement):
    """The one-line finding for the collapsed row.

    `coverageDetail` is the model's sentence about what the evidence shows, so
    it is the right thing to show first. Falling back to the assessment label
    rather than to the criterion text: repeating the requirement in the
    finding column would make the collapsed row say nothing twice.
    """
    detail = (requirement.get("coverageDetail") or "").strip()
    if detail:
        return detail
    gap = (requirement.get("gap") or "").strip()
    if gap:
        return gap
    return requirement.get("assessment") or "Unable to assess"


# --- 1. header -----------------------------------------------------------


def header_block(assembly):
    jira = assembly.get("jira") or {}
    site = jira.get("site")
    key = jira.get("key") or ""
    published = (assembly.get("publication") or "draft") == "published"
    state = "Published to Jira" if published else "Draft " + EMDASH + " not published"

    out = ['<header class="head">', "<div>"]
    out.append('<p class="eyebrow">Upstream development rollup</p>')
    out.append(f"<h1>{text(jira.get('summary') or key)}</h1>")
    out.append(
        '<p class="meta">'
        + jira_anchor(key, site)
        + '<span class="sep">·</span>'
        + text(_date(assembly.get("generatedAt")) or "date not recorded")
        + '<span class="sep">·</span>'
        + text(state)
        + "</p>"
    )

    mappings = assembly.get("mappings") or []
    manifest = assembly.get("manifest") or {}
    if mappings:
        out.append('<ul class="epics">')
        for mapping in mappings:
            ref = mapping.get("ref") or mapping.get("epic") or ""
            label = ref if not mapping.get("title") else f"{ref} {EMDASH} {mapping['title']}"
            link = anchor(mapping.get("url") or links_mod.url_for(ref), label)
            note = ""
            if (mapping.get("linkSource") or "").startswith("incidental"):
                note = (
                    " <span class=\"when\">(from an unlabelled URL on the Jira; "
                    "confirm this is the intended mapping)</span>"
                )
            out.append(f"<li>Upstream: {link}{note}</li>")
        out.append("</ul>")
    else:
        reason = manifest.get("unobservedReason") or "no link recorded on the Jira issue"
        out.append(f'<ul class="epics"><li>Upstream: none recorded ({text(reason)})</li></ul>')
    out.append("</div>")
    out.append(
        '<button type="button" class="toggle no-print" id="toggle-all" '
        'aria-controls="requirement-review" aria-expanded="false">Expand evidence</button>'
    )
    out.append("</header>")
    return out


# --- 2. material limitations ---------------------------------------------


def limitations(assembly, computed):
    """The material collection limitations, as data. Empty list means none.

    Each entry is something a source said or failed to say, never an inference
    about the work. Returning an empty list is the normal case for a clean run
    and the banner is omitted entirely - a standing warning is one nobody
    reads by the third report.
    """
    manifest = assembly.get("manifest") or {}
    items = []

    if not _observed(manifest):
        items.append(
            "No upstream epic was read ("
            + (manifest.get("unobservedReason") or "reason not recorded")
            + "). Upstream coverage is unassessable here, not absent."
        )
    for entry in manifest.get("untraversed") or []:
        items.append(
            "Not traversed: "
            + str(entry.get("ref") or "unnamed branch")
            + " ("
            + (entry.get("reason") or "no reason recorded")
            + "). Criteria owned beneath it are not in this assessment at all."
        )
    for entry in manifest.get("access") or []:
        if entry.get("status") != "readable":
            items.append(
                "Not readable: "
                + str(entry.get("ref"))
                + " ("
                + str(entry.get("status"))
                + ") "
                + EMDASH
                + " "
                + (entry.get("detail") or "no detail recorded")
                + "."
            )
    if not manifest.get("traversalComplete", True):
        items.append(
            "Traversal did not complete. Counts below the epic are a floor, not a total."
        )
    if computed["coverage"]["state"] != metrics_mod.OBSERVED:
        items.append(
            "Requirement coverage could not be computed ("
            + (computed["coverage"].get("reason") or "reason not recorded")
            + ")."
        )
    return items


def banner_block(assembly, computed):
    items = limitations(assembly, computed)
    if not items:
        return []
    out = [
        '<div class="banner" role="note">',
        "<p>Material collection limitations apply to this assessment.</p>",
        "<ul>",
    ]
    out.extend(f"<li>{text(item)}</li>" for item in items)
    out.append("</ul>")
    out.append(
        "<ul><li>No downstream build, payload, or qualification run was inspected. "
        "Qualification is reported only where a source that was read establishes it, and "
        "nothing here is a release-readiness verdict.</li></ul>"
    )
    out.append("</div>")
    return out


# --- 3. overview ---------------------------------------------------------


def outcome_card(assembly, tallied):
    """Counts by requirement type, with no combined completion figure.

    The totals row is the tally the Jira summary and the Markdown report carry,
    so a reader comparing the three sees the same four numbers. It is a count,
    not a score: there is no denominator and no percentage anywhere in this
    card, because acceptance criteria, success criteria and definition-of-done
    items are not interchangeable units of delivery.
    """
    requirements = assembly.get("requirements") or []
    groups = metrics_mod.by_type(requirements)
    heads = "".join(f'<th class="num">{text(OUTCOME_HEADERS[n])}</th>' for n in outcomes_mod.OUTCOMES)

    out = [
        '<div class="card">',
        "<h3>Outcome overview</h3>",
        '<div class="scroll-x">',
        "<table>",
        f"<thead><tr><th>Type</th>{heads}</tr></thead>",
        "<tbody>",
    ]
    if not requirements:
        out.append(
            '<tr><td colspan="5">No acceptance criteria, success criteria, or '
            "definition-of-done items were found on the Jira sources read.</td></tr>"
        )
    for group in groups:
        cells = "".join(
            f'<td class="num">{group["outcomes"][n]}</td>' for n in outcomes_mod.OUTCOMES
        )
        out.append(
            f'<tr><th scope="row">{text(TYPE_PLURAL.get(group["type"], group["type"]))}</th>{cells}</tr>'
        )
    if requirements:
        totals = "".join(
            f'<td class="num"><strong>{tallied["counts"][n]}</strong></td>'
            for n in outcomes_mod.OUTCOMES
        )
        out.append(
            f'<tr><th scope="row">All criteria ({tallied["total"]})</th>{totals}</tr>'
        )
    out.append("</tbody></table></div>")
    out.append(
        '<p class="note">Separate counts by requirement type. '
        + text(tallied["caption"])
        + " They are not summed into a completion figure.</p>"
    )
    out.append("</div>")
    return out


def _movement(assembly, computed):
    """The comparable-movement line, or why there is not one.

    `like_for_like` is the only honest movement figure when the requirement
    inventory changed, because the raw ratio moved partly because the
    denominator did. When it is unavailable the card says that in words rather
    than printing a number that means something else.
    """
    diff = assembly.get("diff") or {}
    baseline = diff.get("baseline")
    if not baseline:
        return "No baseline to compare against."

    requirements = assembly.get("requirements") or []
    changes = diff.get("requirementChanges") or {}
    scope_moved = bool(changes.get("added") or changes.get("removed") or changes.get("textChanged"))
    like = metrics_mod.like_for_like(diff.get("matchedPairs"), requirements)

    if like:
        delta = util.round_half_up(like["current"]["pct"] - like["previous"]["pct"])
        sign = "+" if delta >= 0 else "−"
        return (
            f"Over the {like['total']} criteria present and unchanged in both snapshots, "
            f"evidence found went from {metrics_mod.render_ratio(like['previous'])} to "
            f"{metrics_mod.render_ratio(like['current'])} ({sign}{abs(delta)} pp)."
        )
    if scope_moved:
        return (
            "Numerical movement is unavailable: the requirement inventory changed between "
            "snapshots, so the ratios have different denominators and are not comparable."
        )
    previous = metrics_mod.from_snapshot(assembly.get("baselineSnapshot") or {})
    if not previous:
        return "Numerical movement is unavailable: the baseline snapshot could not be read."
    return (
        f"Evidence found: {metrics_mod.render_ratio(previous['coverage'])} at the baseline, "
        f"{metrics_mod.render_ratio(computed['coverage'])} now."
    )


def context_card(assembly, computed):
    jira = assembly.get("jira") or {}
    diff = assembly.get("diff") or {}
    baseline = diff.get("baseline") or {}
    changes = diff.get("requirementChanges") or {}

    fix = ", ".join(jira.get("fixVersions") or [])
    release = fix if fix else "Not recorded on the Jira issue"

    if baseline.get("generatedAt"):
        kind = "published" if baseline.get("publication") == "published" else "draft, never published"
        baseline_line = f"{_date(baseline['generatedAt'])} ({kind})"
    elif diff.get("baselineProblem"):
        problem = diff["baselineProblem"]
        baseline_line = (
            f"{_date(problem.get('generatedAt'))} exists but could not be read "
            f"({problem.get('detail') or 'no detail recorded'})"
        )
    else:
        baseline_line = "None " + EMDASH + " baseline established by this run"

    # Only against a baseline. A first run's diff lists every criterion as
    # "added", which is true of the file and false of the work - and it is the
    # one line that would differ between this run and a re-render of its own
    # snapshot, because the diff is not what the snapshot stores.
    added = (changes.get("added") or []) if baseline.get("generatedAt") else []
    removed = (changes.get("removed") or []) if baseline.get("generatedAt") else []
    edited = (changes.get("textChanged") or []) if baseline.get("generatedAt") else []
    if added or removed or edited:
        parts = []
        if added:
            parts.append(f"{len(added)} added")
        if removed:
            parts.append(f"{len(removed)} removed")
        if edited:
            parts.append(f"{len(edited)} edited")
        scope_line = ", ".join(parts)
    elif baseline.get("generatedAt"):
        scope_line = "Unchanged since the baseline"
    else:
        scope_line = "No prior inventory to compare"

    rows = [
        ("Release target", release),
        ("Baseline", baseline_line),
        ("Requirement scope", scope_line),
        ("Comparable movement", _movement(assembly, computed)),
        ("Child issues completed", metrics_mod.render_ratio(computed["children"])),
    ]
    out = ['<div class="card">', "<h3>Assessment context</h3>", '<dl class="facts">']
    for label, value in rows:
        out.append(f"<dt>{text(label)}</dt><dd>{text(value)}</dd>")
    out.append("</dl>")
    out.append("</div>")
    return out


def overview_section(assembly, tallied, computed):
    out = ['<section class="first" aria-labelledby="h-overview">', '<h2 id="h-overview">Overview</h2>', '<div class="grid-2">']
    out.extend(outcome_card(assembly, tallied))
    out.extend(context_card(assembly, computed))
    out.append("</div></section>")
    return out


# --- 4. decisions and follow-up ------------------------------------------


def _entry(kind, title, body, refs_html, links_html):
    out = ['<div class="decision">', "<div>"]
    out.append(f'<div class="kind">{text(kind)}</div>')
    out.append(f'<div class="title">{text(title)}</div>')
    if body:
        out.append(f'<div class="body">{text(body)}</div>')
    if refs_html:
        out.append(f'<div class="refs">{refs_html}</div>')
    out.append("</div>")
    out.append(f'<div class="links">{links_html}</div>')
    out.append("</div>")
    return out


def decisions_section(assembly):
    """The model's narrative claims and the dependencies a source actually named.

    The four bullet kinds carry the distinction the brief asks for: what the
    evidence established is filed apart from what is still an open question,
    and the label says which is which. Criterion references are qualified with
    their own source key, and the links are the ones the claim was validated
    against - `assemble` has already refused anything citing a row that does
    not exist or a link no cited row carries.
    """
    narrative = assembly.get("narrative") or []
    dependencies = assembly.get("dependencies") or []
    requirements = assembly.get("requirements") or []
    site = (assembly.get("jira") or {}).get("site")
    index = {(r.get("sourceKey"), r.get("id")): r for r in requirements}
    if not narrative and not dependencies:
        return []

    out = [
        '<section aria-labelledby="h-decisions">',
        '<h2 id="h-decisions">Decisions and follow-up</h2>',
    ]
    for slug, label in summary_mod.BULLETS:
        entries = [e for e in narrative if isinstance(e, dict) and e.get("bullet") == slug]
        for entry in entries:
            cited = [
                index[(ref.get("sourceKey"), ref.get("id"))]
                for ref in entry.get("refs") or []
                if isinstance(ref, dict) and (ref.get("sourceKey"), ref.get("id")) in index
            ]
            # Qualified, and capped. Past a handful the list stops being a
            # pointer into the table below and starts being a second copy of it.
            shown = cited[: summary_mod.MAX_REFS_PER_BULLET]
            refs_html = ", ".join(
                jira_anchor(r.get("sourceKey"), site, summary_mod.qualified(r)) for r in shown
            )
            if len(cited) > len(shown):
                refs_html += text(f", and {len(cited) - len(shown)} more below")
            links_html = " ".join(
                ref_anchor(link, _kind_of(link, cited), links_mod.short(link))
                for link in (entry.get("links") or [])[: summary_mod.LINKS_PER_BULLET]
            )
            sentence = str(entry.get("text") or "").strip()
            out.extend(_entry(label, sentence, None, refs_html, links_html))

    for dependency in dependencies:
        pointer = dependency.get("ref") or dependency.get("key")
        if pointer and links_mod.url_for(pointer):
            links_html = ref_anchor(pointer, None, links_mod.short(pointer))
        elif pointer:
            links_html = jira_anchor(pointer, site)
        else:
            links_html = text("No owning ticket identified")
        criteria = ", ".join(dependency.get("criteria") or []) or "unstated criteria"
        note = dependency.get("note") or (
            "Named on a source that was read; not traversed by this run."
        )
        # Owner and date are shown only when the dependency record carries
        # them. There is nothing to infer them from, and a guessed owner is an
        # action item sent to the wrong person.
        attribution = [
            part
            for part in (dependency.get("owner"), _date(dependency.get("due")))
            if part
        ]
        body = note + (" (" + ", ".join(attribution) + ")" if attribution else "")
        out.extend(_entry("Dependency", criteria, body, "", links_html))

    out.append("</section>")
    return out


def _kind_of(ref, requirements):
    for requirement in requirements:
        for item in (requirement.get("evidence") or []) + (
            requirement.get("refutingEvidence") or []
        ):
            if item.get("ref") == ref:
                return item.get("kind")
    return None


# --- 5. requirement review -----------------------------------------------


def _evidence_items(items):
    out = ["<ul>"]
    for item in items:
        ref = item.get("ref")
        kind = (item.get("kind") or "").lower()
        label = links_mod.short(ref) if links_mod.url_for(ref) else str(ref)
        if kind == "pr":
            label = f"PR {label}"
        line = ref_anchor(ref, kind, label) if kind != "check" else text(ref)
        bits = []
        state = (item.get("state") or "").strip()
        if state:
            bits.append(state)
        if item.get("at"):
            bits.append(_date(item["at"]))
        if bits:
            line += f' <span class="when">({text(" · ".join(bits))})</span>'
        out.append(f"<li>{line}")
        # Commit-pinned file references, only when both the commit and the path
        # were recorded. A path without a commit points at whatever that file
        # says today, which is not what was inspected.
        for source in item.get("files") or []:
            repo, commit, path = source.get("repo"), source.get("commit"), source.get("path")
            if not (repo and commit and path):
                continue
            url = source.get("url") or f"https://github.com/{repo}/blob/{commit}/{path}"
            out.append(
                f'<div class="when">{anchor(url, path)} '
                f"{EMDASH} {text(repo)} @ {text(str(commit)[:7])}</div>"
            )
        out.append("</li>")
    out.append("</ul>")
    return "".join(out)


def _clause_list(heading, clauses, note):
    if not clauses:
        return ""
    items = "".join(f"<li>{text(_clause_text(clause))}</li>" for clause in clauses)
    return (
        f'<div class="block"><h4>{text(heading)}</h4><ul>{items}</ul>'
        f'<p class="note">{text(note)}</p></div>'
    )


def requirement_row(requirement, site):
    outcome = outcomes_mod.classify(requirement)
    finding = _finding(requirement)
    downstream = requirement.get("downstream") or {}
    state = (downstream.get("state") or "unknown").lower()
    qualification = metrics_mod.DOWNSTREAM_LABELS.get(
        state, metrics_mod.DOWNSTREAM_LABELS["unknown"]
    )

    out = [
        "<details class=\"row\""
        f' data-outcome="{attr(outcome)}"'
        f' data-type="{attr(requirement.get("type") or "REQ")}"'
        f' data-attention="{"1" if needs_attention(requirement) else "0"}"'
        f' data-search="{attr(_haystack(requirement, finding))}">'
    ]
    out.append('<summary><span class="rowline">')
    out.append('<span class="chev" aria-hidden="true">❯</span>')
    out.append(f'<span class="cid">{text(summary_mod.qualified(requirement))}</span>')
    out.append(f'<span class="cfind">{text(finding)}</span>')
    out.append(
        f'<span class="cout"><span class="badge {attr(BADGE_CLASS[outcome])}">'
        f"{text(outcomes_mod.ROW_LABELS[outcome])}</span></span>"
    )
    out.append(f'<span class="cq">{text(qualification)}</span>')
    out.append("</span></summary>")

    # --- expanded: left column
    out.append('<div class="detail">')
    out.append("<div>")
    out.append(
        '<div class="block"><h4>Exact requirement text</h4>'
        f"<blockquote>{text(requirement.get('text'), 'Not recorded.')}</blockquote></div>"
    )
    out.append(
        '<div class="block"><h4>Clause-level coverage</h4>'
        f"<p>{text(requirement.get('coverageDetail'), 'No clause-level detail recorded.')}</p></div>"
    )
    out.append(
        _clause_list(
            "Clauses not covered",
            requirement.get("uncoveredClauses"),
            "The rest of the criterion may hold; these parts are not established by "
            "anything inspected.",
        )
    )
    out.append(
        _clause_list(
            "Clauses unresolved",
            requirement.get("unresolvedClauses"),
            "Undecided upstream. Until a decision is recorded these are unassessable "
            "rather than unmet.",
        )
    )
    if requirement.get("gap"):
        out.append(
            '<div class="block"><h4>Gap, dependency, or next action</h4>'
            f"<p>{text(requirement['gap'])}</p></div>"
        )
    out.append("</div>")

    # --- expanded: right column
    out.append("<div>")
    evidence = requirement.get("evidence") or []
    out.append('<div class="block"><h4>Supporting evidence</h4>')
    out.append(
        _evidence_items(evidence)
        if evidence
        else "<p>None recorded. Absence in the sources inspected is not a finding that the "
        "work does not exist.</p>"
    )
    recorded = (requirement.get("evidenceState") or "").strip().lower()
    out.append(
        '<p class="note">Evidence state: '
        + text(EVIDENCE_STATE.get(recorded, requirement.get("evidenceState") or "not recorded"))
        + "</p>"
    )
    out.append("</div>")

    refuting = requirement.get("refutingEvidence") or []
    if refuting:
        out.append(
            '<div class="block"><h4>Refuting evidence</h4>' + _evidence_items(refuting) + "</div>"
        )
    out.append(
        '<div class="block"><h4>Downstream qualification</h4>'
        f"<p><strong>{text(qualification)}.</strong> "
        f"{text(downstream.get('detail'), 'No downstream step identified in the sources inspected; that is not confirmation that none is required.')}</p></div>"
    )
    provenance = f"Assessed {_date(requirement.get('assessedAt')) or 'date not recorded'}"
    if requirement.get("reused"):
        carried = _date(requirement.get("assessedFromSnapshot"))
        provenance += f"; carried forward unchanged{' from ' + carried if carried else ''}"
    out.append(f'<p class="note">{text(provenance)}.</p>')
    out.append("</div>")

    out.append("</div></details>")
    return out


def review_section(assembly):
    requirements = assembly.get("requirements") or []
    jira = assembly.get("jira") or {}
    site = jira.get("site")
    titles = {jira.get("key"): jira.get("summary")}
    for child in jira.get("children") or []:
        titles[child.get("key")] = child.get("summary")

    out = [
        '<section id="requirement-review" aria-labelledby="h-review">',
        '<h2 id="h-review">Requirement review</h2>',
    ]
    if not requirements:
        out.append(
            "<p>No acceptance criteria, success criteria, or definition-of-done items were "
            "found on the Jira sources read. There is nothing to assess coverage against.</p>"
        )
        out.append("</section>")
        return out

    types = []
    for requirement in requirements:
        kind = requirement.get("type") or "REQ"
        if kind not in types:
            types.append(kind)
    type_options = "".join(
        f'<option value="{attr(kind)}">{text(TYPE_PLURAL.get(kind, kind))}</option>'
        for kind in render_mod.TYPE_ORDER
        if kind in types
    )
    outcome_options = "".join(
        f'<option value="{attr(name)}">{text(OUTCOME_HEADERS[name])}</option>'
        for name in outcomes_mod.OUTCOMES
    )

    out.append('<div class="controls no-print">')
    out.append('<label class="sr-only" for="q" hidden>Search criteria</label>')
    out.append(
        '<input type="search" id="q" placeholder="Search criteria, findings, evidence refs…" '
        'aria-label="Search criteria">'
    )
    out.append(
        '<label for="f-outcome" hidden>Outcome</label>'
        f'<select id="f-outcome" aria-label="Filter by outcome"><option value="">All outcomes</option>{outcome_options}</select>'
    )
    out.append(
        '<label for="f-type" hidden>Type</label>'
        f'<select id="f-type" aria-label="Filter by requirement type"><option value="">All types</option>{type_options}</select>'
    )
    out.append(
        '<label class="check" for="f-attention">'
        '<input type="checkbox" id="f-attention"> Show only items needing attention</label>'
    )
    out.append("</div>")
    out.append(
        f'<p class="count" id="visible-count" role="status" aria-live="polite">'
        f"Showing all {len(requirements)} criteria</p>"
    )

    order = []
    for requirement in requirements:
        key = requirement.get("sourceKey")
        if key not in order:
            order.append(key)

    for key in order:
        rows = [r for r in requirements if r.get("sourceKey") == key]
        title = titles.get(key)
        label = f"{key} {EMDASH} {title}" if title else str(key or "Source not recorded")
        heading = jira_anchor(key, site, label) if key else text(label)
        count_label = util.pluralize(len(rows), "criterion", "criteria")
        out.append('<div class="group">')
        out.append(
            f"<h3>{heading}"
            f'<span class="n" data-total="{len(rows)}" data-label="{attr(count_label)}">'
            f"{text(count_label)}</span></h3>"
        )
        out.append('<div class="rows">')
        out.append(
            '<div class="rowhead" aria-hidden="true">'
            '<span></span><span>ID</span><span>Finding</span>'
            "<span>Outcome</span><span>Qualification</span></div>"
        )
        for requirement in rows:
            out.extend(requirement_row(requirement, site))
        out.append("</div></div>")

    out.append("</section>")
    return out


# --- 6. changes since baseline -------------------------------------------


def changes_block(assembly):
    """Outcome movement for matched requirements, kept apart from scope change.

    The distinction the brief protects is the one `metrics.classify_assessment_
    changes` makes: a criterion that moved because work landed, a criterion
    that moved because evidence became visible, and a criterion that moved for
    a reason the dates cannot settle are three different facts. A larger
    assessed inventory is reported as scope, never as progress.
    """
    diff = assembly.get("diff") or {}
    baseline = diff.get("baseline") or {}
    requirements = assembly.get("requirements") or []
    out = ["<h3>Changes since baseline</h3>"]

    if not baseline.get("generatedAt"):
        problem = diff.get("baselineProblem")
        if problem:
            out.append(
                f"<p>A snapshot dated {text(_date(problem.get('generatedAt')))} exists but could "
                f"not be read ({text(problem.get('detail'))}). No comparison is made.</p>"
            )
        else:
            out.append("<p>Baseline established by this run. There is nothing to compare against.</p>")
        return out

    classified = metrics_mod.classify_assessment_changes(
        diff.get("matchedPairs"), requirements, baseline.get("generatedAt")
    )
    causes = {
        "implementation-progress": "New implementation",
        "newly-discovered-evidence": "Newly discovered evidence, not newly done work",
        "undetermined": "Cause undetermined from the dates recorded",
        "regression": "Assessment moved backwards",
    }
    moved = ["<ul>"]
    for entry in classified:
        moved.append(
            f"<li><strong>{text(causes.get(entry['cause'], entry['cause']))}.</strong> "
            f"{text(entry['sourceKey'])} {text(entry['id'])}: "
            f"{text(entry['from'])} → {text(entry['to'])}.</li>"
        )
    moved.append("</ul>")
    if classified:
        out.append("<p>Outcome movement, matched requirements only:</p>")
        out.extend(moved)
    else:
        out.append("<p>No matched requirement changed outcome.</p>")

    changes = diff.get("requirementChanges") or {}
    scope = []
    for item in changes.get("added") or []:
        scope.append(
            f"<li>Added to scope: {text(item.get('sourceKey'))} {text(item.get('id'))}.</li>"
        )
    for item in changes.get("removed") or []:
        scope.append(
            f"<li>Removed from scope: {text(item.get('sourceKey'))} {text(item.get('id'))} "
            f"(was {text(item.get('assessment') or 'unassessed')}).</li>"
        )
    for item in changes.get("textChanged") or []:
        scope.append(
            f"<li>Text edited: {text(item.get('sourceKey'))} {text(item.get('id'))}; "
            "reassessed from scratch.</li>"
        )
    if scope:
        out.append(
            "<p>Scope change. A larger assessed inventory is not delivery progress:</p>"
        )
        out.append("<ul>" + "".join(scope) + "</ul>")

    inventory = diff.get("inventoryChanges") or {}
    access = []
    for ref in inventory.get("accessRestored") or []:
        access.append(f"<li>Access restored: {text(ref)} is readable from this account again.</li>")
    for ref in inventory.get("accessLost") or []:
        access.append(
            f"<li>Access lost: {text(ref)} could not be read this run; it was readable at "
            f"the baseline.</li>"
        )
    for ref in inventory.get("reopened") or []:
        access.append(f"<li>Reopened: {text(ref)} was closed at the baseline and is open again.</li>")
    if access:
        out.append("<ul>" + "".join(access) + "</ul>")
    return out


# --- 7. collection scope -------------------------------------------------


def scope_block(assembly):
    manifest = assembly.get("manifest") or {}
    children = manifest.get("children") or []
    epics = manifest.get("epics") or []
    sources = ", ".join(assembly.get("requirementSourcesChecked") or ["description", "sub-tasks"])

    out = ["<h3>Collection scope and limitations</h3>", "<ul>"]
    out.append(f"<li>Jira sources read for requirements: {text(sources)}.</li>")
    if _observed(manifest):
        repos = sorted({child["ref"].split("#")[0] for child in children if child.get("ref")})
        out.append(
            f"<li>Traversed {text(util.pluralize(len(epics), 'epic'))}, "
            f"{text(util.pluralize(len(children), 'child issue'))} across "
            f"{text(util.pluralize(len(repos), 'repository', 'repositories'))}"
            + (f": {text(', '.join(repos))}" if repos else "")
            + ".</li>"
        )
    else:
        out.append(
            "<li>No upstream epic was read ("
            + text(manifest.get("unobservedReason") or "reason not recorded")
            + "). Upstream coverage is unassessable, not absent.</li>"
        )
    for entry in manifest.get("untraversed") or []:
        title = f" {EMDASH} {entry['title']}" if entry.get("title") else ""
        out.append(
            f"<li><strong>Nested epic not traversed:</strong> "
            f"{ref_anchor(entry.get('ref'))}{text(title)}. "
            f"{text(_sentence(entry.get('reason')) or 'No reason recorded')}.</li>"
        )
    for note in manifest.get("traversalNotes") or []:
        out.append(f"<li>Traversal: {text(note)}</li>")
    for entry in manifest.get("access") or []:
        if entry.get("status") != "readable":
            out.append(
                f"<li>Not readable: {text(entry.get('ref'))} ({text(entry.get('status'))}) "
                f"{EMDASH} {text(entry.get('detail') or 'no detail recorded')}.</li>"
            )
    out.append(
        "<li>Evidence basis: issue and pull-request metadata, changed-file lists, and CI check "
        "results. No diffs were read, so a changed file or a passing job locates the work; it "
        "does not by itself verify a behaviour. <em>Documented</em> and <em>test present</em> "
        "are not states this collection can distinguish and are never reported.</li>"
    )
    out.append(
        "<li>No downstream build, payload, or qualification run was inspected. Downstream "
        "state is <em>Not inspected</em> unless a source that was read says otherwise.</li>"
    )
    out.append(
        f"<li>Assessment generated {text(_date(assembly.get('generatedAt')) or 'date not recorded')}; "
        f"upstream collected {text(_date(manifest.get('collectedAt')) or 'timestamp not recorded')}.</li>"
    )
    out.append("</ul>")
    return out


def footer_section(assembly, rules_version, schema_version):
    out = [
        '<section class="foot" aria-labelledby="h-foot">',
        '<h2 id="h-foot" hidden>Changes and collection scope</h2>',
        '<div class="grid-2">',
        "<div>",
    ]
    out.extend(changes_block(assembly))
    out.append("</div><div>")
    out.extend(scope_block(assembly))
    out.append("</div></div>")
    epics = ", ".join(
        mapping.get("ref") or "" for mapping in assembly.get("mappings") or []
    ).strip(", ")
    marker = render_mod.MARKER + (f" from {epics}" if epics else "")
    out.append(
        f'<p class="colophon">{text(marker)}. Read-only against GitHub; no Jira issues were '
        f"created. Rules version {text(rules_version)}, snapshot schema {text(schema_version)}. "
        "Unweighted counts of requirements and child issues: not a measure of effort completed, "
        "work remaining, or release readiness.</p>"
    )
    out.append("</section>")
    return out


# --- document ------------------------------------------------------------


def render(assembly, tallied=None, rules_version=None, schema_version=None):
    """The whole standalone document as one string."""
    from . import snapshots as snapshots_mod

    computed = assembly.get("metrics") or render_mod.compute_metrics(assembly)
    tallied = tallied or outcomes_mod.tally(assembly.get("requirements") or [])
    jira = assembly.get("jira") or {}
    title = f"{jira.get('key') or 'Rollup'} {EMDASH} full assessment"

    body = []
    body.extend(header_block(assembly))
    body.extend(banner_block(assembly, computed))
    body.extend(overview_section(assembly, tallied, computed))
    body.extend(decisions_section(assembly))
    body.extend(review_section(assembly))
    body.extend(
        footer_section(
            assembly,
            rules_version or snapshots_mod.RULES_VERSION,
            schema_version or snapshots_mod.SCHEMA_VERSION,
        )
    )

    document = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{text(title)}</title>",
        "<style>" + htmlassets.CSS + "</style>",
        "</head>",
        "<body>",
        '<main class="wrap">',
        *body,
        "</main>",
        "<script>" + htmlassets.JS + "</script>",
        "</body>",
        "</html>",
        "",
    ]
    return "\n".join(part for part in document if part != "")
