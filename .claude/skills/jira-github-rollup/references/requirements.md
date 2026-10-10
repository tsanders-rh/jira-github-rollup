# Requirements: extraction and assessment

The part of the rollup no script does. Everything here is a judgement about
language or about what a piece of evidence establishes, and both are wrong in
ways that look right in a table cell.

Read the first half at step 2, the second half at step 5.

## Extracting the requirements

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

- **Quote the statement as written.** Do not normalize, shorten, or rephrase it.
  If it is too long for a table cell, quote verbatim to a sentence boundary and
  append `…` — never paraphrase. The snapshot stores this text and the next run
  matches on it, so an edit here reads as a changed requirement later.
- Assign each one a stable ID in order of appearance, numbered **per type, per
  source issue**, rendered `<PREFIX><n> (SOURCE-KEY)`. A parent's acceptance
  criteria and a child's both start at `AC1`; the key is what tells the rows
  apart. A criterion inherited from a child is not the parent's criterion.
- **Never merge the types.** An acceptance criterion, a success criterion and a
  definition-of-done item are different commitments made by different people,
  and a reader acts on them differently. **Never report a combined count as a
  number of acceptance criteria** — count by type, or say "requirements".
- **Never synthesize a requirement.** Not from the summary, not from prose, and
  above all not from a GitHub issue title. Only text the Jira presents as a
  criterion is a criterion.
- **None found:** say so, name the sources you checked, and continue. The
  coverage section then reports there is nothing to assess against; it does not
  get filled with inferred criteria.
- **Unresolved parameter or decision** (`within the agreed latency budget
  (TBD)`) — keep it verbatim and split it at assessment time. One TBD does not
  make a criterion unassessable.
- **Nothing checkable at all** (`performance should be acceptable`): keep it
  verbatim, assess `Unable to assess`, ask the owner to restate it.

The JSON for `requirements.json`:

```json
[
  {
    "id": "AC1",
    "sourceKey": "RHOAIENG-1234",
    "type": "AC",
    "heading": "Acceptance Criteria",
    "text": "Requests for a tiered model are routed to the serving pool configured for that tier."
  }
]
```

## Assessing coverage

Take each requirement and ask what the sources you actually inspected establish
about it. **Never work in the other direction** — starting from an issue and
looking for a criterion it might satisfy is how candidate mappings get promoted
to coverage.

### Evidence state — how far the work got

| Evidence | State |
| --- | --- |
| Nothing mapped | `—` (never `planned`; that implies tracking that does not exist) |
| Mapped issue open, no PR | planned |
| PR open or draft | in progress |
| PR open with reviews requested or submitted | in review |
| PR merged | merged |
| A named job, file or test case exercising the criterion passed | tested |

The state describes the criterion as a whole. A test covering one clause of a
two-clause criterion does not make it `tested` — that is `merged` at most.

### Coverage assessment — what the behaviour is established to do

Exactly one of four, and say what it rests on:

| Assessment | Means |
| --- | --- |
| Evidence found | **Every** checkable clause of the criterion is supported by evidence you read, and no clause is undecided. State what establishes each. |
| Partial evidence | Some clauses are supported and some are not. Name the ones that are not. |
| No evidence found | The sources inspected do not establish coverage. |
| Unable to assess | An access failure, truncated results, a criterion with no checkable clause at all, or a missing upstream mapping blocked assessment. Say which. |

### `Evidence found` is a claim about the whole criterion

Most criteria are conjunctions — "routed to the pool for that tier **and**
rejected above the tier quota" is two commitments in one sentence, and a PR
that lands the routing establishes nothing about the rejection. The failure
this guards against is specific and common: evidence that the *work exists* is
read as evidence that *every clause holds*.

So before assessing `Evidence found`, split the criterion into clauses and ask
of each one what you actually read:

| Clause state | Goes in | Effect |
| --- | --- | --- |
| Supported by evidence you read | nothing; cite it in `coverageDetail` | — |
| Checkable, but nothing you read supports it | `uncoveredClauses` | blocks `Evidence found` |
| Not checkable yet — a TBD, an unset parameter, an open decision | `unresolvedClauses` | blocks `Evidence found` |

A criterion with either list non-empty is `Partial evidence` when some clauses
are supported, and `No evidence found` when none are. The assembler **refuses**
`Evidence found` with a clause open rather than quietly downgrading it: the
downgrade would produce the right count beside a `coverageDetail` still written
as though the whole criterion were established, which is the worse of the two
errors.

Name clauses the way the reader can act on them — "nothing in the traversed set
establishes rejection above the tier quota", not "partially covered".

One clause, nothing open: `uncoveredClauses` and `unresolvedClauses` are both
`[]` and `Evidence found` is exactly right. This is a stricter standard, not a
prohibition.

**The two columns answer different questions and must not be collapsed.** Work
in flight raises the state without moving the assessment: a criterion whose only
evidence is an open PR is `No evidence found` at state `in review`, with the PR
named in the Gap column. `Partial evidence` is for a criterion genuinely
part-covered by landed evidence — typically two clauses where one merged.

### Criteria with an unresolved clause

A criterion that mixes checkable requirements with an undecided parameter is
**not** automatically `Unable to assess`. Split it:

1. Assess the checkable clauses against the evidence as you would a whole
   criterion.
2. Name the unresolved part, the specific clarification needed, and who can give
   it — "the retention window is given as TBD; product to set a value before
   this clause can be checked", not "criterion is ambiguous".
3. The row takes the assessment the checkable clauses earn: `Partial evidence`
   when they are covered and the unresolved clause is open, `No evidence found`
   when they are not covered either. It is never `Evidence found` while an
   unresolved clause remains — the criterion as stated cannot be met until
   someone decides what it asks for.

`Unable to assess` stays reserved for a criterion with **no** checkable clause,
for access failures or truncated retrieval, and for a missing upstream mapping.
Discarding the checkable half because one number is undecided throws away the
part of the assessment that was free to make.

When nothing upstream was observed, every row reads `Unable to assess` with the
same Gap throughout — and that Gap depends on why: a missing link and a refused
credential are different asks of different people. A criterion with an
unresolved clause still names that clause in the Gap column: it is a separate
ask again.

### Evidence rules, in force for every row

- **An issue title alone is a candidate mapping, not coverage.** Open the issue;
  its contents have to establish the required behaviour.
- **An open issue establishes planned work**, never implemented behaviour.
- **A merged PR establishes landed implementation**, never release readiness.
- **Test evidence must support the specific behaviour claimed** — not an
  adjacent behaviour, and not "CI is green". A green run establishes that the
  suite passed, not that the suite exercises the criterion. Cite a test only
  when you can name the job, file or test case.
- Changed test files under a PR that closes the child are reasonable evidence of
  intent to cover; name the file rather than claiming the behaviour is verified.
- A merged docs change establishes **documented** behaviour, not verified
  behaviour.
- If checks are inaccessible (private repo, 404, expired logs), say so against
  that criterion rather than falling back to merge state as proof.
- **"No evidence found" is never "not implemented."** Scope it to what you
  looked at: "no evidence in example-org/example-gateway#412 and its children."
  "No upstream issue covers this" is a claim about every repository on GitHub,
  made from a walk of one epic; `assemble` rejects it in a `gap`, a
  `coverageDetail`, a note or either rendered output. Write "no upstream work
  in the traversed set is linked to …", and if a nested epic went untraversed
  this run, that is part of what the claim is scoped to.
- **A missing mapping is never missing implementation.** You inspected nothing,
  so you know nothing about the state of the work.
- **Scope every absence claim** to the sources inspected. Partial traversal
  makes the claim weaker still — say so.
- **Incomplete access or traversal is reported prominently**, not as a footnote.
  Any inaccessible repo, 404, truncated page or skipped child gets named, and
  the Summary says coverage is incomplete.
- **Do not infer coverage from an epic's completion percentage.** 80% of
  children closed says nothing about which criterion the remaining 20% carries.
- **Do not invent** issue links, test results, owners, review commitments or
  target dates. If no owner is identified, write "owner not identified in the
  sources inspected."

### Criteria something inspected contradicts

`confirmed-unmet` is the one outcome declared by hand — `"outcome":
"confirmed-unmet"` plus `refutingEvidence` naming what shows the criterion is
not satisfied. It is a finding, not a schedule item, and it is never inferred
from absence.

What it is also not is a recommendation. "Reopen the work" and "revise the
criterion" are two possible answers to a question nobody has asked yet, and
picking one from an assessment row commits someone else's team to a decision on
the strength of a table cell. Two sources can both be accurate and still
disagree about what should happen: an issue proposing to reject a combination
and a criterion requiring the combination to work are a product question, not a
defect in either.

So state the question. "Confirm whether the criterion still describes intended
behaviour" is the item, and the evidence that raised it goes beside it. Put the
clarification first, the options after, and only where a source you read
actually named one.

### Downstream qualification, separately

For each requirement, state whether downstream integration or qualification is
still required. This is a different question from upstream coverage and is
answered independently: upstream `Evidence found` with a merged PR routinely
still needs a downstream build, payload or qualification run.

- `confirmed` — the sources inspected show the downstream step happened.
- `pending` — a downstream artifact was inspected and is outstanding.
- `unknown` — downstream state was not inspected. Never `pending`; `pending` is
  a claim about something someone actually looked at.

### Failure kinds

Sort every uncovered requirement, because they need different follow-ups and
the Summary has to distinguish them:

| Kind | Looks like | Follow-up |
| --- | --- | --- |
| Missing mapping | The Jira records no upstream link at all | Someone adds the link; nothing is known about the work until then |
| Missing tracking | Upstream was traversed, but no issue in it maps to this requirement | Owner identifies coverage or confirms a gap |
| Unresolved requirement | A clause names a parameter or decision nobody has set | Product or owner decision, not engineering time |
| Unfinished implementation | Mapped, but planned / in progress / in review | Engineering time |
| Downstream validation | Upstream merged or tested, downstream pending | Integration or qualification run |

The first two look identical in a table cell and are not the same finding.
`Missing mapping` means the search never happened; `Missing tracking` means it
happened and came back empty.

### The JSON for `assessments.json`

One object per requirement in `diff.json`'s `reassess` list. `id` and
`sourceKey` identify the row; `text` is matched on if present.

```json
[
  {
    "id": "AC1",
    "sourceKey": "RHOAIENG-1234",
    "assessment": "Evidence found",
    "coverageDetail": "PR #520 implements tier-to-pool selection; CI job e2e-routing passed on the merge commit and asserts pool assignment per tier",
    "evidenceState": "tested",
    "evidence": [
      {"ref": "example-org/example-gateway#413", "kind": "issue", "at": "2026-09-18T10:00:00Z"},
      {"ref": "example-org/example-gateway#520", "kind": "pr", "state": "merged", "at": "2026-09-18T09:14:00Z"}
    ],
    "gap": "Downstream qualification pending; see below",
    "downstream": {"state": "pending", "detail": "implementation merged to main on 2026-09-18; no downstream build inspected"},
    "unresolvedClauses": [],
    "uncoveredClauses": []
  }
]
```

Both clause lists default to `[]`. Omitting them asserts that every clause of
the criterion is supported and settled, so leave them out only when that is
what you mean.

`at` is load-bearing: the trend section classifies a changed assessment as
implementation progress, newly discovered evidence, or undetermined by comparing
these timestamps against the baseline's. An evidence item with no usable date
produces `undetermined`, which is the honest answer — do not supply a plausible
date to avoid it.

The assembler rejects `Evidence found` or `Partial evidence` with an empty
`evidence` list, rejects any assessment string outside the four above, and
rejects `Evidence found` carrying a non-empty `unresolvedClauses` or
`uncoveredClauses`.

### Downstream `pending` is re-checked every run

A stored `pending` is never reused. Downstream artifacts are outside the
traversal, so no content hash can ever contradict one, and carrying it forward
would republish "qualification outstanding" indefinitely after anyone last
looked. `unknown` *is* reusable — nobody looked then, nobody looked now, and
saying so again is still true.
