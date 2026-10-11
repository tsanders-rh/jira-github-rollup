# Example: the second run, four weeks later

**Everything on this page is fictional.** This is `RHOAIENG-1234` from
[`sample-rollup.md`](sample-rollup.md), rolled up again on 2026-11-02 against the
snapshot the 2026-10-05 run left behind. All orgs, repos, issue numbers, PRs,
dates, and test jobs are invented.

Read [`sample-rollup.md`](sample-rollup.md) first — this page only makes sense as
the second half of a pair.

## What happened in the fiction between the two runs

On the Jira:

- Someone inserted a new acceptance criterion after AC2: *"Tier assignment is
  visible in the request trace."* The criteria below it renumbered — the old AC3
  and AC4 are now AC4 and AC5. **Nothing about them changed except the number.**

Upstream:

- `example-org/example-controller#88` closed as completed; PR #95 merged
  2026-10-21.
- `example-org/example-tests#15` closed as **not planned** on 2026-10-14, and its
  open PR #22 was closed unmerged.
- Read access to `example-org/example-dlp` was granted. `#31` turns out to have
  been closed since August, with PR #77 merged **2026-08-04** — before the
  previous snapshot.

Nothing else moved.

---

````markdown
### Upstream Development Rollup

**Status:** In progress
**Source epic:** [example-org/example-gateway#412](https://github.com/example-org/example-gateway/issues/412) — Request routing for tiered models
**Generated:** 2026-11-02

#### Summary

Three of seven requirements now have full upstream evidence, up from one. Two of
those three are genuine movement: the controller CRD work merged on 2026-10-21,
closing the last gap on RHOAIENG-1240 AC1. The third, AC5 (streaming
enforcement), was implemented back in August — this run is simply the first that
could read example-org/example-dlp, so it is newly visible rather than newly
done. AC4 (metering) still has no upstream mapping in the sources inspected, and
the newly added AC3 (request trace) has none either. DoD1 remains blocked on a
product decision, not on engineering. The e2e coverage issue
example-org/example-tests#15 was closed as not planned and nothing replaced it,
which leaves no tracked owner for end-to-end verification.

#### Progress

3 of 4 child issues closed as completed; 1 closed as not planned; 5 pull requests
merged.

| Child | Status | PRs |
| --- | --- | --- |
| example-org/example-gateway#413 — request routing | Closed (completed) | example-org/example-gateway#520 (merged 2026-09-18) |
| example-org/example-gateway#414 — tier config parsing | Closed (completed) | example-org/example-gateway#531 (merged 2026-09-30), example-org/example-gateway#536 (merged 2026-10-01), example-org/example-gateway#541 (merged 2026-10-02) |
| example-org/example-controller#88 — CRD plumbing | Closed (completed) | example-org/example-controller#95 (merged 2026-10-21) |
| example-org/example-tests#15 — e2e coverage | Closed (not planned) | example-org/example-tests#22 (closed unmerged 2026-10-14) |

#### Requirements coverage

6 acceptance criteria, 1 definition-of-done item.

| Requirement | Evidence | Evidence state | Coverage | Gap / next validation step |
| --- | --- | --- | --- | --- |
| AC1 (RHOAIENG-1234) "Requests for a tiered model are routed to the serving pool configured for that tier." | example-org/example-gateway#413, PR example-org/example-gateway#520 (merged 2026-09-18) | tested | Evidence found — PR #520 implements tier-to-pool selection; CI job e2e-routing passed on the merge commit and asserts pool assignment per tier | Downstream qualification pending; see below |
| AC2 (RHOAIENG-1234) "An unknown tier is rejected with HTTP 400, and tier configuration changes take effect without a gateway restart." | example-org/example-gateway#414, PRs #531, #536 (merged 2026-09-30, 2026-10-01) | merged | Partial evidence — the 400 on an unknown tier is covered: PR #536 adds tests/test_tier_reject.py asserting it. The no-restart clause is not. `internal/config/loader.go` at 4a7e9c2 (the #536 merge commit) reads the file once from `main()` and registers no watcher, and `config_test.go` at the same commit asserts parsing only | **Implementation gap** — add a reload path under #414 or open an issue for it |
| AC3 (RHOAIENG-1234) "Tier assignment is visible in the request trace." | — | — | No evidence found — nothing in example-org/example-gateway#412, its four children, or example-org/example-dlp#31 maps to tracing | Added to the Jira since the previous snapshot; owner to identify upstream coverage |
| AC4 (RHOAIENG-1234) "Routing decisions, including denials, are recorded in the metering stream within 60 seconds." | — | — | No evidence found — no issue in example-org/example-gateway#412 or its four children maps to metering | Owner to identify upstream coverage or confirm this is a gap |
| AC5 (RHOAIENG-1234) "Streaming responses are subject to the same tier enforcement as non-streaming responses." | example-org/example-dlp#31, PR example-org/example-dlp#77 (merged 2026-08-04) | merged | Evidence found — #31 applies the tier enforcement path to the streaming handler, and PR #77 adds tests/test_stream_tier.py asserting it | Downstream qualification pending; see below |
| DoD1 (RHOAIENG-1234) "The admin guide documents tier configuration, and the gateway logs a deprecation warning for the legacy per-model pool field for at least one release before removal (release count TBD with product)." | example-org/example-gateway#414, PRs #536 (merged 2026-10-01), #541 (merged 2026-10-02) | merged | Partial evidence — PR #541 adds docs/admin-tiers.md covering tier configuration, and PR #536 emits the deprecation warning (tests/test_legacy_warning.py asserts it). The deprecation period cannot be checked at all: the release count is left TBD in the criterion itself | Product to set the release count; the two landed clauses need no further upstream work |
| AC1 (RHOAIENG-1240) "Per-tier request counts and p99 latency are exposed on the controller /metrics endpoint." | example-org/example-controller#88, PR example-org/example-controller#95 (merged 2026-10-21) | merged | Evidence found — PR #95 adds the /metrics handler with per-tier counters and a p99 latency histogram | Downstream qualification pending; no CI job named in #95 exercises the endpoint |

#### Downstream qualification

- AC1 (RHOAIENG-1234) — merged to main 2026-09-18. No downstream build or
  qualification run was inspected, so downstream integration is still required.
- AC5 (RHOAIENG-1234) — merged to main 2026-08-04; same.
- DoD1 (RHOAIENG-1234) — the docs and warning merged 2026-10-01 and 2026-10-02;
  same.
- AC1 (RHOAIENG-1240) — merged to main 2026-10-21; same.

Requirements not listed above have no identified downstream step in the sources
inspected; that is not confirmation that none is required.

#### Coverage caveats

- AC3 and AC4 have no upstream mapping in the reachable set. No search beyond the
  epic, its four children, and example-org/example-dlp#31 was performed, so these
  are absences in those sources, not findings that the work does not exist.
- DoD1 leaves the deprecation period as "TBD with product". That clause is
  unassessable until someone sets a number; the rest of the item was assessed
  normally.
- example-org/example-tests#15 was closed as not planned, so the end-to-end
  coverage it tracked is no longer tracked anywhere in the reachable set.

#### Risks and blockers

- example-org/example-tests#15 was closed as not planned on 2026-10-14 and PR #22
  was closed unmerged. Nothing in the reachable set replaces it, and no
  requirement names an owner for end-to-end verification.
- AC3 and AC4 have no upstream issue in the reachable set. Whether work exists
  elsewhere is not something this traversal can see.

#### Trend since previous snapshot

Baseline: published snapshot 2026-10-05. This snapshot: 2026-11-02.

| Indicator | Previous | Current | Change |
| --- | --- | --- | --- |
| Child issues completed | 2/4 (50%) | 3/4 (75%) | +1 issue, +25 pp |
| Requirements with evidence found | 1/6 (17%) | 3/7 (43%) | +2 requirements, +26 pp |
| Partial / no evidence / unable to assess | 2 / 2 / 1 | 2 / 2 / 0 | 0 / 0 / −1 |
| Downstream confirmed / pending / unknown | 0 / 0 / 6 | 0 / 0 / 7 | 0 / 0 / +1 |

Not counted toward completion: 1 child closed as not planned
(example-org/example-tests#15). No child was closed with an unrecorded reason.

Requirement mix: 6 acceptance criteria, 1 definition-of-done item (previously 5
and 1).

- **Implementation progress.** RHOAIENG-1240 AC1 moved from No evidence found to
  Evidence found on PR example-org/example-controller#95, merged 2026-10-21 —
  after the previous snapshot. example-org/example-controller#88 closed as
  completed in the same change.
- **Newly discovered evidence.** AC5 (previously numbered AC4) moved from Unable
  to assess to Evidence found because read access to example-org/example-dlp was
  granted. Its PR #77 merged 2026-08-04, before the previous snapshot: this is
  evidence newly visible, not work newly done.
- **Scope added.** One acceptance criterion, AC3, was added to RHOAIENG-1234. The
  denominator rose from 6 to 7; no requirement lost evidence. Over the six
  requirements present and unchanged in both snapshots, evidence found went from
  1/6 (17%) to 3/6 (50%), +33 pp.
- **Renumbering.** Inserting AC3 shifted the previous AC3 and AC4 to AC4 and AC5.
  They were matched on their text, not their IDs, and neither changed.
- **Scope closed as not planned.** example-org/example-tests#15 was closed as not
  planned, which is why child completion rose to 3/4 rather than 4/4. It remains
  in the denominator.
- **Access changed.** example-org/example-dlp is readable from this account as of
  this run; it returned 404 on 2026-10-05.
- No requirement was removed, no requirement's text changed, no mapping changed,
  and no issue was reopened.

_Unweighted counts of requirements and child issues. Not a measure of effort
completed, work remaining, or release readiness._

---

_Generated by the jira-github-rollup skill from example-org/example-gateway#412.
Read-only against GitHub; no Jira issues were created._
````

---

## Where the snapshot went

Before showing this draft, the run wrote:

```
~/.jira-github-rollup/snapshots/RHOAIENG-1234/20261102T090412Z-draft.json
```

The directory already held the baseline this run compared against:

```
~/.jira-github-rollup/snapshots/RHOAIENG-1234/
  20260918T101500Z-published.json
  20261005T142203Z-published.json      ← the baseline for this run
  20261102T090412Z-draft.json          ← written by this run
```

If the user approves this draft and it is posted, that third file is promoted in
place: `publication` becomes `published`, `publishedAt` and `jiraCommentId` are
filled, and the suffix is renamed to `-published`. If the user never approves it,
it stays a draft and the 2026-10-05 snapshot remains the published baseline for
the next run.

Nothing is ever overwritten. That is the point of keeping the baseline on disk
rather than parsing it back out of the Jira comment: the skill offers to **edit
the previous comment in place** so the issue does not accumulate near-identical
updates, and editing a comment would otherwise destroy the only record of what
the last run found.

Abridged to two requirements and two children — the real file carries all seven
and all four. Full schema in
[`references/snapshots.md`](../.claude/skills/jira-github-rollup/references/snapshots.md).

```json
{
  "schemaVersion": 2,
  "rulesVersion": "2026-10-10",
  "jiraKey": "RHOAIENG-1234",
  "generatedAt": "2026-11-02T09:04:12Z",
  "publication": "draft",
  "publishedAt": null,
  "jiraCommentId": null,
  "baseline": { "generatedAt": "2026-10-05T14:22:03Z", "publication": "published" },
  "jiraStatus": "In Progress",
  "rollupStatus": "In progress",
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
        "ref": "example-org/example-controller#88",
        "title": "CRD plumbing",
        "state": "CLOSED",
        "stateReason": "COMPLETED",
        "closedAt": "2026-10-21T16:30:02Z",
        "epics": ["example-org/example-gateway#412"],
        "contentHash": "a41c7e…",
        "accessible": true,
        "prs": [
          { "ref": "example-org/example-controller#95", "state": "merged",
            "mergedAt": "2026-10-21T16:29:44Z", "baseRef": "main" }
        ]
      },
      {
        "ref": "example-org/example-tests#15",
        "title": "e2e coverage",
        "state": "CLOSED",
        "stateReason": "NOT_PLANNED",
        "closedAt": "2026-10-14T11:07:55Z",
        "epics": ["example-org/example-gateway#412"],
        "contentHash": "6b0f92…",
        "accessible": true,
        "prs": [
          { "ref": "example-org/example-tests#22", "state": "closed",
            "mergedAt": null, "baseRef": "main" }
        ]
      }
    ],
    "otherInspected": ["example-org/example-dlp#31"],
    "traversalComplete": true,
    "traversalNotes": null,
    "observed": true,
    "unobservedReason": null
  },
  "access": [
    { "ref": "example-org/example-dlp", "status": "readable",
      "detail": "404 on 2026-10-05; readable this run",
      "observedAt": "2026-11-02T09:03:38Z" }
  ],
  "requirements": [
    {
      "sourceKey": "RHOAIENG-1234",
      "type": "AC",
      "id": "AC5",
      "text": "Streaming responses are subject to the same tier enforcement as non-streaming responses.",
      "heading": "Acceptance Criteria",
      "assessment": "Evidence found",
      "evidenceState": "merged",
      "evidence": [
        { "ref": "example-org/example-dlp#77", "kind": "pr", "state": "merged",
          "at": "2026-08-04T13:18:20Z", "epic": "example-org/example-gateway#412" }
      ],
      "downstream": { "state": "unknown", "detail": "no downstream source inspected" },
      "unresolvedClauses": [],
      "failureKind": null,
      "reused": false,
      "assessedAt": "2026-11-02T09:04:12Z",
      "assessedFromSnapshot": null
    },
    {
      "sourceKey": "RHOAIENG-1240",
      "type": "AC",
      "id": "AC1",
      "text": "Per-tier request counts and p99 latency are exposed on the controller /metrics endpoint.",
      "heading": "Acceptance Criteria",
      "assessment": "Evidence found",
      "evidenceState": "merged",
      "evidence": [
        { "ref": "example-org/example-controller#95", "kind": "pr", "state": "merged",
          "at": "2026-10-21T16:29:44Z", "epic": "example-org/example-gateway#412" }
      ],
      "downstream": { "state": "unknown", "detail": "no downstream source inspected" },
      "unresolvedClauses": [],
      "failureKind": null,
      "reused": false,
      "assessedAt": "2026-11-02T09:04:12Z",
      "assessedFromSnapshot": null
    }
  ],
  "inventory": {
    "collectedAt": "2026-11-02T09:03:51Z",
    "inventoryHash": "d7e5b1…",
    "stage": "evidence",
    "epics": [
      { "ref": "example-org/example-gateway#412",
        "childRefs": ["example-org/example-controller#88", "example-org/example-tests#15"],
        "accessible": true }
    ]
  }
}
```

Note `id: "AC5"` sitting next to text that was `AC4` in the previous snapshot.
The ID is stored for display and is never used to match — the text is.

Content hashes are abbreviated here; the real file carries them in full. They
are what makes the *next* run cheap: a child whose hash is unchanged cannot have
moved, so the requirements resting on it keep their stored assessment, and
`reused: true` with an earlier `assessedAt` records that it was carried forward
rather than judged again. Both requirements above were assessed this run —
#95 merged and the DLP repository became readable — so both read `false`.

---

## What to notice

**Two requirements gained evidence and only one of them is progress.** That is
the distinction the whole section is built around. RHOAIENG-1240 AC1 is a PR
merged on 2026-10-21, after the baseline: work done this period. AC5 is a PR
merged on 2026-08-04, before the baseline: the work was already there and the
account could not see the repository. Reporting both as a month's progress would
credit the team for something that happened in August and would hide the real
cause, which was an access grant. The test is mechanical — compare each new piece
of evidence's date against the baseline's timestamp — and it is why snapshots
store timestamps rather than just states.

**The criteria renumbered and nothing reports a change.** Inserting AC3 shifted
two criteria down by one. Matching on `(source key, type, verbatim text)` sees
six unchanged requirements and one addition. Matching on IDs would have seen
three changed requirements and one addition, and a reader would have gone looking
for edits that never happened.

**The denominator moved, and the sentence that says so is next to the number.**
Coverage went 17% → 43%, which is flattering, and the headline ratio changed
denominator underneath it. The bullet gives the like-for-like figure over the six
requirements in both snapshots — 1/6 to 3/6 — so the reader can see how much of
the jump is movement and how much is arithmetic. The same discipline protects the
opposite case: had the added criterion arrived with no new evidence, coverage
would have fallen from 17% to 14% with nothing having gone backwards, and that
must never be printed as a regression.

**`example-org/example-tests#15` is closed and does not count.** Closed as not
planned, so it is excluded from the numerator, kept in the denominator, and named
on its own line. That is why completion reads 3/4 and not 4/4. Folding it into
the closed count would have reported 100% completion on an epic whose end-to-end
coverage nobody owns — which is also why it is the first entry under Risks.

**Partial evidence did not move and earns nothing.** AC2 and DoD1 are both
part-covered and have been since the first run. They contribute zero to the
evidence-found ratio and appear in their own column. Giving them half credit
would have shown 4/7 instead of 3/7 and invented the claim that a two-clause
criterion with one clause landed is halfway to being met.

**AC2's finding is carried forward, not re-derived.** Its child, its PRs, and
their merge commits all hash the same as in the previous snapshot, so the
assessment is reused and no source file was opened for it this run — which is
why the rendered draft has no follow-up-read bullet. The reads that produced
the finding are named in the 2026-10-05 draft, at the commit they were read at,
and that commit has not moved. Re-reading `loader.go` at today's main would
have been the wrong check anyway: it would say what the code does now, not what
the assessed revision did.

**Every requirement is `unknown` downstream, including the `tested` one.** The
skill inspects no downstream source, so there is nothing to confirm and nothing
identified as pending. Reporting those as `pending` would invent a step nobody
has named, and reporting them as confirmed because the PR merged is the exact
conflation the Downstream qualification section exists to prevent.

**The access change is reported as an access change.** It appears in the trend
bullets and it is gone from Coverage caveats, because the repository is readable
now. Had it gone the other way — readable on 2026-10-05, 404 today — AC5 would
move to `Unable to assess`, the evidence-found count would fall, and the bullet
would have to say that the recorded evidence has not been withdrawn and nothing
observed this run contradicts it.

**The closing label is not decoration.** Three ratios and a set of deltas look
like a burn-down whether or not one is intended, and the first thing a reader
does with two data points is extrapolate. The section reports movement between
two observations and refuses to turn that into a rate or a date.
