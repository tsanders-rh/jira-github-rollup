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
    └── pr-checks/…
```

The manifest names `cacheDir` once and records every `bodyPath` and evidence
`path` relative to it. `excerpt` resolves them for you from `--key` and `--ref`,
so you rarely need to join them by hand.

The two directories have opposite rules on purpose. The **cache** holds raw
responses, is overwritten freely, and may be deleted at any time — it is how
raw payloads stay out of the conversation. The **snapshot store** is the record
of what each run found and is append-only, because the Jira comment may be
edited in place and the comparison baseline must survive that.

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

Children are discovered by union of native sub-issues, task-list references in
the epic body (`- [ ] org/repo#123` and full URLs), and timeline
cross-references, deduplicated across epics with every originating epic
retained. Cross-repo children keep their own repo; `crossRepo` marks them. A
child that looks like an epic itself is marked `nested` and recorded, not
traversed.

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
accessRestored), `mappingChanged`, and `matchedPairs`.

A requirement is reassessed when any of these hold:

- it is new, or its text changed, or it could not be matched to exactly one
  previous requirement;
- an artifact its stored evidence rests on changed, was removed, was reopened,
  or changed access;
- it was not previously `Evidence found` and anything upstream changed — a
  requirement with no coverage is exactly the one a new artifact might cover;
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
  --assessments assessments.json \
  --report full-assessment.md --summary jira-summary.md --out result.json
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
  "caveats": ["example-org/example-dlp returned 404 for this account."],
  "dependencies": [{"ref": "RHOAIENG-1250", "criteria": ["SC9"], "note": "Named in the description."}],
  "risks": [],
  "trendNotes": [],
  "blocked": false
}
```

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
| `--full-assessment-url URL` | Adds a "Full assessment" link to the summary. Dropped unless it is a durable URL — a local path is never published |
| `--no-snapshot` | Renders without writing one. For iterating on wording, not for a real run |
| `--snapshot-dir` | Overrides the location |

`result.json` carries `outcomes` (the four counts), `deliveryConfidence`,
`summaryWords`, `snapshotPath`, the three ratios, and `reused`/`assessed`.

Three ways this command refuses rather than emitting something wrong:

- A requirement with no fresh and no reusable assessment. It will not invent one.
- A `confirmed-unmet` declared without `refutingEvidence`, or declared on an
  assessment other than `No evidence found`. Absence of evidence is `unverified`.
- A disagreement between the two outputs — the outcome row missing from either,
  counts that do not sum to the criteria total, or a local path in the summary.

The status line is derived, not supplied: `Unknown — upstream mapping missing`
when nothing was observed, `Complete` only when every requirement is `Evidence
found`, no downstream step is outstanding, and every child is closed.
`blocked: true` is the one override, for evidenced blockage.

### `rerender`

```bash
python3 rollup.py rerender --snapshot <path> --site https://your-site.atlassian.net \
  --title "RHOAIENG-1234 Tiered quota" \
  --report full-assessment.md --summary jira-summary.md --out result.json
```

Rebuilds both outputs from a stored snapshot. No collection, no reassessment, no
new snapshot — the stored assessments are passed straight back in, so the
judgements are exactly the ones that were made at the time.

Use it to regenerate a report after a rendering change, or to see what a past
run would look like under the current renderer. It cannot change an outcome: a
snapshot written before a rule existed is re-rendered under the old judgements,
which is the point. `--narrative` supplies the Summary paragraph, which the
snapshot does not store.

### `excerpt`

```bash
python3 rollup.py excerpt --key <KEY> --ref example-org/example-gateway#413 --field body
python3 rollup.py excerpt --key <KEY> --ref example-org/example-gateway#520 --kind pr-checks \
  --field '' --match 'fail' --context 1 --max-chars 2000
```

`--kind` is `issue`, `pr`, `pr-files` or `pr-checks`. Truncation is always
reported in `truncated`, with `fullChars` and the `path` to the whole file, so
a short read can be widened rather than mistaken for the whole artifact.

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
| `assemble` errors on an assessment string | Not one of the four | Use the exact wording from `references/requirements.md` |
| `assemble` errors `confirmed-unmet declared with nothing cited` | Absence was reported as refutation | Drop the `outcome` field. Absence of evidence is `unverified`, and the count is the same either way |
| `assemble` errors `the Jira summary does not carry the outcome row` | The two renderings disagree | A renderer bug, not a data problem. Do not hand-edit either output to agree |
| `assemble` errors `contains paths a reader cannot follow` | A local path reached the summary | Usually a `--full-assessment-url` pointing at `/tmp` or `~`. Omit it unless the URL is durable |
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
