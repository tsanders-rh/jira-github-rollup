---
name: jira-github-rollup
description: Use when asked to summarize, roll up, or report upstream GitHub development status for an existing Jira requirement, to check whether its acceptance criteria, success criteria, or definition of done are covered upstream, or to show what has moved since the last such report (e.g. "roll up RHOAIENG-1234", "what's the upstream status of this epic", "draft a status update for this Jira", "are the acceptance criteria on RHOAIENG-1234 covered", "which requirements have no upstream evidence", "what changed since the last rollup", "show the trend on RHOAIENG-1234", "generate an HTML report for RHOAIENG-1234"). Reads the GitHub epic links already present on the Jira issue, follows child issues and their pull requests across repositories, maps each stated requirement to the upstream evidence for it, and renders one assessment three ways: a detailed evidence review, a concise Jira summary draft posted only after explicit approval, and on request a standalone interactive HTML report. Saves a dated snapshot per run and reports unweighted movement against the previous one. Drafts a partial rollup when no upstream link exists. Read-only against GitHub; never creates mirrored Jira issues.
---

# Jira ← GitHub Development Rollup

Draft a development-status rollup for an **existing** Jira requirement by
following the GitHub epic links a human already placed on that issue.

Scripts do the retrieval, the counting and the rendering. You do the two things
code cannot: read what a requirement actually asks for, and judge what a piece
of evidence establishes about it. Keep that line — a script that guessed at
coverage, or an assessment made from a summary nobody read, are the two ways
this skill produces a confidently wrong report.

One run produces **one assessment, rendered more than once**: a full assessment
for review, a short Jira summary draft that is the only thing ever posted, and —
on request — a standalone interactive HTML file of the same full assessment. All
three come from the same tally and the assembler refuses to emit them if their
counts disagree, so never hand-edit one to match another.

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

Still no mapping: extract the requirements (step 4), then run the partial
sequence below. It ends at the same place step 6 does, so **do not assemble
again** — go to step 7. Do not search GitHub for a plausible epic.

```bash
python3 rollup.py collect --key <KEY> --epics '[]' --out manifest.json
python3 rollup.py diff --manifest manifest.json \
  --requirements requirements.json --out diff.json
```

Now write `assembly.json` exactly as step 6 describes, with `mappings: []` and a
`summary` that says no upstream source was inspected. It has to exist before the
next command: `--in` reads it, and `--manifest`/`--diff` only override two of its
keys.

```bash
python3 rollup.py assemble --in assembly.json --manifest manifest.json \
  --diff diff.json --requirements requirements.json --assessments '[]' \
  --report full-assessment.md --summary jira-summary.md --out result.json
```

The empty epic list sets `observed: false`, so every row is auto-filled `Unable
to assess` with the gap naming the link that is needed, child counts render
`unknown` rather than `0`, and `--assessments '[]'` is correct — there is
nothing to assess, and nothing is being skipped. The Jira side is still reported
in full, and the report carries the missing link as the limitation it is.

### 3. Collect the evidence

```bash
python3 rollup.py collect --key <KEY> --epics refs.json --out manifest.json
```

This walks the epics, their children (sub-issues, task lists, timeline
cross-references, across repositories), and each child's PRs, caching every raw
response and returning a compact manifest: refs, originating epics, states,
`stateReason`, timestamps, content hashes, access failures, and cache paths.

A child that is itself an epic is traversed **one further level, and only when
a declared relation found it** — a sub-issue or a task-list entry. A timeline
cross-reference establishes that something mentioned the epic, which is not
membership, and descending through one would attach an unrelated tree to this
issue's criteria. Everything left alone lands in `manifest.untraversed`, which
every rendering reports by name; it is the scope of every absence claim in the
run.

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

**Before you write down a clause as unsupported, resolve what you can resolve.**
If a source already within scope would settle the question — a file in a PR's
changed-file list, a symbol its description names, the test beside the
implementation — read it at the revision the evidence was produced at:

```bash
python3 rollup.py source --key <KEY> --repo example-org/example-rails \
  --path rails/deny.py --revision <PR mergeCommit> \
  --match 'FAIL_CLOSED_RAILS|on_error'
```

`--revision` is required and the manifest carries each merged PR's
`mergeCommit`; today's default branch is a different document and proves
nothing about the PR you are citing. The budget is **12 reads per run**,
deduplicated, and it is a lookup rather than an audit — follow concrete
references, do not walk the repository, do not re-read what you have read. Past
the budget, or where the file cannot be read, the command says so and that is
an inspection limitation on the clause, not a finding about the product.

Read what the source establishes, not what it suggests: membership in a list a
validator checks establishes which **configurations** are rejected, never what
happens at runtime. That is a second clause and a second read.

Emit `assessments.json`, one object per reassessed requirement: `id`,
`sourceKey`, `assessment`, `coverageDetail`, `evidence`, `evidenceState`,
`gap`, `downstream`. Anything you leave out of both `assessments.json` and
`diff.json`'s `reuse` is an error, not an `Unable to assess` — the assembler
refuses to invent a verdict.

**An evidence item is `{"ref": …}` and nothing else.** `kind`, `state` and
`at` are joined from the manifest, or from this run's source reads for a
`owner/repo@revision:path` ref; a ref neither one carries is refused by name,
and a field you state that disagrees with what was collected is refused rather
than merged. Anything outside the traversal — a CI job name — states its own
`kind`. Transcribing a merge time by hand is how a rounded timestamp silently
flips a trend row between "work landed" and "we only just found it".

The four coverage assessments become the four outcomes the reader counts, and
the mapping is fixed in code: `Evidence found → met`, `Partial evidence →
partial`, `No evidence found` and `Unable to assess → unverified`.

Both ends of that are guarded, because both are how a count becomes a lie:

- **`Evidence found` is a claim about every clause of the criterion**, not about
  the work existing. Any clause still undecided goes in `unresolvedClauses`, any
  clause still open after the follow-up read goes in `uncoveredClauses`, and
  either one makes the honest assessment `Partial evidence`. The assembler
  refuses `Evidence found` with a clause open rather than downgrading it
  quietly — the detail column would otherwise still read as fully established.
- **Each open clause says why it is open**, because the three reasons go to
  three different people. `implementation-gap` cites what shows the behaviour
  missing; `evidence-gap` names what you inspected that did not settle it;
  `inspection-limitation` states the constraint that stopped the read. All
  three need a `nextAction`. The assembler refuses an implementation gap citing
  nothing — an unread file is not proof of missing functionality, and an absent
  test is not proof of an absent implementation — and refuses an evidence gap
  naming nothing inspected, because with nothing named it is a limitation.
- **A next action you could not take is not a next action.** `source` takes an
  exact path and does not search, so "read the metering emission path" settles
  nothing. The path is a lookup away — `excerpt --kind pr-files --field files`
  has the PR's whole changed-file list — so resolve the subsystem to a file,
  read it, and reassess. Name the file in the clause's optional `nextRead`
  (`repo`, `path`, `revision`) when you can; every run reports open evidence
  gaps, how many name a target, and how many reads went unspent, and
  `assemble` says so on stderr. A clause asking a *person* to decide belongs
  in `unresolvedClauses`, not here.
- **`confirmed-unmet` is the one outcome you may declare by hand**, via
  `"outcome": "confirmed-unmet"` plus `refutingEvidence` naming what shows the
  criterion is not satisfied. The assembler rejects the claim otherwise; it
  never infers it from a gap.

### 6. Assemble the outputs

Write `assembly.json` with `jira` (include `site` so criteria can be linked back,
and `fixVersions` if the issue has one), `mappings`, `summary` (two to five
sentences you write for the full assessment), and optionally `caveats`, `risks`,
`trendNotes`, `dependencies`.

Add `overall`: **the one paragraph every rendering opens with**, 60–100 words,
so a reader gets the position without reconstructing it from the rows. Say what
capability the evidence establishes, which required capabilities are explicitly
unmet, which are unverified or carry conflicting evidence, and what decision
resolves the gaps — grouped into capability areas, never a list of criterion
ids.

```json
{"text": "Tiered routing has a working implementation path, but the collected evidence does not establish the full metering capability. …",
 "establishes": [{"sourceKey": "RHOAIENG-1234", "id": "AC1"}],
 "unmet": [{"sourceKey": "RHOAIENG-1234", "id": "AC2"}],
 "unverified": [{"sourceKey": "RHOAIENG-1234", "id": "DoD1"}],
 "links": ["example-org/example-gateway#520"]}
```

`establishes` must be met or partial rows, `unmet` only `confirmed-unmet` ones
— missing evidence is not a confirmed absence — and `unverified` only rows
nothing settles. `assemble` refuses the run otherwise, and also refuses a
criterion id, a percentage, a readiness claim or a date in the text. Leave it
out and all three renderings fall back to a paragraph built from the counts,
which says nobody wrote one. See
[`references/rollup-format.md`](references/rollup-format.md).

Then write `narrative.json`: the Jira summary's bullets, in your words. This is
the part a manager reads, and a list of criterion ids is not a status update —
say what the system now does, what it does not, and what nobody has decided.

```json
[{"bullet": "evidence-established",
  "text": "Tier-based pool selection routes paid-tier requests and merged on 2026-09-18",
  "refs": [{"sourceKey": "RHOAIENG-1234", "id": "AC1"}],
  "links": ["example-org/example-gateway#520"]}]
```

`bullet` is one of `evidence-established`, `remaining-work`,
`decisions-needed`, `next-actions`; several claims may share one. **Every claim
names the assessment rows it rests on**, and every link it cites has to be
evidence on one of those rows — `assemble` refuses the run otherwise. That
check is traceability, not truth: whether the evidence establishes what your
sentence says is still your judgement. A bullet you leave empty falls back to a
mechanical sentence from the counts, which is a floor, not the goal.

```bash
python3 rollup.py assemble --in assembly.json --manifest manifest.json \
  --diff diff.json --requirements requirements.json \
  --assessments assessments.json --narrative narrative.json \
  --report full-assessment.md --summary jira-summary.md \
  --html full-assessment.html --out result.json
```

One merge, one tally, three renderings:

| Output | Audience | Contains |
| --- | --- | --- |
| `full-assessment.md` | Review, in this conversation | Criterion-by-criterion evidence, outcomes split by type, downstream qualification, dependencies and tracking gaps, collection scope and limitations, trend |
| `jira-summary.md` | The Jira comment, after approval | 210–350 words: the outcome table, the type mix, the overall assessment, four bullets of narrative, trend, one scope caveat. No criterion-by-criterion analysis, no collection diagnostics |
| `full-assessment.html` | Reading and forwarding outside this conversation | The same full assessment, searchable and filterable, with each criterion's evidence behind a disclosure. Written only when `--html` names a path |

The renderer keeps the summary readable at 49 criteria as well as 9: a criterion
is named explicitly in **one** bullet and counted thereafter, at most three
explicit references appear per bullet with the rest collapsed to counts by
owning issue, and every reference is qualified — `RHOAIENG-1234 AC1`, never a
bare `AC1`, which six issues in one rollup can each have. Complete lists live in
the full assessment.

`result.json` reports `outcomes`, `deliveryConfidence`, `summaryWords`,
`summaryWordBudget`, `narrativeClaims`, `snapshotPath`, and `htmlBytes` with
`htmlPath` when `--html` was given. `references/rollup-format.md` documents all
three contracts.

**`summaryWordBudget.condition` of `over-ceiling` is a step, not a statistic.**
Rewrite the bullets and assemble again *before* you show the draft; `assemble`
prints how many words they actually have left. Nothing in the renderer will fix
it — it never truncates a claim, and naming fewer criteria per bullet is worth a
handful of words at any scale. At 49 criteria the four bullets have about a
hundred words between them, so a bullet gives the **shape** of the finding —
how many, whose, of what kind — and sends the reader to the full assessment
instead of enumerating it. `under-floor` needs no re-run: it usually means the
bullets are a list of ids rather than a status.

**`--html` writes a file; it does not create a link.** The document is
standalone — embedded CSS and script, no fonts, no CDN, no network at runtime —
so it works from a local path, an attachment or a share drive. None of those is
a URL a Jira reader can open. `--full-assessment-url` adds a "Full assessment"
link to the summary, and only for an absolute `http(s)` URL you were actually
given; a local path, a `file://` URL and a bare filename are all dropped rather
than published. Never pass the `--html` path to it.

Do not write HTML yourself. The renderer builds the document from the assembled
rows, escapes every string from Jira and GitHub, and drops any ref that is not
an `http(s)` URL — a hand-written narrative in HTML would be a fourth document
nothing cross-checks.

Material gaps belong in your `summary`, named by kind (missing mapping, missing
tracking, unresolved requirement, unfinished implementation, downstream
validation) so the reader knows who has to act. If everything is covered, say
that in the same sentence structure rather than going silent on coverage.

Show both. Tell the user where the snapshot went. The snapshot stores your
narrative along with the assessments, so re-rendering reproduces the text that
was reviewed rather than falling back to counts — re-render from a stored
snapshot without re-collecting or re-judging anything:

```bash
python3 rollup.py rerender --snapshot <path> --site <jira-base-url> \
  --report full-assessment.md --summary jira-summary.md \
  --html full-assessment.html --out result.json
```

This is also how you produce the HTML for a run that did not ask for it, or
regenerate it after the renderer changes: no collection, no cache, no new
judgement. A snapshot whose comment was posted re-renders as published rather
than as a draft.

### 7. Post only after approval

Show the summary and ask whether to post **that text**. Offer to revise it;
every revision is a new draft needing its own yes. Nothing below happens
without one, and what gets posted is the summary, never the full assessment.

Do not bring a draft here whose `summaryWordBudget.condition` is
`over-ceiling`. Asking for approval of something nobody will read to the end is
asking for the wrong yes.

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
- **Making an existence claim the traversal cannot support.** "No upstream
  issue covers this" is about all of GitHub; you walked one epic. Scope it to
  the traversed set — and remember an untraversed nested epic is part of what
  you are scoping it to.
- **Prescribing the fix for a contradicted criterion.** "Reopen the work or
  revise the requirement" answers a question nobody asked. State the question:
  does the criterion still describe intended behaviour.
- **Writing a narrative claim that no assessment row carries.** Every sentence
  in the summary names the rows it rests on. The check that they exist is not a
  check that you read them right — that part is still yours.
- **Filling the bullets with criterion ids.** The counts are two lines above.
  A manager needs to know what the system does now, not which ordinals moved.
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
- **Stopping one read short.** Naming the file that would settle a clause,
  having access to it, and reporting the clause open anyway. If the source is
  in scope and within budget, open it; the reader is otherwise told the product
  is missing something when what was missing was a read.
- **Writing a next action addressed to a tool that cannot take it.** "Read the
  metering emission path" names a subsystem; `source` takes a path. Resolve it
  against the changed-file list and read the file, or say that it does not
  resolve within the traversed set and classify the clause an
  `inspection-limitation`. A to-do list the run cannot act on becomes a gap
  report about the product.
- **Reading the default branch for a merged PR.** The question is what the code
  did at the revision the evidence was produced at. `--revision` takes the PR's
  `mergeCommit`, and a read at any other revision is about a different
  document.
- **Letting a configuration-time fact stand in for a runtime one.** A filter's
  membership in the list a validator checks establishes which configurations
  are rejected. It establishes nothing about what happens when the filter
  errors, is unavailable, or is bypassed at runtime.
- **Reporting an unanswered question as a defect.** Three different things get
  written as "not covered": something inspected shows it missing, what was
  inspected does not settle it, and nothing could be inspected. Only the first
  is engineering's. Say which.
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
- **Treating the HTML file as somewhere a Jira reader can go.** It is a file on
  one machine. Link it from the comment only when someone hands you a URL that
  already serves it.
- **Inferring delivery confidence from the counts.** Nine met is not "on track"
  without a release target and qualification evidence. `Not assessed` is the
  honest answer and the script will insist on it.
- **Naming an owner for a gap.** "The Metering epic covers SC6" is a claim about
  an epic nobody traversed. Say "identify and link the work covering SC6" unless
  a source you read names the owner.
- **Inventing a link, or pasting a local path.** `~/.jira-github-rollup/...` in a
  Jira comment publishes someone's home directory; the assembler blocks it, but
  do not write it in the first place.
