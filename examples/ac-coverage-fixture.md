# Fixture: requirement coverage cases

**Everything on this page is fictional.** The Jira keys, repos, issue numbers,
PRs, and test jobs are invented to exercise the rules in `SKILL.md` steps 2, 3,
6, and 8. No real issue or test result is referenced.

This repo has no test runner — the deliverable is prose, so the check is a desk
check. Walk each case against the current `SKILL.md` and
`references/rollup-format.md` and confirm the skill's rules force the expected
output. A change that lets any case produce a different answer is a regression,
and the case is the argument for why.

## Fixture input

Jira `RHOAIENG-9001 — Policy rails for inference requests`, with child
requirement `RHOAIENG-9002 — Rail observability`. The description carries an
`Acceptance Criteria` section (cases 1–5), a `Definition of Done` section
(case 7), and an `Upstream Development` section listing two epics:
`example-org/example-rails#200` and `example-org/example-audit#12`.

Upstream state:

| Artifact | State |
| --- | --- |
| `example-org/example-rails#200` | Epic 1. Task list naming #201, #202, and `example-org/example-dlp#31`. Body also says "depends on example-org/example-meter#9" |
| `example-org/example-audit#12` | Epic 2. One child, `example-org/example-audit#18` |
| `example-org/example-rails#201` | Closed. PR #310 merged to `main` 2026-09-22. Touches `rails/deny.py`, `tests/test_deny_403.py`. CI job `unit` passed on the merge commit |
| `example-org/example-rails#202` | Open. No linked PR. Last activity 2026-07-30 |
| `example-org/example-audit#18` | Closed. PR #25 merged 2026-09-28, adds audit-log writes and `tests/test_deny_audit.py` |
| `example-org/example-dlp#31` | Title "streaming DLP hooks". Repo returns 404 for this account |
| `example-org/example-meter#9` | Open. PR #44 open, 6 days, one review requested |

## Cases

| # | Requirement (source) | Upstream facts | Expected state | Expected coverage | What the output must not do |
| --- | --- | --- | --- | --- | --- |
| 1 | AC1 (RHOAIENG-9001) "A denied request returns HTTP 403." | #201 closed, PR #310 merged, `tests/test_deny_403.py` added, `unit` passed on the merge commit | tested | **Evidence found** — names PR #310 and `tests/test_deny_403.py` as establishing the 403 | Claim release readiness, or cite "CI green" without naming the job or file |
| 2 | AC2 (RHOAIENG-9001) "Deny outcomes are written to the audit log and reflected in metering within one billing interval." | Audit clause: `example-audit#18` closed, PR #25 merged with `tests/test_deny_audit.py`. Metering clause: `example-meter#9` open, PR #44 open 6d with a review requested | merged | **Partial evidence** — audit-log clause landed and tested in `example-audit#18`/PR #25; the metering clause is unmerged, and the one-interval bound is unverified | Round up to `Evidence found` because a PR exists, let PR #44 read as landed behavior, or cite PR #25 without saying it came from the `example-audit#12` epic |
| 3 | AC3 (RHOAIENG-9001) "Streaming responses are subject to the same enforcement as non-streaming responses." | `example-dlp#31` named in the epic task list; repo 404s | `—` | **Unable to assess** — title is a candidate mapping only; contents unreadable | Infer coverage from the title, or report the access failure as `No evidence found` |
| 4 | AC4 (RHOAIENG-9001) "Rail evaluation should be fast enough for interactive use." | n/a — no clause of it is checkable | `—` | **Unable to assess** — nothing checkable in the criterion; ask the owner to restate with a threshold | Pick a latency number, or silently drop the criterion from the table |
| 5 | AC5 (RHOAIENG-9001) "An operator can disable a single rail without restarting the service." | Nothing in either epic, their children, or `example-meter#9` mentions rail toggles | `—` | **No evidence found** — nothing in `example-rails#200`, `example-audit#12`, their children, or `example-meter#9` maps to this | Search the org for "rail toggle", say "not implemented", or scope the absence to only one of the two epics |
| 6 | AC1 (RHOAIENG-9002) "Per-rail decision counts are exposed on /metrics." | `#202` open, no PR, stale since 2026-07-30 | planned | **No evidence found** — #202 is open with no PR; planned work, not implemented behavior | Write `planned` in the Coverage column, drop the `(RHOAIENG-9002)` key, or omit that #202 exists |
| 7 | DoD1 (RHOAIENG-9001) "Deny decisions are documented in the operator guide and retained in the audit log for the agreed retention window (TBD with compliance)." | Docs clause: PR #25 adds `docs/deny-audit.md`. Retention clause: no window has been set | merged | **Partial evidence** — the operator-guide clause landed in PR #25; the retention window is TBD in the criterion itself, so that clause cannot be checked against anything | Mark the whole item `Unable to assess` because of the TBD, invent a retention window, number it `AC6`, or route it to engineering rather than to compliance |

## Expected cross-cutting output

- **Row order** follows the Jira: `RHOAIENG-9001` AC1–AC5, then its `DoD1`, then
  `RHOAIENG-9002` AC1. Two rows are labelled `AC1`; the source key is what
  separates them, and dropping it misattributes case 6 to the parent. Case 7 is
  `DoD1`, not `AC6` — numbering restarts per type.
- **Counts are typed.** Seven rows is "six acceptance criteria and one
  definition-of-done item", never "seven acceptance criteria".
- **Both epics appear on the Source epic line**, and both were traversed without
  anyone being asked which to use — they were listed together in the
  `Upstream Development` section, which is a mapping, not an ambiguity.
- **Evidence stays attributable.** Case 1's evidence comes from
  `example-rails#200`; case 2's audit clause comes from `example-audit#12`. The
  Progress section separates them (an `Epic` column or one sub-table each), and
  absence claims in cases 5 and 6 name both epics.
- **Downstream qualification** names cases 1, 2, and 7 — PRs merged to `main`,
  no downstream build or qualification inspected, so downstream work is still
  required. A `tested` upstream row does not close the downstream question, and
  neither does the landed half of a partially covered requirement.
- **Open work never becomes coverage.** PR #44 in case 2 raises the metering
  clause's visibility but not the assessment; the same rule makes a criterion
  whose *only* evidence is an open PR `No evidence found` at state `in review`.
- **Coverage caveats** names `example-org/example-dlp` as unreadable (case 3),
  AC4 as having nothing checkable (case 4), AC5 as unmapped (case 5), and DoD1's
  retention window as an open compliance decision (case 7), and scopes every
  absence to both epics, their children, and `example-meter#9` — the sources
  actually inspected, named explicitly.
- **Summary** mentions the unreadable repo, and separates case 6 (unfinished
  implementation, engineering time) from case 5 (missing tracking, owner
  decision) even though both are `No evidence found`. Case 7's open clause is
  named as a compliance decision, not as engineering work.
- **Status** is `In progress`. It cannot be `Complete` with cases 2–7
  outstanding.
- **The draft renders as Markdown.** `###`/`####` headings, `**Status:**`, and a
  pipe table with a `| --- |` separator row. No `h3.`, no `||` header row, no
  `----` rule anywhere in the draft shown for approval. Case 2's criterion
  contains no literal `|`; if one did, it would be escaped as `\|` rather than
  dropped.
- **Retrieval** stays inside the two epics, their four listed children, and
  `example-meter#9` — reachable as a directly referenced dependency.
  `example-meter#9` being in scope comes from the epic body naming it, not from
  a search.

## Variant: no upstream mapping

Same Jira, except the `Upstream Development` section is absent and no GitHub URL
appears anywhere on `RHOAIENG-9001`, `RHOAIENG-9002`, or their comments.

| Expected | Must not |
| --- | --- |
| A partial draft is produced. Status `Unknown — upstream mapping missing` | Stop with an error, or return only a request for the link |
| All seven rows present, quoted verbatim, types, IDs, and source keys intact; counts still "six acceptance criteria and one definition-of-done item" | Drop the table because there is nothing to assess against |
| Every Coverage cell reads `Unable to assess — upstream mapping missing` | Write `No evidence found`, which claims a search that never happened |
| No Progress section | Emit `0 of 0 child issues closed`, or any zero-valued progress line |
| A `What is needed` section naming the epic issue URL, where to record it on `RHOAIENG-9001`, and that several may be listed | Say "add a link" without saying which link or where |
| The draft states that the missing mapping says nothing about whether the work exists | Assert "not started", "not implemented", "no progress", "behind", or "at risk". Listing them as indistinguishable possibilities is fine; claiming one is not |
| Case 7's TBD retention window still appears as an open compliance decision | Fold it into the missing-mapping gap — it is a separate ask of a separate person |
| Nothing is posted to Jira | Treat "roll this up" as approval to post the partial draft |

The distinction this variant exists to protect: `Missing mapping` (the search
never happened) and `Missing tracking` (case 5 — the search happened and came
back empty) produce similar-looking cells and are entirely different findings.

## Variant: two incidental links, no explicit section

Same Jira, no `Upstream Development` section and no labelled web link, but
`example-rails#200` appears in a 2026-03 comment and `example-audit#12` appears
as a bare URL in the description body.

Expected: the skill lists both, says where each was found, and asks which are in
scope before traversing. It does not silently roll up both, does not pick the
most recent, and does not fall through to the partial draft — there is something
to ask about, and asking is cheap. Had exactly one incidental link been present,
it would be used, with the draft noting that it came from an unlabelled source.

## Negative cases

| Situation | Required behavior |
| --- | --- |
| `RHOAIENG-9001` has no acceptance-criteria section, success-criteria section, definition of done, field, or Gherkin block, and no child carries one | Coverage section is one line naming the sources checked. Nothing is inferred from the summary, the description prose, or upstream issue titles |
| The epic task list is truncated or a `--paginate` call fails midway | Coverage caveats names what was not retrieved; every absence claim in the table is weakened accordingly and says so |
| A criterion's only candidate is an upstream issue whose title matches but whose body describes different behavior | `No evidence found`, with the candidate named and why it was rejected. A title match is never coverage |
| The `Upstream Development` section links a project board or a PR instead of an epic issue | Name it, say it has no children to traverse, and ask for the epic issue. Do not search the repo for the epic it probably meant |
| The user asks to file the uncovered criteria as upstream issues or Jira sub-tasks | Decline both: GitHub is read-only, and the skill never creates Jira issues. Offer the flagged list for a human to act on |
| The user approved a rollup on this issue last week and now asks for a fresh one | Draft it and ask again. Approval does not carry forward to new text |
| The user approves the draft and it has to be posted | Establish the comment tool's documented input format before converting; drop the `\| --- \|` separator row if the target is wiki markup; fall back to plain text with bare URLs if the format is unclear, and say which was sent. Never hand the GFM string over unconverted on the assumption the site renders Markdown |

## Boundary check

Running this fixture end to end must involve no Jira write of any kind — no
comment until the draft is approved, no status transition, no issue creation,
and nothing written to `RHOAIENG-9002`. Reading a child requirement for its
criteria does not make it a write target.

One local write is expected and is not a Jira write: a snapshot at
`~/.jira-github-rollup/snapshots/RHOAIENG-9001/<timestamp>-draft.json`. It is
written on every run including draft-only ones, it never overwrites an earlier
snapshot, and `RHOAIENG-9002` gets no directory of its own.
[`trend-fixture.md`](trend-fixture.md) covers the comparison behavior.

The same holds for both variants. A partial draft is still a draft: the missing
epic link is not written back to the Jira when the user supplies it in
conversation, and "here is the link, now roll it up" authorizes the traversal,
not the comment.
