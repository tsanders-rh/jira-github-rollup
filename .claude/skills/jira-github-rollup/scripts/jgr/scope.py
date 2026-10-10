"""Why nothing upstream was observed, and what that means for the report.

"No link was recorded" and "the link is there but we were refused" are
different findings with different owners. One needs someone to add a link; the
other needs someone to grant access or supply a credential, and the link is
already correct. Reporting the second as `upstream mapping missing` sends the
reader to fix something that is not broken, and quietly reads as "nobody has
started this" when the work may be finished.

Every phrase a report uses about an unobserved run is derived from one kind,
recorded in the manifest as `unobservedKind`. A manifest with no kind - any
snapshot written before this existed - is treated as `no-mapping`, which is
what those runs already said.
"""

from __future__ import annotations

NO_MAPPING = "no-mapping"
ACCESS_DENIED = "access-denied"
NOT_FOUND = "not-found"
UNREADABLE = "unreadable"

AUTO_FILL = "unable-to-assess-unobserved"
# What `diff` emitted before the kinds existed. Still accepted so a diff from
# an older run does not fall through to "no assessment supplied".
LEGACY_AUTO_FILL = "unable-to-assess-missing-mapping"

_KINDS = {
    NO_MAPPING: {
        "reason": "no upstream mapping recorded on the Jira issue",
        "status": "upstream mapping missing",
        "gap": "Link the GitHub epic on the Jira issue; this requirement cannot "
        "be assessed until then.",
    },
    ACCESS_DENIED: {
        "reason": "the linked epic exists but access to it was denied",
        "status": "upstream access denied",
        "gap": "Grant the credential this runs under read access to the linked "
        "GitHub epic; the link is correct and this requirement cannot be "
        "assessed until the epic can be read.",
    },
    NOT_FOUND: {
        "reason": "the linked epic could not be found",
        "status": "upstream epic not found",
        "gap": "Correct the GitHub link on the Jira issue; the epic it names "
        "could not be found, so this requirement cannot be assessed.",
    },
    UNREADABLE: {
        "reason": "the linked epic could not be read",
        "status": "upstream epic unreadable",
        "gap": "Re-run collection against the linked GitHub epic; it could not "
        "be read this run, so this requirement cannot be assessed.",
    },
}


def _entry(kind):
    return _KINDS.get(kind or NO_MAPPING, _KINDS[NO_MAPPING])


def reason(kind):
    """The phrase stored as `unobservedReason` and quoted in the scope section."""
    return _entry(kind)["reason"]


def status(kind):
    """What follows `Unknown -` on the status line."""
    return _entry(kind)["status"]


def gap(kind):
    """The action in the Gap column of every auto-filled requirement row."""
    return _entry(kind)["gap"]


def link_present(kind):
    """True when a human-created link was found and the failure is downstream of it.

    The distinction the whole module exists for: with a link present, an
    unverified row is about access, not about tracking.
    """
    return (kind or NO_MAPPING) != NO_MAPPING


def needed(kind, jira_key, refs=None):
    """Bullets for "What is needed to complete this assessment"."""
    named = ", ".join(refs or []) or "the linked epic"
    if not link_present(kind):
        return [
            f"- The GitHub epic issue URL for this requirement, recorded on {jira_key} in an",
            "  `Upstream Development` description section or as a web link labelled",
            "  `Upstream epic`. Several URLs if the requirement spans more than one epic.",
            "- Alternatively, the URL supplied directly in the request.",
            "- Nothing else is blocking: the requirements were read successfully and will be",
            "  assessed against whatever epic is supplied.",
        ]
    if kind == ACCESS_DENIED:
        return [
            f"- Read access to {named}. The link on {jira_key} is correct; the credential",
            "  `gh` authenticated with was refused by the repository or its organisation.",
            "- A credential the organisation accepts, if it restricts the token type in use.",
            "- Nothing else is blocking: the requirements were read successfully and will be",
            "  assessed as soon as the epic can be read.",
        ]
    if kind == NOT_FOUND:
        return [
            f"- A working GitHub epic URL on {jira_key}. The recorded link points at {named},",
            "  which could not be found - it may have been moved, deleted, or mistyped.",
            "- Nothing else is blocking: the requirements were read successfully and will be",
            "  assessed against whatever epic is supplied.",
        ]
    return [
        f"- A successful read of {named}. The link on {jira_key} is present, but the epic",
        "  could not be retrieved this run; re-run once the cause is known.",
        "- Nothing else is blocking: the requirements were read successfully and will be",
        "  assessed as soon as the epic can be read.",
    ]
