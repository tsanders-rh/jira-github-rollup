# Fixture: trend across repeated runs

**Everything on this page is fictional.** The Jira keys, repos, issue numbers,
PRs, and dates are invented to exercise the rules in `SKILL.md` step 9 and
`references/snapshots.md`. No real issue is referenced.

As with [`ac-coverage-fixture.md`](ac-coverage-fixture.md), there is no test
runner — the check is a desk check. Walk each run against the current skill and
confirm its rules force the expected output. A change that lets any run produce a
different answer is a regression, and the run is the argument for why.

Every run below is a **draft-only** run unless it says otherwise. No Jira write
occurs anywhere in this fixture.

## Baseline fixture

`RHOAIENG-7001 — Quota enforcement`, with child requirement
`RHOAIENG-7002 — Quota telemetry`.

`RHOAIENG-7001` description, `Acceptance Criteria`:

1. "A request over quota is rejected with HTTP 429."
2. "Quota counters reset at the start of each billing interval."
3. "An operator can raise a tenant's quota without a restart."

`RHOAIENG-7001` description, `Definition of Done`: "The quota model is documented
in the operator guide."

`RHOAIENG-7002` description, `Acceptance Criteria`: "Quota rejections are
exported as a counter metric."

Five requirements: four acceptance criteria (three on the parent, one on the
child) and one definition-of-done item.

`Upstream Development` section links `example-org/example-quota#300`, whose
children are `#301`, `#302`, and `example-org/example-meter#40`.

---

## Run 1 — initial run (2026-07-01)

Upstream: `#301` closed as completed, PR #350 merged 2026-06-28 with
`tests/test_429.py`. `#302` open, no PR. `example-org/example-meter#40` open, no
PR.

| Expected | Must not |
| --- | --- |
| Trend section present and reads exactly `Baseline established — no prior snapshot available` | Omit the section, or print a table of zeroes |
| No table, no bullets, no percentages, no `0%` anywhere in the section | Emit `0/5 (0%), previously 0/5 (0%)` |
| The rest of the rollup is normal: AC1 Evidence found, the other four No evidence found | Suppress coverage because there is nothing to compare |
| A snapshot is written to `~/.jira-github-rollup/snapshots/RHOAIENG-7001/20260701T<hhmmss>Z-draft.json` and the path is stated to the user | Write nothing, write under the current working directory, or stay silent about where it went |
| Snapshot `baseline` is `null`; `publication` is `"draft"` | Record a baseline that does not exist, or mark an unapproved run `published` |
| No Jira write of any kind | Treat "roll this up" as approval to post |

The point of this run: **a first run has no history and says so.** The previous
Jira comment, the issue's created date, and the epic's own age are all available
and none of them is a baseline. Inventing one from any of them is fabrication.

## Run 2 — unchanged rerun (2026-07-08)

Nothing changed on the Jira. Nothing changed upstream. Run 1 was never approved,
so its snapshot is still a draft.

| Expected | Must not |
| --- | --- |
| `Baseline: draft snapshot 2026-07-01 (never published). This snapshot: 2026-07-08.` | Say "published", or omit which kind of snapshot it was |
| All four indicator rows present; every Change cell reads `no change` | Drop unchanged rows, or write `0` where nothing moved |
| `Child issues completed 1/3 (33%) \| 1/3 (33%) \| no change` | Round 33.3% inconsistently between the two columns |
| `Requirements with evidence found 1/5 (20%) \| 1/5 (20%) \| no change` | — |
| A line stating no requirement was added, removed, retexted, remapped, reopened, and no access changed | Emit an empty bullet list and let the reader guess whether it was checked |
| A second draft snapshot is written; the 2026-07-01 one is untouched | Overwrite the 2026-07-01 snapshot, or delete it as superseded |

Why the draft baseline is used here: there is no published snapshot, and a
labelled comparison against a draft is more useful than none. Why the label is
mandatory: a delta against something nobody ever saw is a different claim from a
delta against the last thing in the Jira.

`no change` rather than `0` because the two are different findings. `0` is a
measurement; `no change` says the row was measured and did not move.

## Run 3 — genuine progress (2026-08-03)

Run 2 was approved and posted, so its snapshot was promoted to
`20260708T<hhmmss>Z-published.json`.

Upstream: `#302` closed as completed, PR #361 merged 2026-07-29 adding counter
reset plus `tests/test_reset.py`. `example-org/example-meter#40` still open.

| Expected | Must not |
| --- | --- |
| `Baseline: published snapshot 2026-07-08.` | Use the 2026-07-01 draft, which is older but also a baseline candidate |
| `Child issues completed 1/3 (33%) \| 2/3 (67%) \| +1 issue, +33 pp` | Report `+34 pp` by subtracting rounded percentages |
| `Requirements with evidence found 1/5 (20%) \| 2/5 (40%) \| +1 requirement, +20 pp` | — |
| One bullet classified as **implementation progress**, naming PR #361 and its merge date 2026-07-29, which is after the 2026-07-08 baseline | Report it without the date, or without saying which category it falls in |
| Downstream row `0 / 0 / 5` in both columns, `no change` | Mark AC2 `pending` because its PR merged |
| Denominator unchanged, so no like-for-like restatement is needed | Add a like-for-like line anyway and imply scope moved |

Percentage-point arithmetic is specified because it is the easiest thing to get
quietly wrong: 1/3 is 33.33% and 2/3 is 66.67%, a difference of 33.33 pp, which
rounds to 33. Subtracting the displayed 33 from the displayed 67 gives 34.

## Run 4 — scope growth (2026-08-17)

Run 3 was approved and published. Two acceptance criteria were added to
`RHOAIENG-7001`, appended after the existing three:

4. "Quota state survives a gateway restart."
5. "A tenant can query its own remaining quota."

Nothing changed upstream.

| Expected | Must not |
| --- | --- |
| `Requirements with evidence found 2/5 (40%) \| 2/7 (29%) \| +0 requirements, −11 pp` | Present −11 pp as a decline in coverage, or as any kind of regression |
| A bullet: scope added, two acceptance criteria, denominator 5 → 7, **no requirement lost evidence** | Report only the percentage and leave the cause to the reader |
| A like-for-like line: over the five requirements in both snapshots, 2/5 (40%) → 2/5 (40%), no change | Omit it because the raw numbers "speak for themselves" |
| `Requirement mix: 6 acceptance criteria, 1 definition-of-done item (previously 4 and 1)` | Write "7 acceptance criteria", merging the DoD item into the AC count |
| Child issues row unchanged at 2/3 (67%), `no change` | Let the requirement-side change bleed into the issue row |
| The two new criteria appear in the coverage table as `No evidence found`, scoped to the sources inspected | Mark them `Unable to assess` because they are new |

This is the run the rules exist for. A percentage that falls because somebody
wrote down more of what they wanted is not a project going backwards, and the
sentence saying so has to sit beside the number — a reader acts on the first
clause they read, and "coverage fell to 29%" is the first clause.

## Run 5 — reordered criteria (2026-08-24)

A criterion was **inserted** as the new first acceptance criterion on
`RHOAIENG-7001`: "Quota configuration is validated at load time." The parent's
five acceptance criteria, previously `AC1`–`AC5 (RHOAIENG-7001)`, are now
`AC2`–`AC6`. `AC1 (RHOAIENG-7002)` is unaffected — numbering is per type per
source issue, and the child is a different source. `DoD1` is unaffected for the
same reason. No existing text changed. Nothing changed upstream.

| Expected | Must not |
| --- | --- |
| Exactly one addition reported | Report six changed requirements, or five removals plus six additions |
| A renumbering note: the parent's previous AC1–AC5 are now AC2–AC6, matched on text and unchanged | Silently renumber, let the reader compare IDs against the previous comment, or claim the child's AC1 moved |
| The 429 criterion keeps its `Evidence found` assessment under its new ID `AC2` | Reassess it from scratch, or lose its link to PR #350 |
| `Requirements with evidence found 2/7 (29%) \| 2/8 (25%) \| +0, −4 pp`, with the scope bullet | Present −4 pp as a regression |
| The renumbering is reported as a note, **not** counted among the changes | List "6 requirements changed" in the bullets |

The whole reason requirements are matched on `(source key, type, verbatim text)`
rather than on ID. One insertion at the top of a list changes every ID beneath
it; an ID-based diff turns that into a wall of false changes, and a reader who
sees six changed requirements stops trusting the section.

## Run 6 — lost access (2026-09-07)

`example-org/example-quota` now returns 404 for this account. The
`Upstream Development` link is still on the Jira and still names
`example-org/example-quota#300`.

| Expected | Must not |
| --- | --- |
| Every requirement whose evidence came from that repo becomes `Unable to assess`, with the access failure named | Report them as `No evidence found`, which claims a search that failed to happen |
| `Requirements with evidence found 2/8 (25%) \| 0/8 (0%) \| −2, −25 pp` | Shrink the denominator by dropping unassessable rows, which would make losing access look like a flat result |
| `Unable to assess` count rises to 8; the sentence *no requirement could be assessed; 0% reflects absent assessment, not absent implementation* is present | Print 0% unqualified |
| Child issues completed reads `unknown`, with the 404 as the reason | Report `0/0`, `N/A`, `0%`, or carry forward the previous run's 2/3 as if re-observed |
| A bullet classified as **access changed**, naming the repo, the 404, and the date it was last readable | File it under regression or under implementation, both of which blame the wrong thing |
| An explicit statement that the evidence recorded on 2026-08-24 has not been withdrawn and that nothing observed this run bears on the state of the work | Let a reader conclude the work was reverted |
| The mapping is reported as **unchanged** — the link is still there | Report a mapping change; the Jira did not change, the account's access did |

Both this run and run 7 report child completion as `unknown`, and the *reason*
is what differs: here the mapping is present and the repository would not open;
in run 7 there is no mapping to open. Neither is `N/A`, which is reserved for a
zero that was actually observed — an epic that was read and has no children. A
404 is not a count of zero.

## Run 7 — mapping removed (2026-09-21)

Somebody deleted the `Upstream Development` section from `RHOAIENG-7001` during
an edit. No GitHub URL remains anywhere on the issue or its comments. Access to
`example-org/example-quota` has been restored, but nothing points at it.

| Expected | Must not |
| --- | --- |
| The partial-draft shape from `references/rollup-format.md` | Stop with an error, or fall back to run 6's epic from the previous snapshot |
| Child issues completed reads `unknown`, with `unknown — no upstream mapping recorded this run` in the Change column | Report `0/0`, `N/A`, or `0%`; or reuse the snapshot's remembered children as if re-observed |
| `Requirements with evidence found 0/8 (0%) \| 0/8 (0%) \| no change`, all eight `Unable to assess` | — |
| A bullet classified as **mapping changed**, saying the section present on 2026-09-07 is gone | Report it as an access change, or as requirements being removed |
| An explicit statement that the previously recorded evidence has not been withdrawn, and that upstream work may be complete, in flight, or unstarted | Assert "not started", "no progress", "behind", or "at risk" |
| The previous snapshot's epic link is reported as *what used to be mapped*, and is **not** used to traverse | Traverse it anyway because the skill "already knows" the epic |
| Status `Unknown — upstream mapping missing` | Soften it to `Not started` or `Blocked` |

The last two rows are the subtle ones. A snapshot store makes it technically easy
to carry a stale mapping forward, and doing so would quietly resurrect the
guessing prohibition from the other direction: the human-created link is the only
acceptable source, and a link that was deleted is not a current link. Reporting
what used to be mapped is useful; traversing it is not permitted.

## Cross-cutting expectations

Hold for every run above.

- **`Partial evidence` never earns fractional credit** in any ratio, in any run,
  under any denominator. It is counted once in its own position.
- **Unassessable requirements stay in the denominator.** Runs 6 and 7 are the
  test: if the denominator shrinks when assessment fails, losing a repository
  reads as an improvement.
- **`NOT_PLANNED` children stay in the denominator** and are named on their own
  line. A child closed with an empty `stateReason` gets its own count too and
  does not silently fail the COMPLETED test.
- **Every percentage carries its fraction.** No bare percentages anywhere.
- **Every run states its baseline** in the first line of the section, including
  whether it was published.
- **Requirement types stay separated** in every count. Only aggregates may be
  called "requirements".
- **No run derives a rate, a velocity, a burn-down, or a projected date**, and
  every run with a comparison carries the unweighted-indicator label verbatim.
- **Every run writes exactly one snapshot** and deletes none. After run 7 the
  directory holds seven files: runs 2 and 3 published, the rest drafts.

## Boundary check

No run in this fixture writes to Jira. Runs 2 and 3 are described as approved and
posted so that later runs have a published baseline to select; that approval is
part of the fiction, not something the fixture authorizes.

A draft-only run writes one local file under
`~/.jira-github-rollup/snapshots/RHOAIENG-7001/` and nothing else. It does not
create the snapshot in the Jira, does not attach it, does not mention it in a
comment, and does not treat having written it as a reason the rollup is now
posted. Saving a snapshot is bookkeeping; posting is a decision, and only the
user makes it.

Nothing is written to `RHOAIENG-7002` in any run, including the snapshot — the
store is keyed on the issue the user named, and a child read for its criteria
does not get a directory.
