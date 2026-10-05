---
name: jira-github-rollup
description: Use when asked to summarize, roll up, or report upstream GitHub development status for an existing Jira requirement, or to check whether its acceptance criteria are covered upstream (e.g. "roll up RHOAIENG-1234", "what's the upstream status of this epic", "draft a status update for this Jira", "are the acceptance criteria on RHOAIENG-1234 covered", "which requirements have no upstream evidence"). Reads GitHub epic links already present on the Jira issue, follows child issues and their pull requests across repositories, maps each acceptance criterion to the upstream evidence for it, and drafts a concise rollup for that same Jira issue. Read-only against GitHub; never creates mirrored Jira issues.
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

Acceptance-criteria analysis may **read** child Jira requirements, but that does
not widen the write surface: the comment still goes on the one issue the user
named, and nothing — not a comment, not a status transition — is written to the
children.

If the user asks for mirrored Jira issues, say that this skill deliberately does
not do that and offer the rollup instead.

## When this applies

The intended workflow is:

1. A human creates or identifies a GitHub epic corresponding to a downstream Jira
   requirement.
2. The human links that epic from the Jira issue (see
   `examples/jira-link-section.md` in this repo for the link conventions).
3. This skill reads those links and reports what has actually happened upstream.

Workflow steps 1 and 2 are **manual and stay manual.** This skill starts at
workflow step 3 — which is the Procedure below, numbered separately.

Acceptance-criteria coverage rides on the same premise: the criteria are
whatever the Jira says they are, and the mapping between a criterion and
upstream work is only as good as the links a human placed. The skill reports
what the evidence supports and flags the rest for owner review.

## Procedure

### 1. Resolve the Jira issue

Fetch the issue with the Atlassian MCP tools (`getJiraIssue`). Capture:

- key, summary, status, fix version(s), assignee
- description body and any remote/web links
- existing comments, so the rollup does not repeat an unchanged update
- sub-tasks and child requirements (`fields.subtasks`, `fields.issuelinks`)

The default MCP response is compact and omits custom fields. If the site keeps
acceptance criteria in a custom field rather than the description, re-fetch with
`view: evidence` (or `full`) and read `fields.customFields` — custom field IDs
differ per site, so do not hard-code one.

If the user gave a URL rather than a key, extract the key from it.

### 2. Extract the acceptance criteria

Collect the criteria this rollup will be judged against, **verbatim**. Look in
this order and union the results:

1. A description section headed `Acceptance Criteria`, `Success Criteria`, or
   `Definition of Done`.
2. A dedicated acceptance-criteria custom field, if the site has one.
3. Gherkin blocks (`Given / When / Then`) anywhere in the description.
4. The same three sources on **child requirements** — sub-tasks, and issues
   linked as a child of the named issue. One level only.

Rules:

- **Quote the criterion as written.** Do not normalize, shorten, or rephrase it.
  If it is too long for a table cell, quote verbatim to a sentence boundary and
  append `…` — never paraphrase.
- Assign each one a stable ID in order of appearance, **scoped to its source
  issue** and rendered `AC<n> (SOURCE-KEY)`. A parent and a child requirement
  therefore both start at `AC1`, and the key is what tells the two rows apart.
  A criterion inherited from a child is not the parent's criterion.
- **Never synthesize a criterion.** Not from the summary, not from prose in the
  description, and above all not from a GitHub issue title. Only text the Jira
  presents as a criterion is a criterion.
- **No criteria found:** say so, name the sources you checked, and continue with
  the rest of the rollup. The coverage section then reports that there is nothing
  to assess against — it does not get filled with inferred criteria.
- **Ambiguous criterion** — one that is not checkable as written (`performance
  should be acceptable`): keep it verbatim, assess it `Unable to assess`, and ask
  the owner to restate it.

### 3. Find the GitHub epic links

Scan, in this order, stopping when you find at least one epic:

1. A dedicated section in the description (the conventional heading text is
   `Upstream Development` — see `examples/jira-link-section.md`).
2. Jira remote links / web links pointing at `github.com`.
3. Any `github.com/<org>/<repo>/issues/<n>` URL elsewhere in the description.
4. Comments, most recent first.

Normalize every hit to `<org>/<repo>#<number>`. De-duplicate.

**If no GitHub link is found, stop.** Report that the Jira has no upstream link
and ask the user to add one. Do not guess an epic by searching GitHub for
title matches — a wrong epic produces a confidently wrong rollup.

**If multiple unrelated epics are found**, list them and ask which to include
rather than silently merging them.

### 4. Traverse the epic

For each epic, use `gh` (read-only). Child issues can be expressed several ways;
check all of them and union the results:

```bash
# Epic body + metadata
gh issue view <n> --repo <org>/<repo> --json number,title,state,stateReason,body,labels,assignees,url,closedAt

# Native sub-issues (GitHub Issues hierarchy)
gh api repos/<org>/<repo>/issues/<n>/sub_issues --paginate

# Cross-references and timeline links (catches "tracked by", mentions, transfers)
gh api repos/<org>/<repo>/issues/<n>/timeline --paginate
```

Also parse the epic body for task-list references (`- [ ] org/repo#123` or full
URLs) — many upstream epics track children that way rather than natively.

Children frequently live in **different repositories** than the epic. Always
carry the owning repo with each child; never assume the epic's repo.

`stateReason` distinguishes a child closed as `COMPLETED` from one closed as
`NOT_PLANNED`. The second is a flag, not progress.

**Bound the retrieval.** The reachable set is: the linked epic(s), their
children, those children's PRs, and dependencies those artifacts reference
directly (`depends on org/repo#5`, `blocked by …`). Do not widen beyond that —
no org-wide issue search, no searching GitHub by criterion keyword or title to
find a plausible owner for an unmapped criterion. A criterion with nothing in
the reachable set is an unmapped criterion, reported as such for owner review.
That is a more useful output than a guess, and it is the only honest one.

### 5. Resolve pull requests per child

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

### 6. Collect verification evidence

Only needed for criteria that have a candidate PR. This is what separates
"landed" from "demonstrated."

```bash
# What the PR actually touched — implementation vs tests vs docs
gh pr view <pr> --repo <org>/<repo> --json files,changedFiles,closingIssuesReferences

# CI result for that PR
gh pr checks <pr> --repo <org>/<repo> --json name,state,bucket,workflow,link,completedAt
```

`gh pr checks` exits nonzero by design: `8` means checks are still pending and
`1` means at least one failed. Read the JSON; do not treat the exit code as a
command failure or as "no checks exist."

- A green run establishes that **the suite** passed, not that the suite exercises
  the criterion. Cite a test as evidence only when you can name the job, file, or
  test case that covers the behavior the criterion describes.
- Changed test files under a PR that closes the child are reasonable evidence of
  intent to cover; name the file rather than claiming the behavior is verified.
- A merged docs change establishes **documented** behavior, not verified behavior.
- If the checks are inaccessible (private repo, 404, expired logs), say so against
  that criterion rather than falling back to the PR's merge state as proof.

### 7. Assess status honestly

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

`Complete` additionally requires that every acceptance criterion came out
`Evidence found` in step 8 with no downstream qualification outstanding. Closed
children with uncovered criteria are `In progress`, not `Complete`.

### 8. Assess acceptance-criteria coverage

Take each criterion from step 2 and ask what the sources you actually inspected
establish about it. Never work in the other direction — starting from an issue
and looking for a criterion it might satisfy is how candidate mappings get
promoted to coverage.

**Evidence state** — the furthest point the supporting evidence reached:

| Evidence | State |
| --- | --- |
| Nothing mapped | `—` (never `planned`; that implies tracking that does not exist) |
| Mapped issue open, no PR | planned |
| PR open or draft | in progress |
| PR open with reviews requested or submitted | in review |
| PR merged | merged |
| A named job, file, or test case exercising the criterion passed | tested |

The state describes the criterion as a whole. A test covering one clause of a
two-clause criterion does not make it `tested` — that is `merged` at most, and
`Partial evidence` in the next column.

**Coverage assessment** — exactly one of four, and say what it rests on:

| Assessment | Means |
| --- | --- |
| Evidence found | The evidence supports the criterion. State precisely what it establishes. |
| Partial evidence | Covers part of the criterion. Name what is still unverified. |
| No evidence found | The sources inspected do not establish coverage. |
| Unable to assess | Access failure, truncated results, or an ambiguous criterion blocked assessment. |

The two columns answer different questions and must not be collapsed:
**Evidence state is how far the work got; Coverage is what the behavior is
established to do.** Work in flight raises the state without moving the
assessment — a criterion whose only evidence is an open PR is `No evidence
found` at state `in review`, with the PR named in the Gap column. `Partial
evidence` is for a criterion that is genuinely part-covered by landed evidence,
typically one with two clauses where only one of them merged.

Evidence rules, in force for every row:

- **An issue title alone is a candidate mapping, not coverage.** Open the issue;
  its contents have to establish the required behavior.
- **An open issue establishes planned work**, never implemented behavior.
- **A merged PR establishes landed implementation**, never release readiness.
- **Test evidence must support the specific behavior claimed** — not an adjacent
  behavior, and not "CI is green."
- **"No evidence found" is never "not implemented."** It is a statement about
  what you looked at, and it must be scoped that way in the text: "no evidence in
  example-org/example-gateway#412 and its children."
- **Scope every absence claim** to the sources actually inspected. If traversal
  was partial, the absence claim is weaker still — say so.
- **Incomplete access or traversal is reported prominently**, not as a footnote.
  Any inaccessible repo, 404, truncated page, or skipped child gets named, and
  the Summary says coverage is incomplete.
- **Do not infer coverage from an epic's completion percentage.** 80% of children
  closed says nothing about which criterion the remaining 20% carries.
- **Do not invent** issue links, test results, owners, review commitments, or
  target dates. If no owner is identified in the sources, write "owner not
  identified in the sources inspected."

Then, **separately for each criterion, state whether downstream integration or
qualification is still required.** This is a different question from upstream
coverage and is answered independently: upstream `Evidence found` with a merged
PR routinely still needs a downstream build, payload, or qualification run. Do
not claim a downstream step is complete unless the sources inspected show it; if
downstream state was not inspected at all, say that.

Finally, sort the criteria into the three failure kinds, because they need
different follow-ups and the Summary has to distinguish them:

| Kind | Looks like | Follow-up |
| --- | --- | --- |
| Missing tracking | No upstream issue mapped at all | Owner identifies coverage or confirms a gap |
| Unfinished implementation | Mapped, but planned / in progress / in review | Engineering time |
| Downstream validation | Upstream merged or tested, downstream pending | Integration or qualification run |

### 9. Draft the rollup

Follow `references/rollup-format.md` for the exact structure and tone. Keep it
short — a rollup that runs longer than a screen will not be read. The audience is
a program manager scanning for risk, not an engineer reading a changelog.

Include a generation timestamp and the epic(s) the rollup was derived from, so a
reader can tell how stale it is and verify the source.

Material acceptance-criteria gaps belong in the Summary, not only in the table —
any criterion with `No evidence found` or `Partial evidence`, and any coverage
that could not be assessed. Name the kind of gap (missing tracking, unfinished
implementation, downstream validation) so the reader knows who has to act. If
every criterion is covered, the Summary says so in the same sentence structure;
it does not go silent on coverage.

### 10. Post only after approval

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
- **Writing criteria the Jira does not contain.** A paraphrase is an invented
  criterion. Quote, or report that none were found.
- **Promoting a candidate mapping.** A matching issue title is a lead to verify,
  not coverage. Read the issue before claiming the criterion is addressed.
- **Reading "no evidence found" as "not implemented."** It describes your
  search, not the product. Scope it to the sources inspected, every time.
- **Calling merged work shipped.** Merged upstream is not qualified downstream.
  State the downstream question separately for each criterion.
- **Widening the search to rescue an unmapped criterion.** Flag it for owner
  review instead; an org-wide search produces confident wrong mappings.
- **Burying an access failure.** An unreadable repo changes what the whole
  coverage section is worth. It goes in the Summary.
