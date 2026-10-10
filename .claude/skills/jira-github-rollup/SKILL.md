---
name: jira-github-rollup
description: Use when asked to summarize, roll up, or report upstream GitHub development status for an existing Jira requirement, to check whether its acceptance criteria, success criteria, or definition of done are covered upstream, or to show what has moved since the last such report (e.g. "roll up RHOAIENG-1234", "what's the upstream status of this epic", "draft a status update for this Jira", "are the acceptance criteria on RHOAIENG-1234 covered", "which requirements have no upstream evidence", "what changed since the last rollup", "show the trend on RHOAIENG-1234"). Reads the GitHub epic links already present on the Jira issue, follows child issues and their pull requests across repositories, maps each stated requirement to the upstream evidence for it, and produces two outputs from one assessment: a detailed evidence review, and a concise Jira summary draft posted only after explicit approval. Saves a dated snapshot per run and reports unweighted movement against the previous one. Drafts a partial rollup when no upstream link exists. Read-only against GitHub; never creates mirrored Jira issues.
---

# Jira ← GitHub Development Rollup

Draft a development-status rollup for an **existing** Jira requirement by
following the GitHub epic links a human already placed on that issue.

Scripts do the retrieval, the counting and the rendering. You do the two things
code cannot: read what a requirement actually asks for, and judge what a piece
of evidence establishes about it. Keep that line — a script that guessed at
coverage, or an assessment made from a summary nobody read, are the two ways
this skill produces a confidently wrong report.

One run produces **two outputs from one assessment**: a full assessment for
review, and a short Jira summary draft that is the only thing ever posted. They
are rendered from the same tally and the assembler refuses to emit them if their
counts disagree, so never hand-edit one to match the other.

## Invariants

These hold at every step. They are not restated later.

1. **Never create Jira issues.** No mirrors, no sub-tasks, no linked issues. The
   only Jira write is a comment on the one issue the user named. Reading child
   requirements does not widen that. If asked for mirrored issues, say the skill
   deliberately does not do that and offer the rollup.
2. **Never post without approval of the specific summary text in front of the
   user.** Approval of an earlier draft never carries forward, and a substantive
   revision after approval needs approving again. A request for a draft is not
   approval to post. Post the **Jira summary**, never the full assessment, and
   never change status, fix versions or assignee as part of posting.
3. **Never guess the epic.** The human-created link is the only acceptable
   source. No link means a partial draft, not a title search and not a report of
   unstarted work.
4. **GitHub is read-only.** `scripts/jgr/ghclient.py` constructs read verbs only.
5. **The only thing written outside Jira is a snapshot** under
   `~/.jira-github-rollup/snapshots/<JIRA-KEY>/`, plus a raw-response cache under
   `~/.jira-github-rollup/cache/<JIRA-KEY>/`. No run overwrites or deletes
   another run's snapshot. **The assessment payload is immutable once written**:
   the only permitted later change is `promote`, which adds publication
   metadata (`publication`, `publishedAt`, `jiraCommentId`, `published`) and
   renames `-draft.json` to `-published.json`. It never touches a requirement,
   an assessment, an evidence item or a count.
6. **Counts are unweighted and never a forecast.** No velocity, no burn-down, no
   projected dates, no partial credit. A count that was not observed is
   `unknown`, never `0`, `0/0`, `N/A` or `0%`. Closed-issue ratios are never
   converted into feature completion.
7. **Absence of evidence is never absence of work.** "No evidence found" is a
   statement about the sources inspected and is always scoped to them; a missing
   mapping means nothing upstream was inspected at all. `confirmed-unmet` means
   you found evidence the outcome is *not* satisfied — never that you found
   nothing.
8. **Never print raw payloads into the conversation.** Timelines, CI logs, full
   issue bodies and API responses stay in the cache. Read what you need with
   `rollup.py excerpt`.

## Procedure

Run from `.claude/skills/jira-github-rollup/scripts/`. Every command reads and
writes JSON files; pass paths, not pasted contents.

### 1. Read the Jira issue

`getJiraIssue` for the key (extract it from a URL if that is what you were
given). Capture key, summary, status, fix versions, description, web links, and
one level of child requirements (`fields.subtasks`, `fields.issuelinks`).

Custom fields are omitted by default — if the site keeps acceptance criteria in
one, re-fetch with `view: evidence` and read `fields.customFields`. IDs differ
per site; do not hard-code one.

Do not pull comment bodies yet. They are only needed if step 2 finds no explicit
link, and they are the largest thing on a busy issue.

### 2. Extract the requirements, and find the mapping

Read `references/requirements.md` and extract the stated requirements verbatim
into `requirements.json`: one object per requirement with `id`, `sourceKey`,
`type`, `text`, `heading`. This is yours alone — no script invents, merges,
splits or paraphrases a requirement.

Hand the Jira text to the reference scanner, which normalizes, deduplicates and
tiers every GitHub reference it finds:

```bash
python3 rollup.py refs --in jira-text.json --out refs.json
```

Its input is `{jiraKey, description, descriptionSections, webLinks, comments,
userSupplied}`; omit `comments` on the first pass. It returns the epics to roll
up, the question to ask if the mapping is genuinely unclear, and non-issue
references (PRs, boards, bare repos) that have no children to traverse.

If `mappingFound` is false and you have not searched comments, check whether any
comment mentions GitHub at all before fetching bodies:

```
searchJiraIssuesUsingJql: key = <KEY> AND comment ~ "github.com"
```

Only on a hit, re-fetch the issue with comments and re-run `refs`. Ask whatever
question `refs.json` returns rather than resolving it yourself.

Still no mapping: run the partial sequence below and go to step 6. Do not search
GitHub for a plausible epic.

```bash
python3 rollup.py collect --key <KEY> --epics '[]' --out manifest.json
python3 rollup.py diff --manifest manifest.json \
  --requirements requirements.json --out diff.json
python3 rollup.py assemble --in assembly.json --manifest manifest.json \
  --diff diff.json --requirements requirements.json --assessments '[]' \
  --report full-assessment.md --summary jira-summary.md --out result.json
```

The empty epic list sets `observed: false`, so every row is auto-filled `Unable
to assess` with the gap naming the link that is needed, child counts render
`unknown` rather than `0`, and `--assessments '[]'` is correct — there is
nothing to assess, and nothing is being skipped. The Jira side is still
reported in full. Say in `summary` that no upstream source was inspected.

### 3. Collect the evidence

```bash
python3 rollup.py collect --key <KEY> --epics refs.json --out manifest.json
```

This walks the epics, their children (sub-issues, task lists, timeline
cross-references, across repositories), and each child's PRs, caching every raw
response and returning a compact manifest: refs, originating epics, states,
`stateReason`, timestamps, content hashes, access failures, and cache paths.

Then fetch verification evidence **only** for the PRs you consider candidates
for some requirement:

```bash
python3 rollup.py collect --key <KEY> --epics refs.json --stage evidence \
  --manifest manifest.json --targets '["example-org/example-gateway#520"]' \
  --out manifest.json
```

The reachable set is fixed in code: linked epics, their children, those
children's PRs, and directly referenced dependencies. There is no widening
option, and adding one would be a change to the skill's constraints.

### 4. Find out what needs reassessing

```bash
python3 rollup.py diff --manifest manifest.json \
  --requirements requirements.json --out diff.json
```

Picks the baseline (most recent published snapshot, else most recent draft,
labelled as never published), matches requirements on `(sourceKey, type,
verbatim text)` rather than ID, and returns `reassess` (what you must look at)
and `reuse` (assessments carried forward with their evidence and timestamps).

`--full-refresh` reassesses everything. The plan already forces that when there
is no baseline, when the rules version changed, when the baseline predates
content hashing, when the mapping changed, or when nothing was observed.

### 5. Assess the requirements in `reassess`

Read the assessment half of `references/requirements.md` **once**, then work
through the list. For each requirement, work from the requirement to the
evidence — never from an issue to a criterion it might satisfy. Read bodies and
test content deliberately:

```bash
python3 rollup.py excerpt --key <KEY> --ref example-org/example-gateway#413 --field body
python3 rollup.py excerpt --key <KEY> --ref example-org/example-gateway#520 \
  --kind pr-files --field files --match 'test'
```

Excerpts report their own truncation and carry the path to the full text. A
compact summary is not proof: if the manifest does not settle a question, read
the artifact.

Emit `assessments.json`, one object per reassessed requirement: `id`,
`sourceKey`, `assessment`, `coverageDetail`, `evidence` (each with `ref`,
`kind`, `state`, `at`), `evidenceState`, `gap`, `downstream`. Anything you leave
out of both `assessments.json` and `diff.json`'s `reuse` is an error, not an
`Unable to assess` — the assembler refuses to invent a verdict.

The four coverage assessments become the four outcomes the reader counts, and
the mapping is fixed in code: `Evidence found → met`, `Partial evidence →
partial`, `No evidence found` and `Unable to assess → unverified`.

Both ends of that are guarded, because both are how a count becomes a lie:

- **`Evidence found` is a claim about every clause of the criterion**, not about
  the work existing. Any clause still undecided goes in `unresolvedClauses`, any
  clause the evidence does not support goes in `uncoveredClauses`, and either
  one makes the honest assessment `Partial evidence`. The assembler refuses
  `Evidence found` with a clause open rather than downgrading it quietly — the
  detail column would otherwise still read as fully established.
- **`confirmed-unmet` is the one outcome you may declare by hand**, via
  `"outcome": "confirmed-unmet"` plus `refutingEvidence` naming what shows the
  criterion is not satisfied. The assembler rejects the claim otherwise; it
  never infers it from a gap.

### 6. Assemble both outputs

Write `assembly.json` with `jira` (include `site` so criteria can be linked back,
and `fixVersions` if the issue has one), `mappings`, `summary` (two to five
sentences you write for the full assessment), and optionally `caveats`, `risks`,
`trendNotes`, `dependencies`. Then:

```bash
python3 rollup.py assemble --in assembly.json --manifest manifest.json \
  --diff diff.json --requirements requirements.json \
  --assessments assessments.json \
  --report full-assessment.md --summary jira-summary.md --out result.json
```

One merge, one tally, two renderings:

| Output | Audience | Contains |
| --- | --- | --- |
| `full-assessment.md` | Review, in this conversation | Criterion-by-criterion evidence, downstream qualification, dependencies and tracking gaps, collection scope and limitations, trend |
| `jira-summary.md` | The Jira comment, after approval | 150–250 words: the outcome table, four bullets, trend, one scope caveat. No criterion-by-criterion analysis, no collection diagnostics |

`result.json` reports `outcomes`, `deliveryConfidence`, `summaryWords` and
`snapshotPath`. `--full-assessment-url` adds a "Full assessment" link to the
summary, and is only honoured for a durable URL a Jira reader can open; a local
path is dropped rather than published. `references/rollup-format.md` documents
both contracts.

Material gaps belong in your `summary`, named by kind (missing mapping, missing
tracking, unresolved requirement, unfinished implementation, downstream
validation) so the reader knows who has to act. If everything is covered, say
that in the same sentence structure rather than going silent on coverage.

Show both. Tell the user where the snapshot went. To re-render either from a
stored snapshot without re-collecting or re-judging anything:

```bash
python3 rollup.py rerender --snapshot <path> --site <jira-base-url> \
  --report full-assessment.md --summary jira-summary.md --out result.json
```

### 7. Post only after approval

Show the summary and ask whether to post **that text**. Offer to revise it;
every revision is a new draft needing its own yes. Nothing below happens
without one, and what gets posted is the summary, never the full assessment.

`addOrEditJiraIssueComment` takes `commentBody` as **Markdown by default**, with
`contentFormat: "html"` as the alternative — it is not a wiki-markup input. Send
`jira-summary.md` as written. Use HTML only if Markdown comes back mangled:

```bash
python3 rollup.py convert --in jira-summary.md --target html
```

Check the posted comment renders its headings, table, bullets and links. If a
prior rollup comment exists — find it by the marker sentence, not its markup —
offer to edit it in place instead of appending.

Only after the post returns a comment id:

```bash
python3 rollup.py promote --path <snapshot-path> --comment-id <id> \
  --published-text jira-summary.md
```

A failed or declined post leaves the snapshot a draft. `promote` refuses a blank
id for exactly this reason: advancing the published baseline for a comment that
never landed silently corrupts the next run's trend.

## References

| File | Read it when |
| --- | --- |
| `references/requirements.md` | Extracting requirements (step 2) or assessing them (step 5) |
| `references/pipeline.md` | A command fails, or you need the full CLI, cache layout or recovery steps |
| `references/rollup-format.md` | Checking what a section should contain, or converting for Jira (step 7) |
| `references/snapshots.md` | Reasoning about the baseline, the schema, or a metric definition |

## Failure modes

The scripts enforce the arithmetic, the buckets, the matching and the
append-only store. These are the ones still available to you:

- **Inventing an epic link,** or stopping dead when there is none. No link means
  a partial draft and a request for the link.
- **Reading a missing mapping as missing work,** or letting the layout imply it.
- **Writing criteria the Jira does not contain.** A paraphrase is an invented
  criterion. Quote, or report that none were found.
- **Totalling the requirement types.** Acceptance criteria, success criteria and
  definition-of-done items are counted and labelled separately.
- **Promoting a candidate mapping.** A matching issue title is a lead. Open the
  issue.
- **Treating green CI as coverage.** Name the job, file or test case that
  exercises the behaviour the criterion describes, or do not claim `tested`.
- **Writing off a whole criterion because one clause is undecided.** Assess the
  checkable clauses; name the decision the rest waits on.
- **Calling a criterion met on evidence that the work exists.** A criterion is a
  conjunction. Evidence for its main clause is not evidence for all of them —
  name the rest in `uncoveredClauses` and assess `Partial evidence`.
- **Calling merged work shipped.** Downstream qualification is a separate
  question, answered separately for each requirement.
- **Burying an access failure.** An unreadable repo changes what the coverage
  section is worth; it goes in the Summary.
- **Asserting from the manifest alone.** It carries states and hashes, not
  behaviour. Excerpt the artifact before claiming what it does.
- **Pasting raw output into the conversation** to "show your work."
- **Drafting in Jira markup,** or guessing the comment format.
- **Reporting discovery as progress.** Access restored or a link finally added
  moves requirements with no new code; the script classifies this from evidence
  dates, so give it accurate `at` values.
- **Posting the full assessment.** It is for review in this conversation. The
  Jira comment is the summary.
- **Inferring delivery confidence from the counts.** Nine met is not "on track"
  without a release target and qualification evidence. `Not assessed` is the
  honest answer and the script will insist on it.
- **Naming an owner for a gap.** "The Metering epic covers SC6" is a claim about
  an epic nobody traversed. Say "identify and link the work covering SC6" unless
  a source you read names the owner.
- **Inventing a link, or pasting a local path.** `~/.jira-github-rollup/...` in a
  Jira comment publishes someone's home directory; the assembler blocks it, but
  do not write it in the first place.
