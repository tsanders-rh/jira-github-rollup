---
name: jira-github-rollup
description: Use when asked to summarize, roll up, or report upstream GitHub development status for an existing Jira requirement, to check whether its acceptance criteria, success criteria, or definition of done are covered upstream, or to show what has moved since the last such report (e.g. "roll up RHOAIENG-1234", "what's the upstream status of this epic", "draft a status update for this Jira", "are the acceptance criteria on RHOAIENG-1234 covered", "which requirements have no upstream evidence", "what changed since the last rollup", "show the trend on RHOAIENG-1234"). Reads the GitHub epic links already present on the Jira issue, follows child issues and their pull requests across repositories, maps each stated requirement to the upstream evidence for it, and drafts a concise rollup for that same Jira issue. Saves a dated snapshot per run and reports unweighted movement against the previous one. Drafts a partial rollup when no upstream link exists. Read-only against GitHub; never creates mirrored Jira issues.
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

Coverage analysis may **read** child Jira requirements, but that does not widen
the write surface: the comment still goes on the one issue the user named, and
nothing — not a comment, not a status transition — is written to the children.

If the user asks for mirrored Jira issues, say that this skill deliberately does
not do that and offer the rollup instead.

The one thing it writes outside Jira is a snapshot file under
`~/.jira-github-rollup/snapshots/`, so the next run has a baseline to compare
against (step 11). That is a local file, it is written on draft-only runs too,
and it is never a substitute for approval to post.

## When this applies

The intended workflow is:

1. A human creates or identifies a GitHub epic corresponding to a downstream Jira
   requirement.
2. The human links that epic from the Jira issue (see
   `examples/jira-link-section.md` in this repo for the link conventions).
3. This skill reads those links and reports what has actually happened upstream.

Workflow steps 1 and 2 are **manual and stay manual.** This skill starts at
workflow step 3 — which is the Procedure below, numbered separately.

When workflow step 2 has not happened, the skill still runs: it reports the
Jira side in full and says precisely what link would complete the assessment
(step 10). What it never does is supply the missing link by guessing.

Coverage analysis rides on the same premise: the requirements are whatever the
Jira says they are, and the mapping between a requirement and upstream work is
only as good as the links a human placed. The skill reports what the evidence
supports and flags the rest for owner review.

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

### 2. Extract the stated requirements

Collect the statements this rollup will be judged against, **verbatim**, and
keep the type each one was stated under. Union these sources:

| Source | Type recorded | ID prefix |
| --- | --- | --- |
| Description section headed `Acceptance Criteria` | Acceptance criterion | `AC` |
| Description section headed `Success Criteria` | Success criterion | `SC` |
| Description section headed `Definition of Done` | Definition-of-done item | `DoD` |
| A dedicated acceptance-criteria custom field, if the site has one | Acceptance criterion | `AC` |
| Gherkin blocks (`Given / When / Then`) anywhere in the description | The type of the section it sits under | that section's |
| A Gherkin block or criteria list under no typed heading | Unlabelled requirement | `REQ` |

Then repeat all of the above on **child requirements** — sub-tasks, and issues
linked as a child of the named issue. One level only.

Rules:

- **Quote the statement as written.** Do not normalize, shorten, or rephrase it.
  If it is too long for a table cell, quote verbatim to a sentence boundary and
  append `…` — never paraphrase.
- Assign each one a stable ID in order of appearance, numbered **per type, per
  source issue**, and rendered `<PREFIX><n> (SOURCE-KEY)`. A parent's acceptance
  criteria and a child's therefore both start at `AC1`, and the key is what tells
  the two rows apart. A criterion inherited from a child is not the parent's
  criterion.
- **Never merge the types.** An acceptance criterion, a success criterion, and a
  definition-of-done item are different commitments made by different people, and
  a reader acts on them differently. Preserve the heading each came from, carry
  its prefix in every reference, and **never report a combined count as a number
  of acceptance criteria.** Count by type ("three acceptance criteria, two
  definition-of-done items") or use the neutral word "requirements".
- **Never synthesize a requirement.** Not from the summary, not from prose in the
  description, and above all not from a GitHub issue title. Only text the Jira
  presents as a criterion is a criterion.
- **None found:** say so, name the sources you checked, and continue with the
  rest of the rollup. The coverage section then reports that there is nothing to
  assess against — it does not get filled with inferred criteria.
- **Unresolved parameter or decision** (`within the agreed latency budget (TBD)`)
  — keep it verbatim and leave the splitting to step 8. A single TBD inside a
  criterion does not make the criterion unassessable.
- **Nothing checkable at all** (`performance should be acceptable`): keep it
  verbatim, assess it `Unable to assess`, and ask the owner to restate it.

### 3. Find the GitHub epic links

Scan every source — do not stop at the first hit — and sort what you find into
two tiers, because the difference decides whether you ask:

**Explicit mapping.** A human stated that this is the upstream work:

1. A dedicated section in the description (the conventional heading text is
   `Upstream Development` — see `examples/jira-link-section.md`).
2. Jira remote links / web links to `github.com` whose label identifies them as
   upstream work (`Upstream epic`, `Upstream development`, and the like).
3. A link the **user** supplied in this conversation as the mapping for this
   issue.

**Incidental.** A GitHub URL that merely appears:

4. Any other `github.com/<org>/<repo>/issues/<n>` URL in the description.
5. GitHub URLs in comments, most recent first.

Normalize every hit to `<org>/<repo>#<number>`. De-duplicate.

**Roll up every link in the explicit tier — all of them, not the first.** A
requirement that spans a data plane and a control plane genuinely has two epics,
and reporting one of them under-reports the requirement. Multiple explicit links
are not a conflict to resolve; do not ask which is "the" epic.

Ask only where the intended scope is actually unclear:

| Situation | Do this |
| --- | --- |
| Explicit tier has two or more entries | Include all of them. No question. |
| Explicit tier empty, incidental tier has exactly one issue URL | Use it, and say in the draft that it came from an unlabelled source. |
| Explicit tier empty, incidental tier has several | List each with where it was found, and ask which are in scope. |
| Incidental tier adds issues beyond the explicit set | Roll up the explicit set; list the extras and ask whether to add them. Do not drop them silently, and do not fold them in silently either. |
| A link points at a PR, project board, milestone, or bare repo | Name it and ask for the epic issue. It has no children to traverse. |

**Keep every artifact attributable to the epic it came from.** With more than one
epic in scope, each child, PR, and piece of evidence carries its originating
epic, and every absence claim names all the epics it was checked against — "no
evidence in `example-org/a#1` or `example-org/b#2` and their children," not "no
evidence upstream."

**If no GitHub link is found anywhere, do not stop — produce a partial draft**
(step 10). Report the Jira side in full, mark upstream progress and coverage as
unassessable for want of a mapping, and say exactly what link would complete the
assessment. Do not guess an epic by searching GitHub for title matches: a wrong
epic produces a confidently wrong rollup, which is worse than a partial one.
Steps 4 to 7 then have nothing to operate on: go straight to step 8 with an
empty evidence set.

### 4. Traverse the epics

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

`stateReason` has four values that matter, and they are four separate buckets —
record which one each child is in, because step 9 counts them separately:

| `state` / `stateReason` | Means |
| --- | --- |
| `CLOSED` / `COMPLETED` | Done. The only thing that counts toward completion |
| `CLOSED` / `NOT_PLANNED` | A scope decision — a flag, not progress, and not removed from scope |
| `CLOSED` / `""` | Closed before GitHub recorded a reason (pre-2022). Not countable as completed; say so rather than guessing |
| `OPEN` / `REOPENED` | Was closed, is not now |

Never normalize an empty `stateReason` to `COMPLETED`, however obvious the
merged PR next to it makes the intent. The rule is `COMPLETED` or nothing, and
the bucket is reported so nobody has to guess what was dropped.

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
| No upstream mapping on the Jira | Unknown — upstream mapping missing |
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

`Complete` additionally requires that every requirement from step 2 came out
`Evidence found` in step 8 with no downstream qualification outstanding. Closed
children with uncovered requirements are `In progress`, not `Complete`.

`Unknown — upstream mapping missing` is a statement about the Jira issue, not
about the work. Never degrade it to `Not started`, `Blocked`, or `At risk`: a
requirement with no recorded link may be fully implemented upstream by a team
that never linked it, and nothing you inspected can distinguish the two.

### 8. Assess requirement coverage

Take each requirement from step 2 — acceptance criteria, success criteria, and
definition-of-done items alike — and ask what the sources you actually inspected
establish about it. Never work in the other direction: starting from an issue and
looking for a criterion it might satisfy is how candidate mappings get promoted
to coverage.

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
| Unable to assess | An access failure, truncated results, a criterion with no checkable clause at all, or a missing upstream mapping blocked assessment. Say which. |

The two columns answer different questions and must not be collapsed:
**Evidence state is how far the work got; Coverage is what the behavior is
established to do.** Work in flight raises the state without moving the
assessment — a criterion whose only evidence is an open PR is `No evidence
found` at state `in review`, with the PR named in the Gap column. `Partial
evidence` is for a criterion that is genuinely part-covered by landed evidence,
typically one with two clauses where only one of them merged.

**A criterion that mixes checkable requirements with an unresolved parameter or
decision is not automatically `Unable to assess`.** Split it instead:

1. Assess the checkable clauses against the evidence exactly as you would a
   whole criterion.
2. Name the unresolved part, the specific clarification needed, and who can give
   it — "the retention window is given as TBD; product to set a value before this
   clause can be checked," not "criterion is ambiguous."
3. The row takes the assessment the checkable clauses earn — `Partial evidence`
   when they are covered and the unresolved clause is still open, `No evidence
   found` when they are not covered either. It is not `Evidence found` while an
   unresolved clause remains: the criterion as stated cannot be met until someone
   decides what it asks for.

`Unable to assess` stays reserved for a criterion with **no** checkable clause at
all (`performance should be acceptable`), for access failures or truncated
retrieval, and for the case where there was no upstream mapping to assess
against. Discarding the checkable half of a criterion because one number in it is
undecided throws away the part of the assessment that was free to make.

With no mapping, every row reads `Unable to assess — upstream mapping missing`,
the same wording throughout. A criterion with an unresolved clause keeps that
clause named in the Gap column even then: it is a separate ask of a separate
person, and the missing link does not absorb it.

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
- **A missing mapping is never missing implementation.** When the Jira has no
  upstream link at all, you inspected nothing upstream, so you know nothing about
  the state of the work. Say the mapping is missing; never say, imply, or let the
  layout suggest that the work has not been done.
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

Then, **separately for each requirement, state whether downstream integration or
qualification is still required.** This is a different question from upstream
coverage and is answered independently: upstream `Evidence found` with a merged
PR routinely still needs a downstream build, payload, or qualification run. Do
not claim a downstream step is complete unless the sources inspected show it; if
downstream state was not inspected at all, say that.

Finally, sort the requirements into the failure kinds, because they need
different follow-ups and the Summary has to distinguish them:

| Kind | Looks like | Follow-up |
| --- | --- | --- |
| Missing mapping | The Jira records no upstream link at all | Someone adds the link; nothing is known about the work until then |
| Missing tracking | Upstream was traversed, but no issue in it maps to this requirement | Owner identifies coverage or confirms a gap |
| Unresolved requirement | A clause of the requirement names a parameter or decision nobody has set | Product or owner decision, not engineering time |
| Unfinished implementation | Mapped, but planned / in progress / in review | Engineering time |
| Downstream validation | Upstream merged or tested, downstream pending | Integration or qualification run |

The first two look identical in a table cell and are not the same finding.
`Missing mapping` means the search never happened; `Missing tracking` means it
happened and came back empty.

### 9. Compare against the previous snapshot

Every run saves a snapshot of what it found, and reports movement against the
previous one. `references/snapshots.md` is the contract: store layout, JSON
schema, matching procedure, and the exact definition of each metric. Read it
before computing anything here.

**Find the baseline** in `~/.jira-github-rollup/snapshots/<JIRA-KEY>/`, newest
filename last:

```bash
ls -1 ~/.jira-github-rollup/snapshots/<JIRA-KEY>/*.json 2>/dev/null | tail -5
```

Prefer the most recent `-published` snapshot; fall back to the most recent
`-draft` and label it as never published. No readable snapshot means this run
is the baseline, and the section says exactly `Baseline established — no prior
snapshot available`. **Never reconstruct a baseline** from Jira history, issue
dates, or an existing rollup comment — a rendered comment is prose, not data.

**Match requirements on `(source key, type, verbatim text)`, never on ID.** IDs
are per-type ordinals, so inserting one criterion renumbers every criterion below
it; matching on IDs would report a single insertion as six changed requirements.

**Compute three unweighted ratios**, each `n/d (p%)` with the fraction always
shown:

| Ratio | Numerator | Denominator |
| --- | --- | --- |
| Child issues completed | `state CLOSED` **and** `stateReason COMPLETED` | every distinct child, deduplicated across epics |
| Requirements with evidence | assessment `Evidence found` | every requirement from step 2 |
| Downstream qualification | downstream state `confirmed` | every requirement from step 2 |

Hard rules on those numbers:

- **`Partial evidence` gets no fractional credit** — not 0.5, not a weight. It is
  counted in its own bucket and reported beside the ratio, with `No evidence
  found` and `Unable to assess`.
- **`Unable to assess` stays in the denominator.** Losing access must never look
  like an improvement, and a missing mapping must never look like missing work.
- **`NOT_PLANNED` children stay in the denominator** and are reported separately.
  So are children closed with an empty `stateReason` — GitHub only began
  recording a reason in 2022, so an older child reports none. Neither counts
  toward completion; both are named rather than dropped.
- **A count that could not be observed is `unknown`** — no upstream mapping, or
  an epic whose repo returned 404. Never `0/0`, `N/A`, or `0%`; a 404 is not a
  count of zero.
- **A zero denominator is `N/A`** with the reason — only when the zero was
  actually observed.
- **Uninspected downstream state is `unknown`**, never `pending`. `pending` is a
  claim about an artifact someone actually looked at.
- Requirement counts stay typed. Only the aggregate may be called
  "requirements"; never "acceptance criteria".

**Classify each change by kind, separately**: added, removed, text changed,
mapping changed, reopened, access changed, assessment changed. Then split an
assessment change by cause, using the evidence timestamps against the baseline's
`generatedAt`:

- evidence dated **after** the baseline → **implementation progress**;
- evidence dated **at or before** it → **newly discovered evidence** (access
  restored, link finally added, deeper traversal — the work already existed);
- no usable timestamp → **undetermined**, said out loud, never defaulted to
  progress.

**When the denominator moved, say so beside the percentage.** Added scope lowers
a percentage with nothing having gone backwards, and a reader acts on the first
clause they read. Give the like-for-like movement over requirements present and
unchanged in both snapshots.

**Never derive a rate, velocity, burn-down, or projected date.** Two unweighted
counts support none of them.

### 10. Draft the rollup

Follow `references/rollup-format.md` for the exact structure and tone. Keep it
short — a rollup that runs longer than a screen will not be read. The audience is
a program manager scanning for risk, not an engineer reading a changelog.

**Write the draft in GitHub-flavored Markdown** — `###`/`####` headings, `**bold**`
labels, pipe tables with a `| --- |` separator row. That is what renders in the
conversation the reviewer is reading it in. Do not draft in Jira wiki markup;
`h3.` lines and `||` header rows render as literal punctuation here, and a
reviewer cannot approve a table they cannot see. Markup conversion happens in
step 12, once, and only if the Jira tool needs it.

Include a generation timestamp and the epic(s) the rollup was derived from, so a
reader can tell how stale it is and verify the source. List every epic when more
than one is in scope.

Material coverage gaps belong in the Summary, not only in the table — any
requirement with `No evidence found` or `Partial evidence`, and any coverage that
could not be assessed. Name the kind of gap (missing mapping, missing tracking,
unresolved requirement, unfinished implementation, downstream validation) so the
reader knows who has to act. If every requirement is covered, the Summary says so
in the same sentence structure; it does not go silent on coverage.

**When no upstream mapping was found**, the draft is partial, not withheld: the
Jira scope and the full requirements table, every row `Unable to assess —
upstream mapping missing`, plus a `What is needed` section naming the link that
would complete it. `references/rollup-format.md` carries the exact shape; what
must not vary is that the status stays `Unknown — upstream mapping missing`,
there is no Progress section, and nothing in the draft describes the work as not
started, unimplemented, behind, or at risk.

### 11. Save the snapshot

Write what this run found to
`~/.jira-github-rollup/snapshots/<JIRA-KEY>/<YYYYMMDDThhmmssZ>-draft.json`,
`mkdir -p` the directory first, and use the Write tool rather than a shell
heredoc so the JSON is not mangled by the shell. The schema is in
`references/snapshots.md`; it carries the mappings, every requirement's verbatim
text and type, the assessments, evidence links, downstream state, the traversal
scope, access limitations, the UTC timestamp, and `schemaVersion`.

This happens **before** approval and regardless of it. A draft-only run saves a
draft snapshot and makes no Jira change of any kind — that is the whole reason
the baseline lives on disk rather than in the comment.

**Never overwrite or delete a snapshot.** Each run writes a new file. The next
step may edit a Jira comment in place; the comparison baseline must survive that.
Tell the user where the file went — a trend report whose storage is invisible is
one the user cannot audit or reset.

If the write fails, say so and continue. The rollup is what was asked for; the
snapshot is bookkeeping, and losing it costs the next run its baseline, not this
run its output.

### 12. Post only after approval

Show the draft — in GitHub-flavored Markdown, as written in step 10 — and ask
whether to post. On approval, add it as a **comment** on the original Jira issue
via `addOrEditJiraIssueComment`.

Once the comment is posted, **promote this run's snapshot**: set `publication`
to `published`, fill `publishedAt` and `jiraCommentId`, and rename the file's
`-draft` suffix to `-published`. Promote only after the post actually succeeded.

**Convert the markup only now, and only to what the tool accepts.** Check the
comment tool's own parameter description and schema for the format it documents
as its input; do not assume wiki markup, and do not assume the GFM will survive.
`references/rollup-format.md` § Preparing the Jira payload has the conversion
table and the plain-text fallback for when the format is unclear. Content,
section order, and every verbatim quote stay identical — only the markup changes.

If a prior rollup comment from this skill exists (identified by its trailing
marker line — match the sentence, not its markup), offer to edit that comment in
place instead of appending a new one, so the issue does not accumulate
near-identical updates.

Posting to Jira is outward-facing and visible to the whole project — never do it
without the user saying yes to that specific draft.

**If the user asked for a draft, the draft is the deliverable.** Hand it over and
stop. Asking for a draft is not approval to post, a partial draft is not a
special case, and approval of an earlier draft never carries forward to this one.
Saving a snapshot is not posting and does not need approval — it writes one local
file and touches nothing in Jira.

## Failure modes to avoid

- **Inventing an epic link.** No link means a partial draft plus a request for
  the link — never a title search, and never a plausible guess.
- **Stopping dead when no epic is linked.** The Jira side is still worth
  reporting, and the requirements table is the most useful part of it.
- **Reading a missing mapping as missing work.** No link means you looked at
  nothing upstream, not that nothing happened upstream.
- **Rolling up only the first epic.** Every explicitly linked epic is in scope,
  and each artifact stays attributed to the one it came from.
- **Dropping cross-repo children.** The epic's repo is not the children's repo.
- **Reporting closed as shipped.** Closed without a merged PR is a flag, not a win.
- **Creating Jira issues.** See the constraint at the top.
- **Silent staleness.** Always timestamp; always name the source epic.
- **Writing criteria the Jira does not contain.** A paraphrase is an invented
  criterion. Quote, or report that none were found.
- **Totalling the requirement types.** Acceptance criteria, success criteria, and
  definition-of-done items are counted and labelled separately. "Five acceptance
  criteria" when two of them are DoD items misreports what was committed to.
- **Writing off a whole criterion because one clause is undecided.** Assess the
  checkable clauses; name the specific decision the rest is waiting on.
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
- **Drafting in Jira markup.** The reviewer reads the draft in this conversation,
  which renders Markdown and not `h3.` or `||`. Convert at post time, not before.
- **Guessing the Jira comment format.** Wiki markup, ADF, and plain text are not
  interchangeable. Read what the comment tool documents; fall back to plain text.
- **Inventing a baseline.** No snapshot means `Baseline established — no prior
  snapshot available`. The previous Jira comment is prose, not data, and the
  issue's own history is not a record of what this skill found.
- **Matching requirements by ID across runs.** IDs renumber when a criterion is
  inserted. Match on source key, type, and verbatim text.
- **Reporting discovery as progress.** Access restored or a link finally added
  can move four requirements in a run with no new code. Check the evidence dates.
- **Letting added scope read as regression.** A denominator that grew explains
  the falling percentage, and it has to say so in the same sentence.
- **Weighting partial coverage.** No halves, no fractions. `Partial evidence` is
  its own count, and any weight would be a number the skill made up.
- **Dropping `not planned` children from the denominator.** That inflates
  completion and hides a scope decision the reader needs.
- **Turning two data points into a forecast.** No velocity, no burn-down, no
  projected date. The section reports movement, not a trajectory.
