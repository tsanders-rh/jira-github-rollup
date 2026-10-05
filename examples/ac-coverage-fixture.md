# Fixture: acceptance-criteria coverage cases

**Everything on this page is fictional.** The Jira keys, repos, issue numbers,
PRs, and test jobs are invented to exercise the rules in `SKILL.md` steps 2, 6,
and 8. No real issue or test result is referenced.

This repo has no test runner — the deliverable is prose, so the check is a desk
check. Walk each case against the current `SKILL.md` and
`references/rollup-format.md` and confirm the skill's rules force the expected
output. A change that lets any case produce a different answer is a regression,
and the case is the argument for why.

## Fixture input

Jira `RHOAIENG-9001 — Policy rails for inference requests`, with child
requirement `RHOAIENG-9002 — Rail observability`. The Jira description links one
epic: `example-org/example-rails#200`.

Upstream state:

| Artifact | State |
| --- | --- |
| `example-org/example-rails#200` | Epic. Task list naming #201, #202, and `example-org/example-dlp#31`. Body also says "depends on example-org/example-meter#9" |
| `example-org/example-rails#201` | Closed. PR #310 merged to `main` 2026-09-22. Touches `rails/deny.py`, `tests/test_deny_403.py`, `tests/test_deny_audit.py`. CI job `unit` passed on the merge commit |
| `example-org/example-rails#202` | Open. No linked PR. Last activity 2026-07-30 |
| `example-org/example-dlp#31` | Title "streaming DLP hooks". Repo returns 404 for this account |
| `example-org/example-meter#9` | Open. PR #44 open, 6 days, one review requested |

## Cases

| # | Criterion (source) | Upstream facts | Expected state | Expected coverage | What the output must not do |
| --- | --- | --- | --- | --- | --- |
| 1 | AC1 (RHOAIENG-9001) "A denied request returns HTTP 403." | #201 closed, PR #310 merged, `tests/test_deny_403.py` added, `unit` passed on the merge commit | tested | **Evidence found** — names PR #310 and `tests/test_deny_403.py` as establishing the 403 | Claim release readiness, or cite "CI green" without naming the job or file |
| 2 | AC2 (RHOAIENG-9001) "Deny outcomes are written to the audit log and reflected in metering within one billing interval." | Audit clause: PR #310 merged with `tests/test_deny_audit.py`. Metering clause: `example-meter#9` open, PR #44 open 6d with a review requested | merged | **Partial evidence** — audit-log clause landed and tested in #310; the metering clause is unmerged, and the one-interval bound is unverified | Round up to `Evidence found` because a PR exists, or let PR #44 read as landed behavior |
| 3 | AC3 (RHOAIENG-9001) "Streaming responses are subject to the same enforcement as non-streaming responses." | `example-dlp#31` named in the epic task list; repo 404s | `—` | **Unable to assess** — title is a candidate mapping only; contents unreadable | Infer coverage from the title, or report the access failure as `No evidence found` |
| 4 | AC4 (RHOAIENG-9001) "Rail evaluation should be fast enough for interactive use." | n/a — criterion is not checkable as written | `—` | **Unable to assess** — ambiguous criterion; ask the owner to restate with a threshold | Pick a latency number, or silently drop the criterion from the table |
| 5 | AC5 (RHOAIENG-9001) "An operator can disable a single rail without restarting the service." | Nothing in #200, its children, or `example-meter#9` mentions rail toggles | `—` | **No evidence found** — nothing in `example-rails#200`, its children, or `example-meter#9` maps to this | Search the org for "rail toggle" to find a candidate, or say "not implemented" |
| 6 | AC1 (RHOAIENG-9002) "Per-rail decision counts are exposed on /metrics." | `#202` open, no PR, stale since 2026-07-30 | planned | **No evidence found** — #202 is open with no PR; planned work, not implemented behavior | Write `planned` in the Coverage column, drop the `(RHOAIENG-9002)` key, or omit that #202 exists |

## Expected cross-cutting output

- **Row order** follows the Jira: `RHOAIENG-9001` AC1–AC5, then
  `RHOAIENG-9002` AC1. Two rows are labelled `AC1`; the source key is what
  separates them, and dropping it misattributes case 6 to the parent.
- **Downstream qualification** names cases 1 and 2 — PR #310 merged to `main`,
  no downstream build or qualification inspected, so downstream work is still
  required. A `tested` upstream row does not close the downstream question, and
  neither does the landed half of a partially covered criterion.
- **Open work never becomes coverage.** PR #44 in case 2 raises the metering
  clause's visibility but not the assessment; the same rule makes a criterion
  whose *only* evidence is an open PR `No evidence found` at state `in review`.
- **Coverage caveats** names `example-org/example-dlp` as unreadable (case 3),
  AC4 as ambiguous (case 4), and AC5 as unmapped (case 5), and scopes every
  absence to `example-rails#200`, its children, and `example-meter#9` — the
  sources actually inspected, named explicitly.
- **Summary** mentions the unreadable repo, and separates case 6 (unfinished
  implementation, engineering time) from case 5 (missing tracking, owner
  decision) even though both are `No evidence found`.
- **Status** is `In progress`. It cannot be `Complete` with cases 2–6
  outstanding.
- **Retrieval** stays inside `#200`, its three listed children, and
  `example-meter#9` — reachable as a directly referenced dependency. `example-meter#9`
  being in scope comes from the epic body naming it, not from a search.

## Negative cases

| Situation | Required behavior |
| --- | --- |
| `RHOAIENG-9001` has no acceptance-criteria section, field, or Gherkin block, and no child carries one | Coverage section is one line naming the sources checked. No criteria are inferred from the summary, the description prose, or upstream issue titles |
| The epic task list is truncated or a `--paginate` call fails midway | Coverage caveats names what was not retrieved; every absence claim in the table is weakened accordingly and says so |
| A criterion's only candidate is an upstream issue whose title matches but whose body describes different behavior | `No evidence found`, with the candidate named and why it was rejected. A title match is never coverage |
| The user asks to file the uncovered criteria as upstream issues or Jira sub-tasks | Decline both: GitHub is read-only, and the skill never creates Jira issues. Offer the flagged list for a human to act on |

## Boundary check

Running this fixture end to end must involve no Jira write of any kind — no
comment until the draft is approved, no status transition, no issue creation,
and nothing written to `RHOAIENG-9002`. Reading a child requirement for its
criteria does not make it a write target.
