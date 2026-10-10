"""Turning refs into clickable links, and keeping unpublishable things out.

Two jobs. Build a real URL for an artifact this run actually saw, and refuse to
let anything into publishable text that a Jira reader cannot follow - a local
filesystem path, a `file://` URL, or a cache directory. The second job matters
more than it sounds: the manifest is full of cache paths, and a renderer that
interpolated one into a comment would publish the shape of someone's home
directory to a whole project.
"""

from __future__ import annotations

import re

GITHUB = "https://github.com"

REF = re.compile(r"^(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)#(?P<number>\d+)$")

# Anything that would be meaningless or disclosing in a Jira comment.
UNPUBLISHABLE = re.compile(
    r"(?:file://)"
    r"|(?:\B~/[\w./-]+)"
    r"|(?:(?<![\w/])/(?:Users|home|var|tmp|private|opt)/[\w./-]+)",
    re.I,
)


def url_for(ref, kind=None):
    """`org/repo#412` -> a github.com URL, or None when the ref is not one.

    GitHub redirects `/issues/<n>` to `/pull/<n>` when the number is a PR, so
    the issue form is safe either way; `kind` only makes the link honest about
    what it points at before you click it.
    """
    if not isinstance(ref, str):
        return None
    match = REF.match(ref.strip())
    if not match:
        return None
    segment = "pull" if (kind or "").lower() == "pr" else "issues"
    return f"{GITHUB}/{match['owner']}/{match['repo']}/{segment}/{match['number']}"


def link(ref, kind=None, label=None):
    """A Markdown link for a ref, or the bare text when no URL can be built.

    Never invents a URL. A ref that does not parse is returned as written -
    an unlinked true string beats a linked guess.
    """
    url = url_for(ref, kind)
    text = label or ref
    return f"[{text}]({url})" if url else str(text)


def short(ref):
    """`example-org/example-gateway#1605` -> `example-gateway#1605`, for link labels inside prose."""
    match = REF.match(str(ref).strip())
    if not match:
        return str(ref)
    return f"{match['repo']}#{match['number']}"


def describe(ref, kind=None):
    """A descriptive link label: `Streaming enforcement PR #1605`, not a bare URL."""
    noun = "PR" if (kind or "").lower() == "pr" else "issue"
    return link(ref, kind, label=f"{noun} {short(ref)}")


def epic_link(mapping):
    url = mapping.get("url") or url_for(mapping.get("ref") or mapping.get("epic"))
    label = mapping.get("title") or mapping.get("ref") or mapping.get("epic")
    ref = mapping.get("ref") or mapping.get("epic")
    if not url:
        return str(label)
    text = f"{ref} — {label}" if label and label != ref else str(ref)
    return f"[{text}]({url})"


def jira_url(site, key):
    """A Jira browse URL, only when a site base is actually known."""
    if not site or not key:
        return None
    return f"{str(site).rstrip('/')}/browse/{key}"


def jira_link(key, site=None, criterion=None):
    """Link the parent Jira and name the criterion: `RHOAIENG-1234 SC5`.

    Criteria have no individual anchors in Jira, so the criterion id is carried
    in the link text rather than pretending to a fragment that would not
    resolve.
    """
    text = f"{key} {criterion}" if criterion else str(key)
    url = jira_url(site, key)
    return f"[{text}]({url})" if url else text


BARE_REF = re.compile(r"(?<![\w/\[(])([\w.-]+/[\w.-]+#\d+)(?![\w\])])")


def linkify(text):
    """Link every bare `org/repo#n` in a plain string, leaving the rest alone.

    For short machine-written strings - a traversal note, a status line. Not
    for model prose, where a dozen incidental mentions would turn a sentence
    into a link farm and bury the one link that matters.
    """
    if not text:
        return text
    return BARE_REF.sub(lambda m: link(m.group(1)), str(text))


def unpublishable(text):
    """Every local path or file URL in a string. Empty list means safe to post."""
    return [match.group(0) for match in UNPUBLISHABLE.finditer(text or "")]


def safe_url(url):
    """A URL only if it is an absolute `http(s)` one. Otherwise None.

    An allow-list, not a deny-list, and it governs two different hazards.

    In the HTML report, a ref carried out of an issue body could be
    `javascript:` or `data:`, and either in an `href` is script execution in a
    file the reader was told was a report.

    In the Jira summary, the hazard is quieter: a relative path like
    `full-assessment.html` is neither a local path nor a file URL, so
    `unpublishable` passes it, and it renders as a link that resolves against
    the Jira host and 404s for everyone. A local HTML file is not a durable
    link and must not be published as one.
    """
    if not url:
        return None
    candidate = str(url).strip()
    lowered = candidate.lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        return None
    if any(char in candidate for char in "\n\r\t"):
        return None
    return candidate
