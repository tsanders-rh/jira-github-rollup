# The pipeline: commands, storage, recovery

Read this when a command fails, when you need an option the procedure did not
mention, or when you want to know where something is stored.

Everything runs from `.claude/skills/jira-github-rollup/scripts/`. Python 3.9+,
standard library only. The only external dependency is `gh`, already
authenticated; no new credential is introduced, and nothing here can reach
Jira — MCP results come from you, as structured input.

## What runs where

| Work | Who | Why |
| --- | --- | --- |
| Normalizing and deduplicating GitHub references, tiering them, deciding whether to ask | script | Mechanical, and the ask-table is easy to drift from |
| Traversing epics, children, PRs; caching raw responses | script | Bounded set, fixed in code |
| Detecting what changed since the baseline | script | Content hashes, not `updatedAt` |
| Counting, percentages, buckets, pp deltas, like-for-like | script | Every one of these has a rule that reads as arbitrary until it is violated |
| Rendering the report; writing and promoting the snapshot | script | Section order and the partial shape are contracts |
| Reading the Jira and passing its fields in | you | Jira is MCP-only |
| Extracting requirements verbatim | you | Language judgement |
| Deciding what evidence establishes | you | The whole point |
| The Summary, caveats, risks, extra trend notes | you | Prose |

## Storage

```
~/.jira-github-rollup/            (or $JGR_HOME)
├── snapshots/<JIRA-KEY>/
│   └── 20261102T090412Z-draft.json      append-only; never overwritten
└── cache/<JIRA-KEY>/
    ├── issue/example-org-example-gateway-412.json
    ├── pr/example-org-example-gateway-520.json
    ├── pr-files/…
    ├── pr-checks/…
    ├── source/example-org-example-gateway-9f2c1ab-pkg-filters-registry-go.json
    └── followups.json                    the source-read ledger and its budget
```

The manifest names `cacheDir` once and records every `bodyPath` and evidence
`path` relative to it. `excerpt` resolves them for you from `--key` and `--ref`,
so you rarely need to join them by hand.

The two directories have opposite rules on purpose. The **cache** holds raw
responses, is overwritten freely, and may be deleted at any time — it is how
raw payloads stay out of the conversation. The **snapshot store** is the record
of what each run found, and it must survive the Jira comment being edited in
place, because that comment is not a reliable baseline.

"Append-only" is precise about one thing and loose about another, so here is
the exact rule. **No run ever reads, rewrites or deletes another run's
snapshot** — it writes a new dated file and nothing else. **The assessment
payload is immutable once written**: `jira`, `mappings`, `scope`, `access`,
`outcomes`, `requirements` and `inventory` are never modified after the run
that produced them.

`promote` is the single exception, and it is additive. On a successful post it
sets `publication`, `publishedAt`, `jiraCommentId` and `published` on one
snapshot, and renames `-draft.json` to `-published.json`. It touches no
requirement, no assessment, no evidence item and no count — what was judged
stays exactly as judged, and only the record of *whether it was published*
changes. That separation is the point: publication is a fact about a Jira
comment, not about the assessment.

Collection does not read the cache by default: change detection depends on this
run actually asking GitHub. `--offline` reuses what is cached, for re-rendering
without network access.

## Commands

### `refs`

```bash
python3 rollup.py refs --in jira-text.json --out refs.json
```

Input:

```json
{
  "jiraKey": "RHOAIENG-1234",
  "description": "…",
  "descriptionSections": [{"heading": "Upstream Development", "text": "…"}],
  "webLinks": [{"label": "Upstream epic", "url": "https://github.com/…"}],
  "comments": [{"id": "1", "created": "2026-09-01T00:00:00Z", "body": "…"}],
  "userSupplied": ["https://github.com/example-org/example-gateway/issues/412"]
}
```

Output carries `epics` (roll these up), `explicit` / `incidental` (with where
each was found), `nonIssueReferences` (PRs, boards, milestones, bare repos — no
children to traverse), `question` (ask it verbatim if present), `mappingFound`,
and `notes` to repeat in the draft.

Link tiers, and when to ask:

| Situation | Behaviour |
| --- | --- |
| Two or more explicit links | All of them are rolled up. No question. A requirement spanning a data plane and a control plane genuinely has two epics. |
| No explicit, exactly one incidental | Used, with a note that it came from an unlabelled source |
| No explicit, several incidental | `question`, listing each with where it was found |
| Incidental extras beyond the explicit set | Explicit set rolled up; extras offered as a `question`. Never dropped silently, never folded in silently. |
| A PR, board, milestone or bare repo | Listed in `nonIssueReferences`; ask for the epic issue |

### `collect`

```bash
# Stage 1 - inventory
python3 rollup.py collect --key <KEY> --epics refs.json --out manifest.json

# Stage 2 - verification evidence for named PRs only
python3 rollup.py collect --key <KEY> --epics refs.json --stage evidence \
  --manifest manifest.json --targets '["example-org/example-gateway#520"]' \
  --out manifest.json
```

`--epics` accepts the `refs` output, a JSON array of refs, or `-` for stdin.
`--key` is required when the epic list does not carry `jiraKey`. An empty epic
list produces the empty manifest — `observed: false`, which is what makes the
child count render `unknown` rather than a zero nobody measured.

Children are discovered by union of three relations, deduplicated across epics
with every originating epic retained. They are not equally strong, and
`discoveredVia` records which one found each child:

| Relation | How it is found | What it establishes |
| --- | --- | --- |
| `sub-issue` | the native GitHub sub-issue relation | A declared parent-child link |
| `task-list` | `- [ ] org/repo#123` or a full issue URL in the epic body | The epic author listed it as part of the work |
| `timeline-cross-reference` | `cross-referenced` and `connected` events on the epic | **Only that something mentioned the epic** |

The third is deliberately inclusive and will pull in loosely related issues — a
"see also", a duplicate, a discussion that linked the epic once. The bias is
toward over-collection: a child wrongly included costs a row a reader dismisses,
while a child wrongly excluded becomes "no evidence found" for a criterion that
was in fact covered. When an assessment rests on a timeline-only child, weigh
it accordingly and say what the relation was.

**Dependencies are a different relation, not a weak child.** `depends on`,
`blocked by` or `requires` followed by an issue reference, in an epic or child
body. They are fetched for their state and never traversed.

Traversal stops in three places, each recorded rather than silent: PRs are
leaves (their cross-references are not followed), dependencies are leaves, and
a child that looks like an epic itself is marked `nested`, with `nestedVia`
saying how it was judged:

| `nestedVia` | Test |
| --- | --- |
| `label` | The child carries an `epic`, `feature` or `initiative` label |
| `sub-issues` | GitHub reports two or more native sub-issues under it |
| `body-references` | Fallback, only where the sub-issues endpoint 404s: two or more issue references in the body, after dropping the child itself and the epics being traversed |

The fallback drops upward references because a leaf that names its parent and a
sibling is not a parent. Each false positive subtracts from what the report
claims to have covered, so the error reads as a gap that is not there. Judging
on the native sub-issue list costs one `gh` request per unlabelled child.

#### Nested epics

A nested epic is traversed **one further level, and only when a declared
relation found it** — `sub-issue` or `task-list`, the two in
`collect.DECLARED_RELATIONS`. Its children are attributed to it (they carry the
nested epic in `epics`, and `depth: 2`), and it is marked `nestedTraversed`.

The rule keys on the discovery relation rather than on nesting, because the
relations establish different things. A task-list entry is the epic author
saying "this is part of the work". A `timeline-cross-reference` is someone
having mentioned the epic once — descending through it would attach an
unrelated tree of issues to this Jira issue's criteria, and every row they
touch would be assessed against work nobody claimed was in scope.

Anything not traversed goes in `manifest.untraversed`, one entry per epic:

```json
{"ref": "example-org/example-gateway#1445", "title": "…",
 "nestedVia": "sub-issues", "discoveredVia": "timeline-cross-reference",
 "depth": 1,
 "reason": "reached only by timeline-cross-reference, which establishes a mention rather than membership"}
```

The other `reason` is `already 1 level below the mapped epic` — the depth
cap, which exists so one run cannot walk an org. Both renderings read this list
directly: the full assessment names each entry under **Not traversed**, and the
Jira summary's scope caveat counts them. That is the whole point of it being
structured — an untraversed branch that only showed up as free-text prose was
a branch a reader could miss, and every "no evidence found" row in the report
inherits the omission.

Cycles terminate: a ref already visited is not queued again, so a child that
lists its own parent walks nowhere.

A `403` on the sub-issue list of a readable issue is a limitation, recorded in
`access`, not an empty branch. The two used to be indistinguishable, which hid
a whole subtree behind "this epic has no children".

`stateReason` is recorded in four buckets and never normalized:

| `state` / `stateReason` | Means |
| --- | --- |
| `CLOSED` / `COMPLETED` | Done. The only thing counting toward completion |
| `CLOSED` / `NOT_PLANNED` | A scope decision — a flag, not progress, not removed from scope |
| `CLOSED` / `""` | Closed before GitHub recorded a reason (pre-2022). Not countable as completed |
| `OPEN` / `REOPENED` | Was closed, is not now |

`gh pr checks` exits `1` when a check failed and `8` when checks are pending;
both are findings and the JSON on stdout is the answer, so the client treats
them as success.

Per-child `contentHash` deliberately excludes `updatedAt`. A PR merging, a check
flipping or a review landing changes the evidence without touching the issue,
and an `updatedAt` comparison would miss every one of them.

### `diff`

```bash
python3 rollup.py diff --manifest manifest.json --requirements requirements.json \
  [--full-refresh] [--with-baseline] --out diff.json
```

Returns `baseline`, `reassess`, `reuse`, `requirementChanges` (added, removed,
textChanged, ambiguous, renumbered), `inventoryChanges` (artifactsAdded,
artifactsRemoved, contentChanged, hashesUnavailable, reopened, accessLost,
accessRestored, dependenciesChanged), `mappingChanged`, and `matchedPairs`.

A requirement is reassessed when any of these hold:

- it is new, or its text changed, or it could not be matched to exactly one
  previous requirement;
- an artifact its stored evidence rests on changed, was removed, was reopened,
  or changed access;
- an artifact appeared in a repository its stored evidence comes from, even
  where it was fully covered. A new artifact matches no stored ref, so without
  this a requirement assessed `Evidence found` would never be looked at again,
  and a later PR narrowing or contradicting that coverage would be reused
  straight past. Scoped to the repository, so one new child does not reassess
  the whole set;
- it was not previously `Evidence found` and anything upstream changed — a
  requirement with no coverage is exactly the one a new artifact might cover;
- a declared dependency it rests on changed state, was added, was removed, or
  changed readability;
- its stored downstream state is `pending`. Downstream artifacts are outside
  the traversal, so no hash here can ever contradict one; reusing it would
  republish "qualification outstanding" long after anyone checked. The other
  two are reusable: `unknown` is nobody looked then and nobody looked now, and
  `confirmed` is an event that already happened and that no later run makes
  false — where the implementation under it has since moved, the evidence rules
  above have already caught the requirement;
- the baseline carries no assessment for it, or carries no content hashes
  (schema v1) to verify reuse against;
- the mapping changed, the rules version changed, a full refresh was asked for,
  or nothing was observed this run.

The bias is deliberate. A wasted assessment costs tokens; a wrongly reused one
costs the report its credibility.

### `assemble`

```bash
python3 rollup.py assemble --in assembly.json --manifest manifest.json \
  --diff diff.json --requirements requirements.json \
  --assessments assessments.json --narrative narrative.json \
  --report full-assessment.md --summary jira-summary.md \
  --html full-assessment.html --out result.json
```

`assembly.json`:

```json
{
  "jira": {"key": "RHOAIENG-1234", "summary": "…", "status": "In Progress",
           "site": "https://your-site.atlassian.net",
           "fixVersions": ["2.26"], "children": [{"key": "RHOAIENG-1240", "summary": "…", "status": "New"}]},
  "mappings": [{"ref": "example-org/example-gateway#412", "url": "https://github.com/…",
                "title": "…", "linkSource": "upstream-development-section"}],
  "summary": "Two to five sentences.",
  "narrative": [{"bullet": "evidence-established", "text": "…",
                 "refs": [{"sourceKey": "RHOAIENG-1234", "id": "AC1"}],
                 "links": ["example-org/example-gateway#520"]}],
  "caveats": ["example-org/example-dlp returned 404 for this account."],
  "dependencies": [{"ref": "RHOAIENG-1250", "criteria": ["SC9"], "note": "Named in the description."}],
  "risks": [],
  "trendNotes": [],
  "blocked": false
}
```

`summary` is the full assessment's Summary paragraph. `narrative` is the Jira
summary's four bullets — one entry per claim, `bullet` naming which of
`evidence-established`, `remaining-work`, `decisions-needed`, `next-actions` it
belongs under. `--narrative narrative.json` supplies the same list from its own
file, which is usually easier to iterate on. A bullet with no claim falls back
to a mechanical sentence built from the counts; that is a floor, not the
intent. `references/rollup-format.md` has the contract.

`jira.site` is what makes a criterion clickable — criteria have no anchors in
Jira, so they are linked as `RHOAIENG-1234 SC5` against the parent. Without it
they render as unlinked text rather than as a guessed URL. `jira.fixVersions`
is one of the inputs to delivery confidence.

`dependencies` is the *only* way a named owning ticket reaches the output. The
renderer never infers one from a gap: an unowned criterion produces "identify
and link the work covering SC6", not a claim about an epic nobody traversed.

| Flag | Effect |
| --- | --- |
| `--report PATH` | Writes the full assessment |
| `--summary PATH` | Writes the Jira summary draft |
| `--html PATH` | Writes the standalone HTML full assessment. A local file, never a Jira link |
| `--narrative PATH` | The Jira summary's bullet claims, as above |
| `--full-assessment-url URL` | Adds a "Full assessment" link to the summary. Dropped unless it is an absolute `http(s)` URL — a local path, a `file://` URL and a bare filename are all refused. **Not** where the `--html` path goes |
| `--no-snapshot` | Renders without writing one. For iterating on wording, not for a real run |
| `--snapshot-dir` | Overrides the location |

`result.json` carries `outcomes` (the four counts), `deliveryConfidence`,
`summaryWords`, `summaryWordBudget`, `summaryBudgetNotice`, `narrativeClaims`,
`snapshotPath`, the three ratios, `reused`/`assessed`, and `htmlBytes` — with
`htmlPath` when `--html` named one. The HTML is rendered on every run so the
cross-check always covers it, and is written only when asked for. It is never
printed: a quarter of a megabyte of markup on stdout is exactly the kind of raw
payload the cache exists to keep out of the conversation.

`summaryWordBudget` is `{floor, ceiling, within, condition, authored,
refsPerBullet}`. `condition` is `within-budget`, `under-floor` or
`over-ceiling`, and `authored` splits the count into the narrative bullets and
the overall assessment — the half the model can shorten. `over-ceiling` also
prints `summaryBudgetNotice` on stderr, because the draft reaches a person for
approval and `result.json` may not. **It is an instruction to rewrite and
re-assemble, not a statistic**; nothing in the renderer can act on it, and the
run still finishes and still writes the draft.

Seven ways this command refuses rather than emitting something wrong:

- A requirement with no fresh and no reusable assessment. It will not invent one.
- An evidence ref that resolves to nothing — not in the manifest, or a source
  read this run did not make — or one whose supplied `kind`, `state` or `at`
  disagrees with what was collected. The three fields are joined from the
  manifest and the source-read ledger, so a cited ref either names something
  the run holds or names a mistake; see `references/requirements.md`.
- An `Evidence found` carrying a non-empty `unresolvedClauses` or
  `uncoveredClauses`. `Evidence found` claims every clause of the criterion
  holds; an open clause makes it `Partial evidence`.
- A `confirmed-unmet` declared without `refutingEvidence`, or declared on an
  assessment other than `No evidence found`. Absence of evidence is `unverified`.
- A disagreement between the renderings — the outcome row missing from one,
  counts that do not sum to the criteria total, by-type rows in the HTML that
  do not add up to the tally, a count stated in the summary's prose that the
  tally contradicts, or a local path in the summary or the HTML.
- An untraceable narrative claim: one citing a requirement not in this run,
  citing no row at all, linking an artifact that is not evidence on any row it
  cites, or filed under `evidence-established` while resting on an `unverified`
  row.
- An unscoped existence claim in either output — "no upstream issue exists",
  "not implemented anywhere". The walk covered the mapped epics and what they
  declare; it did not cover GitHub. Scope the sentence to the sources inspected.

The last two are structural. They establish that a claim is attached to rows
and sources that exist; they do not establish that it is correct. A sentence
that misreads what a merged PR does passes both.

The status line is derived, not supplied. `Complete` requires every requirement
at `Evidence found`, no downstream step outstanding, and every child closed.
`blocked: true` is the one override, for evidenced blockage.

When nothing was observed the status names **why**, from the manifest's
`unobservedKind`. "No link was recorded" and "the link is there and we were
refused" have different owners, and reporting the second as a missing mapping
sends someone to fix a link that is already correct:

| `unobservedKind` | Status | What it asks for |
| --- | --- | --- |
| `no-mapping` | `Unknown — upstream mapping missing` | The epic URL, recorded on the Jira issue |
| `access-denied` | `Unknown — upstream access denied` | Read access for the credential `gh` runs under |
| `not-found` | `Unknown — upstream epic not found` | A corrected link; the one recorded resolves to nothing |
| `unreadable` | `Unknown — upstream epic unreadable` | A re-run, once the cause of the failure is known |

The wording for each kind — status, `unobservedReason`, the Gap column, and the
"What is needed" bullets — lives in `jgr/scope.py` and nowhere else.

### `rerender`

```bash
python3 rollup.py rerender --snapshot <path> \
  --report full-assessment.md --summary jira-summary.md \
  --html full-assessment.html --out result.json
```

`--site` and `--title` are overrides, not required input: the snapshot carries
`jiraSite` and `jiraSummary`.

Rebuilds every output from a stored snapshot. No collection, no reassessment, no
new snapshot — the stored assessments are passed straight back in, so the
judgements are exactly the ones that were made at the time. `--html` is the
supported way to produce the HTML report for a run that did not ask for one,
and it needs no network and no cache: the test suite proves it by deleting the
cache and pointing `GH_BIN` at a binary that always fails.

Use it to regenerate a report after a rendering change, or to see what a past
run would look like under the current renderer. It cannot change an outcome: a
snapshot written before a rule existed is re-rendered under the old judgements,
which is the point.

Evidence is not re-joined here. The stored items were resolved against the
manifest of the run that made them; the manifest reconstructed from a snapshot
is thinner than that one, so re-deriving would re-judge a reviewed document
against a poorer record of the world.

`summaryWordBudget.condition` is still reported, and the `over-ceiling` notice
is not printed. The prose is the stored prose and this command cannot change
it; telling someone re-rendering a published comment to rewrite it before
approval is advice about an approval that already happened.

The prose comes back with it. A snapshot stores `summaryNarrative` (the full
assessment's Summary paragraph) and `narrative` (the Jira summary's bullet
claims), so re-rendering reproduces the summary a reviewer approved rather than
falling back to mechanical counts. `--narrative` overrides the stored Summary
paragraph; there is no flag that re-judges anything.

Everything else the outputs are rendered with comes back too: `summaryTrend`
(the trend sentence, which was computed against a baseline the snapshot does
not contain), `prose` (caveats, risks, dependencies), the Jira title, site and
`fixVersions`, and `publication`. The last two matter to the HTML: without the
fix versions stored, a re-render would turn a recorded release target into "Not
recorded on the Jira issue"; without `publication`, it would stamp "Draft — not
published" over text already sitting on the issue. The full assessment's trend
*table* is rebuilt by reloading the baseline snapshot named in
`baseline.generatedAt`; if that file is gone the section says a baseline existed
and could not be read, rather than claiming a first run.

Two things do not survive a re-render, because the snapshot does not record
them: the per-field `diff` detail behind bullets like "Mapping changed", and
anything derived from the live inventory. The summary and the HTML reproduce
exactly; the Markdown full assessment can differ by a line in the trend
section.

### `excerpt`

```bash
python3 rollup.py excerpt --key <KEY> --ref example-org/example-gateway#413 --field body
python3 rollup.py excerpt --key <KEY> --ref example-org/example-gateway#520 --kind pr-checks \
  --field '' --match 'fail' --context 1 --max-chars 2000
```

`--kind` is `issue`, `pr`, `pr-files` or `pr-checks`. `--field` walks a dotted
path into the payload; `pr-checks` is cached as a bare list, so it takes
`--field ''` — the whole document — and a field path into it fails rather than
returning nothing. A field the collector never asked `gh` for fails the same
way, and the error names what the payload does carry, so a typo and a field
that was never collected do not look alike. Truncation is always reported in
`truncated`, with
`fullChars` and the `path` to the whole file, so a short read can be widened
rather than mistaken for the whole artifact.

Prefer `--match` to reading a payload whole. A field that is not already text
is rendered one key per line, so `--match 'fail' --context 1` returns the few
checks that failed instead of all of them.

### `source`

```bash
python3 rollup.py source --key <KEY> --repo example-org/example-rails \
  --path rails/deny.py --revision 9f2c1ab \
  --match 'FAIL_CLOSED_RAILS|on_error' --context 4
```

One source file at one revision, read through the same windowing as `excerpt`:
`--match`, `--context`, `--max-chars`, and `truncated`/`fullChars` reported the
same way. It exists for the follow-up read described in
`references/requirements.md` — resolving a specific question from a source the
evidence already named, rather than reporting the question as a gap.

`--revision` is **required and has no default.** A read of today's default
branch says nothing about the commit a merged PR produced, and the collector
records each merged PR's `mergeCommit` for exactly this. Pass that.

The budget is **12 distinct source reads per Jira key**, tracked in
`cache/<KEY>/followups.json`. A file already read at a revision is served from
the cache, reports `reused: true`, and spends nothing. `--budget` raises or
lowers the ceiling for one command; raising it is a decision to report.
Deleting the cache resets the count, which is also a decision a person makes.

Every call answers one of two ways, and the field to branch on is `inspected`:

| | Carries |
| --- | --- |
| `inspected: true` | the windowed `text`, `sha`, `budget`, `reused` |
| `inspected: false` | `limitation` — the sentence to put on the clause — and `reason`, one of `budget`, `forbidden`, `unreadable`, `error` |

It never raises and never returns an empty body in place of a failed read. A
directory, a file too large for the contents endpoint, and a 404 at a revision
that does not exist are all `inspected: false` with the constraint named, and
all of them are an `inspection-limitation` on the clause — not evidence about
the behaviour.

### `convert`, `promote`, `measure`

```bash
python3 rollup.py convert --in jira-summary.md --target html   # gfm | html | wiki | plain | adf
python3 rollup.py promote --path ~/.jira-github-rollup/snapshots/RHOAIENG-1234/2026…-draft.json \
  --comment-id 10042 --published-text jira-summary.md
python3 rollup.py measure manifest.json diff.json --label "incremental run"
```

`addOrEditJiraIssueComment` documents `commentBody` as Markdown by default, so
the usual path posts `jira-summary.md` unconverted. `--target html` is the
fallback if Markdown renders badly; it emits only the elements the Atlassian
editor accepts and escapes cell text before inserting any of them.

`convert --target adf` emits the plain-text fallback: ADF is not a markup string
and the six-column coverage table is the first thing to render badly, so each
requirement becomes a labelled block with the same fields in the same order.

`promote` is the only thing that advances the published baseline, and it
**requires a non-blank comment id** — the only evidence this process has that a
Jira update actually happened. A failed, refused or never-attempted post leaves
the snapshot a draft, because promoting on intent silently destroys the next
run's comparison. `--published-text` records a hash of what was posted (the
approved summary, not the full assessment) so a later reader can tell whether
the comment on the issue is still the text the snapshot was promoted for.

`measure` reports tokens when a tokenizer is importable and bytes/characters
otherwise, labelled either way.

## Example runs

**First run.**

```bash
python3 rollup.py refs --in jira-text.json --out refs.json
python3 rollup.py collect --key RHOAIENG-1234 --epics refs.json --out manifest.json
python3 rollup.py collect --key RHOAIENG-1234 --epics refs.json --stage evidence \
  --manifest manifest.json --targets "$(jq -c '[.children[].prs[].ref]' manifest.json)" \
  --out manifest.json
python3 rollup.py diff --manifest manifest.json --requirements requirements.json --out diff.json
# assess everything in diff.json .reassess -> assessments.json
python3 rollup.py assemble --in assembly.json --manifest manifest.json --diff diff.json \
  --requirements requirements.json --assessments assessments.json \
  --report full-assessment.md --summary jira-summary.md --out result.json
```

**Incremental run.** Identical, except `diff.json` returns a short `reassess`
list and a populated `reuse` list, and you assess only the former. Fetch stage-2
evidence only for PRs attached to requirements you are actually reassessing.

**Full refresh.** Add `--full-refresh` to `diff`. Use it when the assessment
rules changed, when a previous run was wrong, or when the user asks for one.

## When something fails

| Symptom | What it means | Do this |
| --- | --- | --- |
| `gh not found on PATH` | No `gh`, or a different name | Say so and stop; there is no fallback that stays read-only and authenticated |
| Epic entry has `accessible: false` | 404 or SAML/403 | It is in `manifest.access` with the reason. Report it prominently; `observed` may now be false |
| `manifest.observed` is false | No epic could be read | The report renders the partial shape with `unknown` counts. Do not substitute zeros |
| `traversalComplete: false` | A cap was hit or a call failed | `traversalNotes` says which. Every absence claim is weaker; say so in the Summary |
| `diff` reports `hashesUnavailable` | A schema v1 baseline | Everything is reassessed this run. Expected once per issue after the upgrade |
| `assemble` errors `no assessment supplied or reusable` | A requirement has no verdict | Assess it. The assembler will not invent one |
| `assemble` errors `is not an artifact this run traversed` | A cited ref the manifest does not carry | A typo, or work outside the traversal. Cite a ref from the manifest, or name the missing link in the gap — do not re-type the ref with fields attached |
| `assemble` errors `names a source read this run did not make` | A `repo@revision:path` ref cited without reading it | Read it with `source`, or cite the artifact the path came from |
| `assemble` errors `but what was collected says` | A supplied `kind`, `state` or `at` disagreeing with the manifest | Delete the field. The assembler joins all three; a hand-typed timestamp is the one that is wrong |
| `assemble` errors `nothing collected this run describes it` | An evidence item that is neither a ref nor a source read | Give it a `kind` — `check` for a CI job — or correct the ref |
| `assemble` errors on an assessment string | Not one of the four | Use the exact wording from `references/requirements.md` |
| `assemble` errors `claims every clause of the criterion holds` | `Evidence found` with a clause left open | Assess it `Partial evidence` and keep the clause listed. Do not empty the list to get past the error — the list is the finding |
| `assemble` errors `confirmed-unmet declared with nothing cited` | Absence was reported as refutation | Drop the `outcome` field. Absence of evidence is `unverified`, and the count is the same either way |
| `assemble` errors `is an evidence gap naming nothing inspected` | A clause claims a read did not settle something, without saying what was read | Do the follow-up read with `source`; if the file is unreadable, reclassify the clause `inspection-limitation` and state the constraint |
| `assemble` errors `is an implementation gap with nothing cited` | An unread file or an absent test was written up as missing functionality | Cite what shows the behaviour missing, or classify it `evidence-gap` naming where you looked |
| `assemble` errors `is an inspection limitation with no constraint stated` | The clause says it could not be checked but not why | Name it: access, an unavailable revision, the follow-up budget, or another stated constraint |
| `assemble` errors `is classified …, which is not one of` | A clause `kind` outside the three | Use `implementation-gap`, `evidence-gap` or `inspection-limitation`; a bare string is read as the second and then refused |
| `assemble` errors `states no next action` | An open clause the reader cannot act on | Say what would settle it. This is the whole reason the clause is in the report |
| `source` returns `inspected: false`, `reason: budget` | 12 follow-up reads spent this run | Record an `inspection-limitation` on the clause, or re-run with `--budget` raised and say in the limitations section that you did |
| `source` returns `inspected: false`, `reason: unreadable` at a revision | That path does not exist at that commit | Check the revision — it should be the PR's `mergeCommit`, not a branch. Do not substitute the default branch |
| `assemble` errors `the Jira summary does not carry the outcome row` | The two renderings disagree | A renderer bug, not a data problem. Do not hand-edit either output to agree |
| `assemble` errors `contains paths a reader cannot follow` | A local path reached the summary | Usually a `--full-assessment-url` pointing at `/tmp` or `~`. Omit it unless the URL is durable |
| `assemble` errors `which is not an assessed requirement in this run` | A narrative claim cites a row that does not exist | Check the `sourceKey`, not just the id. `AC1` exists on six issues |
| `assemble` errors `cites no assessment row` | A claim with no `refs` | Attach it to what it rests on, or drop the sentence |
| `assemble` errors `is not evidence on any row it cites` | A link the cited rows do not carry | Cite the row that carries it, or link what the rows actually hold |
| `assemble` errors `rests on …, which nothing inspected supports` | An `evidence-established` claim over an `unverified` row | Either the claim belongs under another bullet, or the row was assessed too conservatively. Fix whichever is wrong |
| `assemble` errors `claims more than a traversal can show` | An unscoped existence claim, in prose or in a `gap` | Scope it: "no upstream work in the traversed set is linked to …" |
| `assemble` errors `says N met but the tally … says M` | The prose and the table disagree | The tally is right by construction. Fix the sentence |
| `assemble` prints `notice: the Jira summary draft is N words against a 350-word ceiling` | `summaryWordBudget.condition` is `over-ceiling` | Rewrite the bullets and assemble again **before** showing the draft. The notice says how many words they have left; nothing in the renderer can recover them |
| `result.summaryWordBudget.condition` is `under-floor` | The draft is under 210 words | Reported, not enforced, and no re-run needed. Usually the bullets are a list of ids rather than a status |
| `result.overallWordBudget.within` is false | The overall assessment is outside 60–100 words | Reported, not enforced. Short usually means no position was taken; long means it stops being the thing read first |
| `result.overallWordBudget.supplied` is false | Nobody wrote an overall assessment, so all three renderings carry the mechanical fallback | Write one. The fallback restates the tally and says in its last sentence that no position was taken |
| `promote` errors `a Jira comment id is required` | Promoting without a successful post | Correct. Leave the snapshot a draft until the comment lands and returns an id |
| A snapshot "could not be read" in the trend section | Corrupt or unknown schema | Reported in the section, with the date. The run continues and establishes a new baseline |
| Snapshot write fails | Disk or permissions | Say so and continue. The rollup is the deliverable; the snapshot is bookkeeping |

## Tests

```bash
python3 -m unittest discover -s tests
```

`tests/fakegh.py` stands in for `gh` via `GH_BIN`, driven by a JSON world file,
so the real command construction and exit codes are exercised with only the
network faked. `tests/measure_run.py` prints the LLM-facing input sizes for a
full and an incremental run over the same fixture.
