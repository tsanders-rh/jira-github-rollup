# Example: a generated rollup

**Everything on this page is fictional.** Illustrative output for a made-up
requirement `RHOAIENG-1234`, derived from the epic linked in
[`jira-link-section.md`](jira-link-section.md). All orgs, repos, issue numbers,
acceptance criteria, test jobs, and dates are invented. No real issue, PR, or
test result is referenced.

The skill would show this draft for approval before posting it as a comment.

## The fictional input

`RHOAIENG-1234 — Tiered model routing` carries the four acceptance criteria
shown in [`jira-link-section.md`](jira-link-section.md), and its child
requirement `RHOAIENG-1240 — Tier observability` carries one more. Upstream, the
epic `example-org/example-gateway#412` lists four children and references a fifth
issue in a repository this account cannot read.

---

```
h3. Upstream Development Rollup

*Status:* In progress
*Source epic:* example-org/example-gateway#412 — Request routing for tiered models
*Generated:* 2026-10-05

*Summary*
Routing is implemented and merged; two of five acceptance criteria are not
covered by any evidence found upstream. AC3 (metering of routing decisions) has
no linked upstream work in the sources inspected — a tracking gap rather than a
schedule slip, and it needs an owner to say where it lives. AC4 could not be assessed because
example-org/example-dlp is unreadable from this account, so this coverage
section is incomplete. RHOAIENG-1240 AC1 is tracked in
example-org/example-controller#88, which is owned by another team and has had no
activity since 2026-08-28.

*Progress*
2 of 4 child issues closed; 3 pull requests merged.
|| Child || Status || PRs ||
| example-org/example-gateway#413 — request routing | Closed | example-org/example-gateway#520 (merged 2026-09-18) |
| example-org/example-gateway#414 — tier config parsing | Closed | example-org/example-gateway#531 (merged 2026-09-30), example-org/example-gateway#536 (merged 2026-10-01) |
| example-org/example-controller#88 — CRD plumbing | Open | — |
| example-org/example-tests#15 — e2e coverage | Open | example-org/example-tests#22 (open, 11d) |

*Acceptance criteria coverage*
|| Criterion || Evidence || Evidence state || Coverage || Gap / next validation step ||
| AC1 (RHOAIENG-1234) "Requests for a tiered model are routed to the serving pool configured for that tier." | example-org/example-gateway#413, PR example-org/example-gateway#520 (merged 2026-09-18) | tested | Evidence found — PR #520 implements tier-to-pool selection; CI job e2e-routing passed on the merge commit and asserts pool assignment per tier | Downstream qualification pending; see below |
| AC2 (RHOAIENG-1234) "An unknown tier is rejected with HTTP 400, and tier configuration changes take effect without a gateway restart." | example-org/example-gateway#414, PRs #531, #536 (merged 2026-09-30, 2026-10-01) | merged | Partial evidence — PR #536 adds tests/test_tier_reject.py covering the 400 on unknown tier. Nothing in #531 or #536 touches config reload; the no-restart half is unverified | Ask owner whether hot reload is in scope for #414 or needs its own issue |
| AC3 (RHOAIENG-1234) "Routing decisions, including denials, are recorded in the metering stream within 60 seconds." | — | — | No evidence found — no issue in example-org/example-gateway#412 or its four children maps to metering | Owner to identify upstream coverage or confirm this is a gap |
| AC4 (RHOAIENG-1234) "Streaming responses are subject to the same tier enforcement as non-streaming responses." | example-org/example-dlp#31 (referenced from the epic body; not readable) | — | Unable to assess — #31 is a candidate mapping from its title only. example-org/example-dlp returned 404 for this account, so its contents could not establish the enforcement behavior | Grant read access or have the owner confirm #31 covers streaming tier enforcement |
| AC1 (RHOAIENG-1240) "Per-tier request counts and p99 latency are exposed on the controller /metrics endpoint." | example-org/example-controller#88 (open, no PR) | planned | No evidence found — #88 is open with no linked PR; the sources inspected show planned work, not implemented behavior | Engineering time on #88; owned by the controller team |

*Downstream qualification*
- AC1 (RHOAIENG-1234) — implementation merged to main on 2026-09-18. No
  downstream build or qualification run was inspected, so downstream integration
  is still required.
- AC2 (RHOAIENG-1234) — same; the covered half is not qualified downstream either.
Criteria not listed above have no identified downstream step in the sources
inspected; that is not confirmation that none is required.

*Coverage caveats*
- example-org/example-dlp is not readable from this account (404 on
  example-org/example-dlp#31), so AC4 could not be assessed in either direction.
- AC3 has no upstream mapping in the reachable set. No search beyond the epic and
  its children was performed, so this is an absence in those sources, not a
  finding that the work does not exist.
- Coverage was assessed against example-org/example-gateway#412, its four
  children, and example-org/example-dlp#31 only. No wider search was run.

*Risks and blockers*
- example-org/example-controller#88 has no linked PR and no activity since
  2026-08-28 (38 days). It is in a repository this team does not own, and it is
  the only tracking for RHOAIENG-1240 AC1.
- AC3 has no upstream issue in the reachable set, so nothing connects this
  requirement to work on metering. Whether such work exists elsewhere is not
  something this traversal can see.
- example-org/example-tests#22 has been open 11 days with no review.

----
_Generated by the jira-github-rollup skill from example-org/example-gateway#412.
Read-only against GitHub; no Jira issues were created._
```

---

## What to notice

**The lede is the coverage gap, not the progress.** Three PRs merged and two
children closed, but the summary opens with two uncovered criteria. A program
manager scanning the issue learns in the first sentence that "routing is merged"
and "the requirement is covered" are different claims.

**Two rows are `No evidence found` and they mean different things.** AC3 has no
upstream issue — missing tracking, resolved by an owner deciding where it lives.
RHOAIENG-1240 AC1 has an issue that nobody has started — unfinished
implementation, resolved by engineering time. Collapsing them into one bucket
would send the reader to the wrong person. The Summary names the kind for each,
and the `Evidence state` column separates them at a glance: `—` versus `planned`.

**No row says "not implemented."** AC3 says no issue *in the sources inspected*
maps to metering. That is a statement about the search, and the Coverage caveats
repeat its scope. The metering work may well exist somewhere nobody linked —
the rollup cannot tell, and does not pretend to.

**AC4 shows what a candidate mapping is worth.** `example-org/example-dlp#31`
has a plausible title and is referenced from the epic. That makes it a lead. The
repo is unreadable, so the issue's contents never established the enforcement
behavior, and the assessment is `Unable to assess` — not `Evidence found` on the
strength of a title, and not `No evidence found` either, which would misreport an
access failure as an absence.

**The access failure is in the Summary.** An unreadable repo changes what the
whole section is worth, so it appears before the table, not only in the caveats.

**AC1 (RHOAIENG-1234) is `tested` and still not done.** The named CI job makes it the strongest
row in the table, and it still carries a downstream qualification step. Merged
upstream is not shipped downstream, which is why that question gets its own
section rather than a column — the answer can be "still required" even when
upstream coverage is complete.

**AC2 shows what partial means.** The criterion has two clauses. One has a named
test file; the other has nothing. The row names the unverified half rather than
rounding the criterion up to covered or down to uncovered.

**Criteria are quoted, and sourced.** The last row is `AC1 (RHOAIENG-1240)`, not
`AC5 (RHOAIENG-1234)` — IDs are numbered per source issue, so the table contains
two different `AC1`s and the key is what tells them apart. Without it a reader
would hold the parent's owner accountable for the child's criterion. The wording
is the Jira's, not a tidied-up version: a paraphrased criterion is a criterion
the skill made up.

**Status is `In progress`, not `Blocked`.** Real work merged recently. `Blocked`
is reserved for cases where nothing can proceed, and it always requires a named
blocker in the Risks section. It is also not `Complete`, which would require all
five criteria at `Evidence found` with no downstream work outstanding.

**The cross-repo child is called out three times** — in the Progress table
(different repo), in Risks (different owning team), and in the coverage table
(it is the only tracking for RHOAIENG-1240 AC1). That dependency is the most useful
thing in the rollup, and it is exactly what a single-repo traversal would have
missed.

**No "Since last rollup" section**, because this is the first one. On a later run
the skill would find the marker line at the bottom, diff against this content, and
offer to update this comment in place rather than appending a second near-identical
update.

**No filler.** There is no "No other risks identified" line and no restatement of
the requirement's description. If a section has nothing evidenced to say, it is
omitted — but `Coverage caveats` is not optional when a source was unreadable.
