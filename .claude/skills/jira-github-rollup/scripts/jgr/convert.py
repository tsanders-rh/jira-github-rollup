"""Convert the approved GFM draft to the markup the Jira site accepts.

Called once, at post time, on a draft the user has already approved. The
conversion is mechanical and lossless in the ways that matter: section order,
section names, verbatim criterion text, source keys, and the marker-line
wording survive every target. Only the markup changes.

Choosing the target is not this module's job. The skill reads what
`addOrEditJiraIssueComment` documents as its input format and passes the
answer in; `plain` is the fallback when that is silent or ambiguous, because
it is the only rendering that degrades gracefully everywhere.

On a Jira Cloud site reached through the Atlassian MCP server, that tool takes
Markdown by default and HTML when `contentFormat: "html"` is set. Wiki markup
is not one of its input formats, so `gfm` is the ordinary answer there and
`html` is the fallback if a heading, table or link does not survive. `wiki`
remains for sites and tools that do take it.
"""

from __future__ import annotations

import html as html_mod
import re

LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
ITALIC = re.compile(r"(?<!\w)_([^_]+)_(?!\w)")
CODE = re.compile(r"`([^`]+)`")
SEPARATOR = re.compile(r"^\|(?:\s*:?-{2,}:?\s*\|)+$")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET = re.compile(r"^(\s*)[-*]\s+(.*)$")

COVERAGE_HEADER = [
    "Requirement",
    "Outcome",
    "Evidence",
    "Evidence state",
    "Coverage",
    "Gap / next validation step",
]


def _cells(line):
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    # Split on unescaped pipes only; a cell may legitimately contain `\|`.
    parts = re.split(r"(?<!\\)\|", inner)
    return [part.strip().replace("\\|", "|") for part in parts]


def _inline_wiki(text):
    text = LINK.sub(lambda m: f"[{m.group(1)}|{m.group(2)}]", text)
    text = BOLD.sub(r"*\1*", text)
    text = CODE.sub(r"{{\1}}", text)
    return text


def _inline_plain(text):
    text = LINK.sub(lambda m: m.group(2) if m.group(1) in m.group(2) else f"{m.group(1)} ({m.group(2)})", text)
    text = BOLD.sub(r"\1", text)
    text = CODE.sub(r"\1", text)
    text = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", text)
    return text


def _blocks(lines):
    """Group the draft into tables and runs of non-table lines."""
    grouped, buffer, table = [], [], []
    for line in lines:
        if line.lstrip().startswith("|"):
            if buffer:
                grouped.append(("text", buffer))
                buffer = []
            table.append(line)
        else:
            if table:
                grouped.append(("table", table))
                table = []
            buffer.append(line)
    if table:
        grouped.append(("table", table))
    if buffer:
        grouped.append(("text", buffer))
    return grouped


def to_wiki(markdown):
    out = []
    for kind, block in _blocks(markdown.splitlines()):
        if kind == "table":
            rows = [row for row in block if not SEPARATOR.match(row.strip())]
            for index, row in enumerate(rows):
                cells = [_inline_wiki(cell) for cell in _cells(row)]
                if index == 0:
                    out.append("|| " + " || ".join(cells) + " ||")
                else:
                    out.append("| " + " | ".join(cells) + " |")
            continue
        for line in block:
            stripped = line.strip()
            if stripped == "---":
                out.append("----")
                continue
            heading = HEADING.match(stripped)
            if heading:
                level = min(len(heading.group(1)), 6)
                out.append(f"h{level}. {_inline_wiki(heading.group(2))}")
                continue
            out.append(_inline_wiki(line))
    return "\n".join(out).rstrip() + "\n"


def _coverage_blocks(rows):
    out = []
    for row in rows[1:]:
        cells = _cells(row)
        if len(cells) < 6:
            out.append(_inline_plain(" | ".join(cells)))
            continue
        requirement, outcome, evidence, state, coverage, gap = (
            _inline_plain(c) for c in cells[:6]
        )
        out.append(requirement)
        out.append(f"  Outcome: {outcome}")
        out.append(f"  Evidence: {evidence}")
        out.append(f"  State: {state}")
        out.append(f"  Coverage: {coverage}")
        out.append(f"  Gap: {gap}")
        out.append("")
    while out and not out[-1]:
        out.pop()
    return out


def to_plain(markdown):
    out = []
    for kind, block in _blocks(markdown.splitlines()):
        if kind == "table":
            rows = [row for row in block if not SEPARATOR.match(row.strip())]
            if not rows:
                continue
            header = _cells(rows[0])
            if header[: len(COVERAGE_HEADER)] == COVERAGE_HEADER:
                out.extend(_coverage_blocks(rows))
                continue
            for row in rows[1:]:
                cells = [_inline_plain(cell) for cell in _cells(row)]
                labelled = [
                    f"{label}: {value}"
                    for label, value in zip(header[1:], cells[1:])
                    if value and value not in ("—", "-")
                ]
                out.append(" — ".join([cells[0]] + labelled) if labelled else cells[0])
            continue
        for line in block:
            stripped = line.strip()
            if stripped == "---":
                out.append("")
                continue
            heading = HEADING.match(stripped)
            if heading:
                out.append(_inline_plain(heading.group(2)))
                continue
            out.append(_inline_plain(line))
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n"


def _inline_html(text):
    """Inline markup to the subset Jira's HTML importer documents.

    Escaping happens first and link hrefs are re-inserted afterwards, so a
    criterion containing `<` or `&` cannot close a tag it was never part of.
    """
    escaped = html_mod.escape(text, quote=False)
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        lambda m: '<a href="{}">{}</a>'.format(
            html_mod.escape(m.group(2), quote=True), m.group(1)
        ),
        escaped,
    )
    escaped = BOLD.sub(r"<strong>\1</strong>", escaped)
    escaped = CODE.sub(r"<code>\1</code>", escaped)
    escaped = ITALIC.sub(r"<em>\1</em>", escaped)
    return escaped


def to_html(markdown):
    """The documented Jira HTML shapes: h1-h6, p, ul/li, table/thead/tbody, a, hr.

    Nothing outside that set is emitted. Layout elements in particular are
    refused by the importer, and a comment that fails to import is worse than
    one that renders plainly.
    """
    out, bullets = [], []

    def flush():
        if bullets:
            out.append("<ul>" + "".join(f"<li>{item}</li>" for item in bullets) + "</ul>")
            bullets.clear()

    for kind, block in _blocks(markdown.splitlines()):
        if kind == "table":
            flush()
            rows = [row for row in block if not SEPARATOR.match(row.strip())]
            if not rows:
                continue
            head = "".join(f"<th>{_inline_html(c)}</th>" for c in _cells(rows[0]))
            body = "".join(
                "<tr>" + "".join(f"<td>{_inline_html(c)}</td>" for c in _cells(row)) + "</tr>"
                for row in rows[1:]
            )
            out.append(f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
            continue
        for line in block:
            stripped = line.strip()
            if not stripped:
                flush()
                continue
            if stripped == "---":
                flush()
                out.append("<hr/>")
                continue
            heading = HEADING.match(stripped)
            if heading:
                flush()
                level = min(len(heading.group(1)), 6)
                out.append(f"<h{level}>{_inline_html(heading.group(2))}</h{level}>")
                continue
            bullet = BULLET.match(line)
            if bullet:
                bullets.append(_inline_html(bullet.group(2)))
                continue
            flush()
            out.append(f"<p>{_inline_html(stripped)}</p>")
    flush()
    return "\n".join(out) + "\n"


def convert(markdown, target):
    if target == "wiki":
        return to_wiki(markdown)
    if target == "html":
        return to_html(markdown)
    if target in ("plain", "adf", "text"):
        return to_plain(markdown)
    if target in ("gfm", "markdown"):
        return markdown
    raise ValueError(f"unknown target format {target!r}")
