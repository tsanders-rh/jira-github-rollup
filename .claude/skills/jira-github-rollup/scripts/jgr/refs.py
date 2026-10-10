"""Normalize and de-duplicate the GitHub references found on a Jira issue.

Input is whatever the skill read out of Jira through MCP, as structured data.
Output sorts every reference into the explicit and incidental tiers that
SKILL.md step "Map" acts on, keeps each one attributable to where it was found,
and decides whether the mapping is unambiguous enough to proceed without asking.

The script never invents a reference and never searches GitHub. It only reads
the text it was handed.
"""

from __future__ import annotations

import re

ISSUE_URL = re.compile(
    r"https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+)/issues/(\d+)", re.I
)
PR_URL = re.compile(
    r"https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+)/(?:pull|pulls)/(\d+)", re.I
)
PROJECT_URL = re.compile(
    r"https?://(?:www\.)?github\.com/(?:orgs/)?([\w.-]+)(?:/([\w.-]+))?/(projects|milestone|milestones)/(\d+)",
    re.I,
)
REPO_URL = re.compile(
    r"https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+)/?(?:\s|$|[)\]>,;\"'])", re.I
)
SHORTHAND = re.compile(r"\b([\w.-]+)/([\w.-]+)#(\d+)\b")

UPSTREAM_SECTION = re.compile(r"upstream\s+(development|work|epic)", re.I)
UPSTREAM_LABEL = re.compile(r"upstream", re.I)

# Tier order: lower sorts first and wins when the same ref is found twice.
SOURCE_RANK = {
    "user-supplied": 0,
    "upstream-development-section": 1,
    "labelled-web-link": 2,
    "incidental-description": 3,
    "incidental-comment": 4,
}
EXPLICIT_SOURCES = {"user-supplied", "upstream-development-section", "labelled-web-link"}


def _issue_ref(org, repo, number):
    return f"{org}/{repo}#{number}"


def _issue_url(org, repo, number):
    return f"https://github.com/{org}/{repo}/issues/{number}"


def scan(text):
    """Pull every GitHub reference out of one blob of text.

    Returns (issues, non_issues). `issues` are candidate epics; `non_issues`
    are PRs, boards, milestones, and bare repos, which have no children to
    traverse and are reported rather than used.
    """
    if not text:
        return [], []
    issues, others, seen = [], [], set()

    for org, repo, number in ISSUE_URL.findall(text):
        ref = _issue_ref(org, repo, number)
        if ref not in seen:
            seen.add(ref)
            issues.append({"ref": ref, "url": _issue_url(org, repo, number)})

    for org, repo, number in SHORTHAND.findall(text):
        # A task-list line `- [ ] org/repo#123` is a child reference, which is
        # still a GitHub reference on the Jira and still worth reporting.
        ref = _issue_ref(org, repo, number)
        if ref not in seen:
            seen.add(ref)
            issues.append({"ref": ref, "url": _issue_url(org, repo, number)})

    for org, repo, number in PR_URL.findall(text):
        others.append(
            {
                "ref": f"{org}/{repo}!{number}",
                "url": f"https://github.com/{org}/{repo}/pull/{number}",
                "kind": "pull-request",
            }
        )
    for org, repo, kind, number in PROJECT_URL.findall(text):
        others.append(
            {
                "ref": f"{org}/{repo or '-'} {kind} {number}".strip(),
                "url": None,
                "kind": "project-board" if kind.startswith("project") else "milestone",
            }
        )
    stripped = ISSUE_URL.sub(" ", PR_URL.sub(" ", PROJECT_URL.sub(" ", text)))
    for org, repo in REPO_URL.findall(stripped + "\n"):
        others.append(
            {"ref": f"{org}/{repo}", "url": f"https://github.com/{org}/{repo}", "kind": "repository"}
        )
    return issues, others


def collect(payload):
    """Sort every reference on the issue into tiers.

    payload keys (all optional except jiraKey):
      jiraKey            the issue the rollup is about
      description        full description text
      descriptionSections  [{heading, text}]
      webLinks           [{label, url}]
      comments           [{id, created, body}] - newest first is preferred
      userSupplied       [url or org/repo#n] given in the conversation
    """
    hits = {}
    non_issues = []
    notes = []

    def record(issue, source, found_in):
        entry = hits.setdefault(
            issue["ref"],
            {"ref": issue["ref"], "url": issue["url"], "linkSource": source, "foundIn": []},
        )
        entry["foundIn"].append({"source": source, "detail": found_in})
        if SOURCE_RANK[source] < SOURCE_RANK[entry["linkSource"]]:
            entry["linkSource"] = source

    for raw in payload.get("userSupplied") or []:
        issues, others = scan(raw if raw.startswith("http") else raw)
        for issue in issues:
            record(issue, "user-supplied", "supplied in the conversation")
        non_issues.extend(others)

    sections = payload.get("descriptionSections") or []
    upstream_section_text = []
    for section in sections:
        heading = section.get("heading") or ""
        issues, others = scan(section.get("text") or "")
        if UPSTREAM_SECTION.search(heading):
            upstream_section_text.append(section.get("text") or "")
            for issue in issues:
                record(issue, "upstream-development-section", f"description section '{heading}'")
            non_issues.extend(others)
        else:
            for issue in issues:
                record(issue, "incidental-description", f"description section '{heading}'")

    # The whole description, for sections the caller did not split out.
    issues, others = scan(payload.get("description") or "")
    for issue in issues:
        if issue["ref"] in hits:
            continue
        in_upstream = any(issue["ref"] in text or issue["url"] in text for text in upstream_section_text)
        source = "upstream-development-section" if in_upstream else "incidental-description"
        record(issue, source, "issue description")
    non_issues.extend(others)

    for link in payload.get("webLinks") or []:
        label = link.get("label") or ""
        issues, others = scan(link.get("url") or "")
        source = "labelled-web-link" if UPSTREAM_LABEL.search(label) else "incidental-description"
        detail = f"web link labelled '{label}'" if label else "unlabelled web link"
        for issue in issues:
            record(issue, source, detail)
        non_issues.extend(others)

    comments = payload.get("comments") or []
    for comment in comments:
        issues, others = scan(comment.get("body") or "")
        when = comment.get("created") or "unknown date"
        for issue in issues:
            record(issue, "incidental-comment", f"comment {comment.get('id', '?')} ({when})")
        non_issues.extend(others)

    explicit = sorted(
        (h for h in hits.values() if h["linkSource"] in EXPLICIT_SOURCES),
        key=lambda h: (SOURCE_RANK[h["linkSource"]], h["ref"]),
    )
    incidental = sorted(
        (h for h in hits.values() if h["linkSource"] not in EXPLICIT_SOURCES),
        key=lambda h: (SOURCE_RANK[h["linkSource"]], h["ref"]),
    )

    seen_other = set()
    deduped_others = []
    for other in non_issues:
        key = (other["kind"], other["ref"])
        if key not in seen_other:
            seen_other.add(key)
            deduped_others.append(other)

    question = None
    epics = list(explicit)
    if explicit and incidental:
        question = {
            "kind": "incidental-extras",
            "ask": "Roll up the explicitly linked epics. These GitHub issues also appear on the Jira but are not labelled as the upstream mapping - are any of them in scope?",
            "options": incidental,
        }
    elif not explicit and len(incidental) == 1:
        epics = list(incidental)
        notes.append(
            "The only GitHub reference on the Jira is unlabelled "
            f"({incidental[0]['foundIn'][0]['detail']}); say so in the draft and ask for confirmation."
        )
    elif not explicit and len(incidental) > 1:
        epics = []
        question = {
            "kind": "incidental-multiple",
            "ask": "No labelled upstream mapping was found. Several GitHub issues appear on the Jira - which are in scope?",
            "options": incidental,
        }

    if not epics and not question and deduped_others:
        kinds = ", ".join(sorted({o["kind"] for o in deduped_others}))
        notes.append(
            f"GitHub references were found but none is an issue ({kinds}). "
            "A pull request, board, milestone, or bare repository has no children to traverse - "
            "ask for the epic issue URL."
        )

    return {
        "jiraKey": payload.get("jiraKey"),
        "epics": epics,
        "explicit": explicit,
        "incidental": incidental,
        "nonIssueReferences": deduped_others,
        "question": question,
        "notes": notes,
        "commentsScanned": len(comments),
        "mappingFound": bool(epics),
    }
