---
name: jira-github-rollup
description: Use when asked to summarize, roll up, or report upstream GitHub development status for an existing Jira requirement (e.g. "roll up RHOAIENG-1234", "what's the upstream status of this epic", "draft a status update for this Jira"). Reads GitHub epic links already present on the Jira issue, follows child issues and their pull requests across repositories, and drafts a concise rollup for that same Jira issue. Read-only against GitHub; never creates mirrored Jira issues.
---

# Jira ← GitHub Development Rollup

Draft a development-status rollup for an **existing** Jira requirement by following
the GitHub epic links a human already placed on that issue.

## Core constraint — read this first

**Never create Jira issues.** This skill does not mirror GitHub issues into Jira,
does not create sub-tasks, and does not create linked issues. The only write
operation it may perform is adding or updating a comment (or a designated
description section) on the **one** Jira issue the user named — and only after
showing the draft and getting explicit approval.

If the user asks for mirrored Jira issues, say that this skill deliberately does
not do that and offer the rollup instead.

## When this applies

The intended workflow is:

1. A human creates or identifies a GitHub epic corresponding to a downstream Jira
   requirement.
2. The human links that epic from the Jira issue (see
   `examples/jira-link-section.md` in this repo for the link conventions).
3. This skill reads those links and reports what has actually happened upstream.

Step 1 and 2 are **manual and stay manual.** This skill starts at step 3.

## Procedure

### 1. Resolve the Jira issue

Fetch the issue with the Atlassian MCP tools (`getJiraIssue`). Capture:

- key, summary, status, fix version(s), assignee
- description body and any remote/web links
- existing comments, so the rollup does not repeat an unchanged update

If the user gave a URL rather than a key, extract the key from it.

### 2. Find the GitHub epic links

Scan, in this order, stopping when you find at least one epic:

1. A dedicated section in the description (the conventional heading is
   `## Upstream Development` — see `examples/jira-link-section.md`).
2. Jira remote links / web links pointing at `github.com`.
3. Any `github.com/<org>/<repo>/issues/<n>` URL elsewhere in the description.
4. Comments, most recent first.

Normalize every hit to `<org>/<repo>#<number>`. De-duplicate.

**If no GitHub link is found, stop.** Report that the Jira has no upstream link
and ask the user to add one. Do not guess an epic by searching GitHub for
title matches — a wrong epic produces a confidently wrong rollup.

**If multiple unrelated epics are found**, list them and ask which to include
rather than silently merging them.

### 3. Traverse the epic

For each epic, use `gh` (read-only). Child issues can be expressed several ways;
check all of them and union the results:

```bash
# Epic body + metadata
gh issue view <n> --repo <org>/<repo> --json number,title,state,body,labels,assignees,url,closedAt

# Native sub-issues (GitHub Issues hierarchy)
gh api repos/<org>/<repo>/issues/<n>/sub_issues --paginate

# Cross-references and timeline links (catches "tracked by", mentions, transfers)
gh api repos/<org>/<repo>/issues/<n>/timeline --paginate
```

Also parse the epic body for task-list references (`- [ ] org/repo#123` or full
URLs) — many upstream epics track children that way rather than natively.

Children frequently live in **different repositories** than the epic. Always
carry the owning repo with each child; never assume the epic's repo.

### 4. Resolve pull requests per child

For each child issue, find PRs that close or reference it:

```bash
gh api repos/<org>/<repo>/issues/<n>/timeline --paginate \
  --jq '[.[] | select(.event=="cross-referenced" or .event=="connected") | .source.issue.html_url] | unique'

gh pr view <pr> --repo <org>/<repo> \
  --json number,title,state,isDraft,merged,mergedAt,author,url,baseRefName
```

A `gh search prs` fallback is acceptable when the timeline yields nothing:

```bash
gh search prs "<org>/<repo>#<n>" --json number,title,state,url,repository
```

Record for each PR: repo, number, title, state (open / draft / merged / closed),
merge date, author, and target branch. Target branch matters — a PR merged to a
release branch is a different signal than one merged to `main`.

### 5. Assess status honestly

Derive the rollup state from evidence, not from optimism:

| Signal | Report as |
| --- | --- |
| All children closed, PRs merged | Complete |
| Some children closed, PRs merged, others open | In progress, with counts |
| Children open, PRs open or draft | In progress, early |
| Children open, no PRs, no recent activity | Not started / stalled — say which |
| Child closed with no merged PR | Flag it — closed-as-wontfix or moved |

Call out explicitly:

- Children with no activity in 30+ days
- PRs open 14+ days without review
- Children whose repo differs from the epic's repo (cross-repo dependency)
- Any child that is itself an epic (nested — note it, do not recurse past one level
  without asking)

Never infer a completion percentage that the evidence does not support, and never
describe work as "done" because an issue is closed if no PR merged.

### 6. Draft the rollup

Follow `references/rollup-format.md` for the exact structure and tone. Keep it
short — a rollup that runs longer than a screen will not be read. The audience is
a program manager scanning for risk, not an engineer reading a changelog.

Include a generation timestamp and the epic(s) the rollup was derived from, so a
reader can tell how stale it is and verify the source.

### 7. Post only after approval

Show the draft and ask whether to post. On approval, add it as a **comment** on the
original Jira issue via `addOrEditJiraIssueComment`.

If a prior rollup comment from this skill exists (identified by its trailing
marker line), offer to edit that comment in place instead of appending a new one,
so the issue does not accumulate near-identical updates.

Posting to Jira is outward-facing and visible to the whole project — never do it
without the user saying yes to that specific draft.

## Failure modes to avoid

- **Inventing an epic link.** No link means stop and ask, not search-and-guess.
- **Dropping cross-repo children.** The epic's repo is not the children's repo.
- **Reporting closed as shipped.** Closed without a merged PR is a flag, not a win.
- **Creating Jira issues.** See the constraint at the top.
- **Silent staleness.** Always timestamp; always name the source epic.
