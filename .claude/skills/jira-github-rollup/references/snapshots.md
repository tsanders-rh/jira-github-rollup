# Snapshots and trend metrics

How a rollup run records what it found, finds the run before it, and reports the
movement between the two.

The trend section exists to answer "did anything move since last time". It is
**not** an estimate of effort, completion, or release readiness, and nothing in
here may be presented as one. Every number below is an unweighted count of
requirements or issues.

## Storage

Snapshots are plain JSON files under a fixed path in the user's home directory:

```
~/.jira-github-rollup/snapshots/<JIRA-KEY>/<TIMESTAMP>-<draft|published>.json
```

```
~/.jira-github-rollup/snapshots/
  RHOAIENG-1234/
    20260918T101500Z-published.json
    20261005T142203Z-published.json
    20261102T090412Z-draft.json
  RHOAIENG-1240/
    20261004T173055Z-draft.json
```

- `<JIRA-KEY>` is the issue the rollup is *about* — the one the user named. Child
  requirements read for their criteria do not get their own directory.
- `<TIMESTAMP>` is the run's UTC generation time, `YYYYMMDDThhmmssZ`. It sorts
  lexically, which is how "the most recent" is determined. No clock arithmetic.
- The suffix mirrors the `publication` field inside the file. The field is
  authoritative; the suffix exists so `ls` is legible, and a run that publishes a
  snapshot renames the file to keep the two in step.

Why this location: the skill runs from whatever directory the user happens to be
in, so a path relative to the working directory would scatter snapshots and
occasionally commit them to an unrelated repository. A fixed home-directory path
is stable across runs, outside any git tree, and easy for the user to inspect or
delete.

`rollup.py assemble` writes the file; `rollup.py promote` is the only thing that
rewrites one. Do not hand-write a snapshot. `$JGR_HOME` moves the whole tree,
and `--snapshot-dir` moves one run's store, which is how the tests keep out of
the user's real history.

The sibling directory `~/.jira-github-rollup/cache/<JIRA-KEY>/` holds raw `gh`
responses. It is **not** a snapshot store: it is overwritten freely and may be
deleted at any time. See `references/pipeline.md`.

### Rules for the store

- **Never overwrite a snapshot, and never delete one.** Each run writes a new
  file. Editing a Jira comment in place is what the skill does to avoid comment
  spam; it must not be allowed to destroy the baseline, which is exactly why the
  baseline lives here and not in the comment.
- **Promotion is the one exception, and it is additive.** When a drafted rollup
  is approved and posted, set `publication: "published"`, fill `publishedAt`,
  `jiraCommentId` and `published`, and rename the file's suffix. Same file,
  same timestamp — it is the same run.
- **The assessment payload is immutable.** `jira`, `mappings`, `scope`,
  `access`, `outcomes`, `requirements` and `inventory` are written once and
  never modified, by promotion or anything else. Publication is a fact about a
  Jira comment; it must never be able to edit what was judged. A re-render of a
  past snapshot reproduces the old judgements for the same reason.
- **Draft snapshots accumulate.** They are a few kB each. Do not prune them
  automatically; if the user asks, offer to delete drafts older than the most
  recent published snapshot, and never delete a published one without being asked
  for that specific file.
- **The files contain verbatim Jira text,** including criteria from private
  issues. They are local, unencrypted, and never transmitted anywhere. Say so if
  the user asks what is stored.
- A write failure (no permission, disk full) is reported and the rollup still
  proceeds. A missing snapshot degrades the trend section; it does not block the
  rollup, which is the part the user asked for.

## Schema

`schemaVersion` is `2`. Version 1 is still readable — see **Reading a v1
baseline** below. Every field is required; `null` or `[]` is written rather than
the key omitted, so a missing key always means a schema problem rather than an
absent finding.

```json
{
  "schemaVersion": 2,
  "rulesVersion": "2026-10-10",
  "jiraKey": "RHOAIENG-1234",
  "generatedAt": "2026-10-05T14:22:03Z",
  "publication": "draft",
  "publishedAt": null,
  "jiraCommentId": null,
  "baseline": { "generatedAt": "2026-09-18T10:15:00Z", "publication": "published" },

  "jiraStatus": "In Progress",
  "rollupStatus": "In progress",
  "jiraSummary": "Tiered quota enforcement",
  "jiraSite": "https://issues.example.com",
  "jiraFixVersions": ["2.26"],

  "mappings": [
    {
      "epic": "example-org/example-gateway#412",
      "url": "https://github.com/example-org/example-gateway/issues/412",
      "title": "Request routing for tiered models",
      "linkSource": "upstream-development-section"
    }
  ],

  "scope": {
    "sourceIssues": ["RHOAIENG-1234", "RHOAIENG-1240"],
    "children": [
      {
        "ref": "example-org/example-gateway#413",
        "title": "request routing",
        "state": "CLOSED",
        "stateReason": "COMPLETED",
        "closedAt": "2026-09-18T09:02:11Z",
        "epics": ["example-org/example-gateway#412"],
        "contentHash": "3f2a…",
        "accessible": true,
        "prs": [
          { "ref": "example-org/example-gateway#520", "state": "merged",
            "mergedAt": "2026-09-18T08:41:00Z", "baseRef": "main" }
        ]
      }
    ],
    "otherInspected": ["example-org/example-meter#9"],
    "dependencies": [
      { "ref": "example-org/example-meter#9", "state": "OPEN",
        "stateReason": "", "accessible": true }
    ],
    "untraversed": [
      { "ref": "example-org/example-gateway#1445", "title": "Audit and retention",
        "nestedVia": "sub-issues", "discoveredVia": "timeline-cross-reference",
        "depth": 1,
        "reason": "reached only by timeline-cross-reference, which establishes a mention rather than membership" }
    ],
    "traversalComplete": true,
    "traversalNotes": null,
    "observed": true,
    "unobservedReason": null
  },

  "summaryNarrative": "Two to five sentences, as rendered in the full assessment's Summary.",
  "summaryTrend": "no outcome changed since the last update posted here on 2026-09-18.",
  "prose": {
    "caveats": ["…"],
    "risks": ["…"],
    "dependencies": [],
    "blocked": false
  },
  "narrative": [
    { "bullet": "evidence-established",
      "text": "Tier-based pool selection routes paid-tier requests and merged on 2026-09-18",
      "refs": [{ "sourceKey": "RHOAIENG-1234", "id": "AC1" }],
      "links": ["example-org/example-gateway#520"] }
  ],

  "access": [
    { "ref": "example-org/example-dlp", "status": "unreadable",
      "detail": "404 for this account", "observedAt": "2026-10-05T14:21:40Z" }
  ],

  "outcomes": {
    "counts": { "met": 1, "partial": 1, "confirmed-unmet": 0, "unverified": 1 },
    "caption": "Upstream evidence assessment, not release completion."
  },

  "requirements": [
    {
      "sourceKey": "RHOAIENG-1234",
      "type": "AC",
      "id": "AC1",
      "text": "Requests for a tiered model are routed to the serving pool configured for that tier.",
      "heading": "Acceptance Criteria",
      "assessment": "Evidence found",
      "evidenceState": "tested",
      "evidence": [
        { "ref": "example-org/example-gateway#520", "kind": "pr",
          "state": "merged", "at": "2026-09-18T08:41:00Z",
          "epic": "example-org/example-gateway#412" }
      ],
      "downstream": { "state": "unknown", "detail": "no downstream source inspected" },
      "unresolvedClauses": [],
      "uncoveredClauses": [
        { "text": "membership in FAIL_CLOSED_RAILS does not establish runtime fail-closed behaviour",
          "kind": "evidence-gap",
          "inspected": ["example-org/example-rails@9f2c1ab:rails/deny.py"],
          "revision": "9f2c1ab",
          "nextAction": "read pkg/proxy/handler.go at this revision" }
      ],
      "outcome": null,
      "refutingEvidence": [],
      "failureKind": null,
      "reused": false,
      "assessedAt": "2026-10-05T14:22:03Z",
      "assessedFromSnapshot": null
    }
  ],

  "inventory": {
    "collectedAt": "2026-10-05T14:21:58Z",
    "inventoryHash": "9c41…",
    "stage": "evidence",
    "epics": [
      { "ref": "example-org/example-gateway#412",
        "childRefs": ["example-org/example-gateway#413"],
        "accessible": true }
    ]
  }
}
```

Field notes that are easy to get wrong:

| Field | Rule |
| --- | --- |
| `generatedAt` | UTC, ISO 8601 with `Z`. The progress-versus-discovery test in the comparison depends on it being accurate, not rounded to a date. |
| `publication` | `"draft"` until the comment is actually posted. A draft-only run writes `"draft"` and stops. Only `promote` changes it, and only against a returned comment id — a failed or declined post leaves a draft. |
| `published` | Written by `promote --published-text`: `{kind, words, hash}` for the text that actually went to Jira. `kind` is always `"summary"`; the full assessment is never posted. Absent on a draft, and absent on a promotion that did not record the text. |
| `outcomes` | The four counts every rendering was built from, plus the caption that scopes them. Stored so a later reader sees what was reported without re-deriving it, and so a change in the mapping rules shows up against `rulesVersion`. Not used for matching or reuse. |
| `requirements[].outcome` | `null` on every row except a deliberately declared `confirmed-unmet`. The other three outcomes are derived from `assessment` and are not stored per row — storing a derived value invites the two copies to drift. |
| `requirements[].refutingEvidence` | What shows the criterion is *not* satisfied. Required for a `confirmed-unmet` claim and meaningless otherwise; `assemble` rejects the claim without it. |
| `requirements[].uncoveredClauses` | Clauses of the criterion still open after the follow-up read, each carrying the `kind` that says why — `implementation-gap`, `evidence-gap` or `inspection-limitation` — its basis, the revision that basis was read at, and a next action. Non-empty makes `Evidence found` a refusal, not a downgrade. Distinct from `unresolvedClauses`, which is for clauses nobody has *decided* yet — different lists because they need different follow-ups, from different people. |
| `scope.dependencies` | Declared dependencies with the state they were in, so the next run can notice one closing. `scope.otherInspected` records only that they were looked at; a baseline written before this field forces reassessment of anything resting on them, because unknown is not unchanged. |
| `baseline` | What *this* run compared against, so a reader of the file can reconstruct the chain. `null` on a baseline-establishing run. |
| `mappings[].linkSource` | One of `upstream-development-section`, `labelled-web-link`, `user-supplied`, `incidental-description`, `incidental-comment`. A mapping change that is only a change of source is still a mapping change. |
| `children[].ref` | Always `org/repo#number`, never a bare `#number`. This is the deduplication key. |
| `children[].stateReason` | Verbatim from `gh`: `COMPLETED`, `NOT_PLANNED`, `REOPENED`, or `""`. Do not normalize `""` to `COMPLETED`. |
| `children[].epics` | Every linked epic that reaches this child. A child reachable from two epics appears **once**, with both epics listed. |
| `access[]` | Every source that could not be read, and every source that previously could not be and now can. An empty array is a claim that everything was readable. |
| `requirements[].text` | Verbatim, exactly as the Jira states it. This is half the match key; a tidied-up copy breaks matching against every future run. |
| `requirements[].id` | Recorded for display only. **Never used for matching** — see below. |
| `evidence[].at` | Merge date for a PR, close date for an issue. `null` when genuinely unavailable; do not substitute the run time. |
| `downstream.state` | `confirmed`, `pending`, or `unknown`. Nothing else. |
| `rulesVersion` | The assessment rules the stored judgements were made under. A baseline written under a different value is reassessed in full rather than reused. Bump it in `jgr/snapshots.py` whenever a change to `references/requirements.md` would change a verdict. |
| `scope.observed` | `false` when no epic could be read at all — no mapping, or every mapping inaccessible. This is what makes the child count render `unknown` instead of a zero nobody measured, so it must never be set `true` optimistically. |
| `scope.unobservedKind` | One of `no-mapping`, `access-denied`, `not-found`, `unreadable` when `observed` is `false`. Everything a report says about an unobserved run is derived from it. A snapshot written before this field existed reads as `no-mapping`, which is what those runs already said. |
| `scope.unobservedReason` | The same thing as a phrase, for display. |
| `scope.untraversed` | Nested epics that were recorded and not walked, with the relation that found each and why it was left. Stored because both renderings read it: a limitation that only ever existed as free-text prose was one a reader could miss, and every `No evidence found` row in the run inherits it. Empty array means the traversal covered everything it found. |
| `jiraSummary`, `jiraSite` | The issue title the heading uses and the site that makes `AC1 (RHOAIENG-1234)` a link. Neither is derivable from `jiraKey`, and without them `rerender` produces a visibly different document from the one that was reviewed. `rerender --title` / `--site` override them. |
| `jiraFixVersions` | The recorded release target, for the same reason. The HTML report states it when recorded and says so when not, so leaving it out would turn a recorded fix version into "Not recorded on the Jira issue" on re-render — a different and false statement. It is also an input to delivery confidence. |
| `summaryNarrative` | The full assessment's Summary paragraph, verbatim as supplied. |
| `summaryTrend` | The rendered trend sentence. Computed against a baseline this file does not contain, so `rerender` replays it rather than recomputing it — otherwise a reviewed summary re-renders as "Baseline established." |
| `prose` | The remaining model-written sections of the full assessment: `caveats`, `risks`, `dependencies`, `trendNotes`, `blocked`. Stored for the same reason as `narrative`: a re-render that dropped the caveats would quietly remove the limitation reporting. |
| `narrative` | The Jira summary's bullet claims, each tagged with its bullet, the assessment rows it rests on, and the artifacts it links. Stored so `rerender` reproduces the text a reviewer approved instead of falling back to mechanical counts — a re-render that silently changed the prose would make the approved draft unreconstructable. |
| `narrative[].refs` | `{sourceKey, id}` pairs, both parts required. `id` alone is ambiguous: six Jira issues in one rollup each have an `AC1`. |
| `children[].contentHash` | Hash of the fields that constitute evidence — title, state, state reason, close date, body, and each PR's state, merge date and review state. **`updatedAt` is deliberately excluded**: a PR merging or a check flipping changes the evidence without touching the issue, and an `updatedAt` comparison would miss it. |
| `children[].accessible` | `false` when the child could not be read this run. A child that disappears from the list is a removal; a child that stays with `accessible: false` is a loss of access, and they are different findings. |
| `requirements[].reused` | `true` when this run carried the assessment forward rather than making it again. Provenance, not a verdict — it changes nothing a reader sees in the table. |
| `requirements[].assessedAt` | When the judgement in this row was actually made. On a reused row this is an **earlier** run's time, not this run's; that is the point of recording it. |
| `requirements[].assessedFromSnapshot` | The path of the snapshot a reused assessment came from, so the chain can be walked back. |
| `inventory.inventoryHash` | Hash of the whole collected inventory. A cheap first test for "did anything at all change"; the per-child hashes say what. |

A snapshot whose `schemaVersion` is unrecognized or higher than this file
describes is not compared against. Say that the baseline exists but could not be
read, name its date, and establish a new baseline.

### Reading a v1 baseline

v2 is v1 plus additive keys. Every v1 field is still written with its v1
meaning, so an older reader sees what it always saw and **no migration step is
required** — existing snapshot directories keep working and are not rewritten.

What a v1 baseline cannot do is support reuse. It carries no `contentHash`, so
there is no way to establish that the evidence under an assessment is unchanged,
and `diff` reports `hashesUnavailable` and reassesses everything. That happens
once per Jira issue: the run writes a v2 snapshot, and the run after it is
incremental. The same is true of a v2 snapshot written under an older
`rulesVersion`.

Do not hand-edit a v1 file to add hashes. A hash you did not compute from the
response it describes is a claim that nothing changed, which is the one thing
the field is there to prove.

## Matching requirements across snapshots

Matching, the metrics below, and the comparison after them are implemented in
`jgr/diff.py` and `jgr/metrics.py` and run as `rollup.py diff`. This section is
their specification: read it to interpret the output, or before changing the
code. Do not reimplement any of it by hand in a run.

Requirement IDs are ordinals assigned per type per source issue, so inserting a
criterion at the top of a list renumbers everything under it. **Matching on IDs
would report one insertion as six changed requirements.** Match on content:

1. **Exact.** Pair on `(sourceKey, type, normalizedText)`. Normalize for
   comparison only — Unicode NFC, trim, and collapse internal whitespace runs to
   a single space. Keep the verbatim text in the snapshot.
2. **Near.** Among what is left, within each `(sourceKey, type)` group, pair
   texts that are clearly the same statement edited — a shared opening clause, a
   single changed number, a case or punctuation fix. Pair only when exactly one
   candidate remains on each side. Record these as **text changed**.
3. **Leftovers.** Previous-only is **removed**; current-only is **added**. If a
   near-pairing was ambiguous, report removed plus added and say the pairing was
   ambiguous — two wrong pairings are worse than one honest non-match.

When a pair matches but the IDs differ, that is a **renumbering**, not a change.
Note it once ("AC2–AC4 renumbered after a criterion was inserted") so a reader
comparing to the previous comment is not confused, and do not count it among the
changes.

Child issues match on `ref`. Epics match on `ref`. Neither is reordered in a way
that matters.

`matchedPairs` records `sourceKey` and `previousSourceKey` alongside the ids,
and `metrics.like_for_like` resolves a pair through `(sourceKey, id)`. An id
alone does not identify a row: a rollup spanning six Jira issues has six rows
called `AC1`, and resolving by id picked whichever one came first.

## Metrics

Three ratios, all unweighted, all reported as `n/d (p%)`.

Percentages are rounded to the nearest whole percent from the unrounded value,
and the fraction is always shown next to the percentage so the rounding can never
hide the counts. Percentage-point deltas are computed from the **unrounded**
percentages and rounded once at the end.

**A zero denominator is `N/A`**, with the reason. Never `0%` and never `100%`.

`N/A` and `unknown` are not the same and must not be swapped:

| Value | When | Example |
| --- | --- | --- |
| `N/A` | The zero was **observed**. You counted, and there were none | The epic is readable and has no children |
| `unknown` | The count could not be observed at all | No upstream mapping; or the epic's repository returned 404 |

A 404 is not a count of zero. Rendering it `0/0` or `N/A` claims a measurement
that failed, and `0%` claims a result that was never obtained.

### Upstream issue completion

| | |
| --- | --- |
| Denominator | Every distinct child issue in scope, deduplicated by `org/repo#number` across all linked epics |
| Numerator | Children with `state = CLOSED` **and** `stateReason = COMPLETED` |
| Reported alongside | `not planned`, `closed (reason not recorded)`, `open`, `reopened` |

- **`NOT_PLANNED` children stay in the denominator** and are reported as their own
  count. Dropping them from scope silently inflates the percentage, and "we
  decided not to do it" is a scope decision a reader needs to see, not a rounding
  convenience.
- **`stateReason: ""` is its own bucket.** GitHub only began recording a reason in
  2022, so a child closed before that reports an empty reason even though it was
  completed normally. It does not count toward completion — the rule is
  `COMPLETED` or nothing — but it is named in its own count and, when nonzero,
  noted as possibly understating completion.
- **When no child could be observed, this metric is `unknown`.** Not `0/0`, not
  `N/A`, not `0%`. That covers both no upstream mapping and an epic whose
  repository could not be read — in neither case is there a denominator, and a
  zero would read as "no work done", the exact inference the skill exists to
  prevent. `N/A` is only for an epic that was read successfully and has no
  children.

### Requirement coverage

| | |
| --- | --- |
| Denominator | Every requirement extracted in step 2 |
| Numerator | Requirements assessed `Evidence found` |
| Reported alongside | `Partial evidence`, `No evidence found`, `Unable to assess` |

- **`Partial evidence` earns no fractional credit.** Not 0.5, not a weight, not a
  clause-level sub-count. It is counted once, in its own bucket, and a reader can
  see it there. Any fraction would be invented — the skill has no basis for
  deciding that a two-clause criterion is half done, and a weighted number would
  be read as progress toward release.
- **`Unable to assess` stays in the denominator.** An access failure or a missing
  mapping does not shrink what was committed to. Removing those rows would make
  losing access look like an improvement.
- When `Unable to assess` is nonzero, its count appears immediately next to the
  percentage. When it equals the total, add the sentence: *no requirement could be
  assessed; 0% reflects absent assessment, not absent implementation.*
- **Counts are typed.** Report acceptance criteria, success criteria, and
  definition-of-done items separately. Only the total may be labelled
  "requirements"; it may never be labelled "acceptance criteria".

### The outcome tally

The same requirements, bucketed for the reader rather than for the ratio. The
coverage ratio above answers "what did the evidence establish"; the four
outcomes answer "how many of the things we committed to are met". Both are
computed from the same `assessment` field, by `jgr/outcomes.py`:

| Outcome | From |
| --- | --- |
| `met` | `Evidence found` |
| `partial` | `Partial evidence` |
| `unverified` | `No evidence found`, `Unable to assess` |
| `confirmed-unmet` | A declared `outcome` with `refutingEvidence`; never derived |

- **The four are mutually exclusive and sum to the total.** `tally()` asserts
  that rather than assuming it: a reader who adds the four numbers and gets a
  different total has reason to distrust the whole report.
- **`confirmed-unmet` is never inferred from absence.** "We looked and found
  nothing" and "we looked and found that it does not work" are different
  findings, and collapsing them turns an untracked requirement into a failed
  one — sending a reader to argue with a team that may have shipped the work
  somewhere nobody linked.
- **No percentages.** The tally is counts and a caption, never `3/9 (33%)`. The
  coverage ratio is where a percentage belongs, and even there it carries its
  fraction.
- The trend line compares tallies only when they are comparable. A changed
  criteria set or changed source access is stated instead of a delta, because
  the two tallies are not measuring the same thing.

### Downstream qualification

| State | Rendered as | Means |
| --- | --- | --- |
| `confirmed` | Verified, with evidence | A downstream artifact was inspected and establishes the requirement downstream |
| `pending` | Inspected; no qualifying evidence found | A specific downstream step was identified and inspected, and has not completed |
| `unknown` | Not inspected | No downstream state was inspected, or none was identified to inspect |

The labels are long because the short ones were being read as each other.
`metrics.DOWNSTREAM_LABELS` owns them, and the full assessment and the HTML
both use that one copy.

`confirmed + pending + unknown` equals the requirement total, which is the same
denominator as coverage.

**Uninspected is `unknown`, never `pending` and never failed.** `pending` is a
finding about an artifact someone looked at. As of this version the skill
inspects no downstream source at all, so the honest result on most runs is that
every requirement is `unknown` — including requirements whose upstream evidence
is `tested`. That is not a defect in the report; it is the state of the input.
Reporting those as `pending` would invent a step nobody has identified.

## Comparison

### Choosing a baseline

| Situation | Baseline | Say |
| --- | --- | --- |
| A published snapshot exists | The most recent published one | `Baseline: published snapshot 2026-10-05.` |
| Only draft snapshots exist | The most recent draft | `Baseline: draft snapshot 2026-10-05 (never published).` |
| None exist, or none readable | — | `Baseline established — no prior snapshot available.` |
| The most recent is unreadable or a future schema | — | Name its date, say it could not be read, establish a new baseline |

Published is preferred over a more recent draft because the published snapshot is
what a reader of the Jira issue actually last saw; the trend section is addressed
to them. Always state which baseline was used and whether it was published — a
delta against an unpublished draft is a different claim and must be labelled.

**A run whose traversal was incomplete is still snapshotted, and can still
become the next run's baseline.** `select_baseline` filters on readability and
schema, not on completeness: a run that lost access to a repository, or stopped
at an undeclared nested epic, writes the same kind of file as a clean one. The
comparison against it is therefore between what was seen then and what was seen
now, which is what the trend section claims and no more. The stopping points are
recorded in `scope.untraversed` and `access`, so say what was missing from the
baseline whenever the delta would otherwise read as movement: scope that
reappears when access is restored is newly observed, not newly done.

**Never fabricate a baseline.** A first run has no history, and the line for that
is `Baseline established — no prior snapshot available`. Do not infer a previous
state from the Jira's own history, from issue creation dates, or from an existing
rollup comment that has no snapshot behind it. A comment is rendered prose; it is
not a baseline.

### Classifying what changed

Report these separately. Collapsing them is what turns a report into a
misleading one:

| Change | Detected by |
| --- | --- |
| Requirement added | Match pass 3, current-only |
| Requirement removed | Match pass 3, previous-only |
| Requirement text changed | Match pass 2 |
| Mapping changed | `mappings[]` differs — epic added, removed, or its `linkSource` changed |
| Issue reopened | A child `CLOSED` in the baseline and `OPEN` now, or `stateReason = REOPENED` |
| Access changed | `access[]` differs in either direction, or a child's `accessible` flips |
| Artifact added or removed | A `ref` present on one side only |
| Artifact content changed | `contentHash` differs — this is what catches a PR merging or a check flipping with no change to the issue |
| Assessment changed | A matched requirement's `assessment` differs |

An assessment change is then split by **what caused it**, which the evidence
timestamps decide:

| Cause | Test |
| --- | --- |
| **Implementation progress** | At least one newly supporting piece of evidence has `at` **after** the baseline's `generatedAt` |
| **Newly discovered evidence** | Every newly supporting piece of evidence has `at` **at or before** the baseline's `generatedAt` — the work already existed and this run could finally see it |
| **Undetermined** | The evidence carries no usable timestamp. Say so; do not default to progress |
| **Regression** | The assessment moved backwards. Name the cause: a reopened issue, a reverted PR, lost access, or changed requirement text |

The progress-versus-discovery split matters because they are different news.
Access being restored, or someone finally adding the epic link, can move four
requirements to `Evidence found` in a single run without a line of code having
been written that month. Reporting that as a month's progress would be false.

### Denominator changes

When the requirement or child count differs between snapshots, the raw percentage
comparison is not like-for-like and must not be presented as one. Report both:

1. The headline ratio for each snapshot, as measured.
2. The movement **restricted to the matched set** — requirements present in both
   snapshots with unchanged text.
3. A sentence naming the scope change and its direction.

Added scope lowers a percentage without anything having gone backwards. That must
be stated in the same breath as the percentage, not left for the reader to work
out: *"Coverage 8/22 (36%), previously 8/20 (40%). Two requirements were added;
no requirement lost evidence."*

**Movement is only ever computed over the matched set.** When the total moved,
the Jira summary's trend line reports the scope change and says the outcome
counts are not comparable across it, rather than printing a delta. Nine
criteria becoming forty-nine is a scope event; rendering it as `unverified
4→42` states forty-two problems, none of which anyone found. The like-for-like
figure belongs in the full assessment, which has room to qualify it.

### Labelling

Every trend section carries, once:

> Unweighted counts of requirements and child issues. Not a measure of effort
> completed, work remaining, or release readiness.

Do not report velocity, burn-down, a projected completion date, or a derived
rate. Two data points and an unweighted count support none of those, and the
section is deliberately built so that nobody can read one out of it.
