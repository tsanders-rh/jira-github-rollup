# Example: a generated rollup

**Everything on this page is fictional.** Illustrative output for a made-up
requirement `RHOAIENG-1234`, derived from the epic linked in
[`jira-link-section.md`](jira-link-section.md). All orgs, repos, issue numbers,
acceptance criteria, test jobs, and dates are invented. No real issue, PR, or
test result is referenced.

Two drafts are shown: the normal case, and the same requirement when no upstream
epic is linked. The skill would show either one for approval before posting it as
a comment — and if you only asked for a draft, it stops at the draft.

Both are reproduced exactly as the skill emits them: **GitHub-flavored Markdown**,
which is what renders in the conversation you are reviewing them in. If you
approve one for posting, the skill converts it to whatever the Jira comment tool
accepts at that point. The words do not change; only the markup does.

## The fictional input

`RHOAIENG-1234 — Tiered model routing` carries the four acceptance criteria and
the one definition-of-done item shown in
[`jira-link-section.md`](jira-link-section.md), and its child requirement
`RHOAIENG-1240 — Tier observability` carries one more acceptance criterion.
Upstream, the epic `example-org/example-gateway#412` lists four children and
references a fifth issue in a repository this account cannot read.

---

````markdown
### Upstream Development Rollup

**Status:** In progress
**Source epic:** [example-org/example-gateway#412](https://github.com/example-org/example-gateway/issues/412) — Request routing for tiered models
**Generated:** 2026-10-05

#### Summary

Routing is implemented and merged, but only one of six requirements is fully
covered by the evidence found upstream. AC2's uncovered half is an
implementation gap, not an unknown: the config loader was read at the merge
commit and has no reload path. AC3 (metering of routing decisions) has
no linked upstream work in the sources inspected — a tracking gap rather than a
schedule slip, and it needs an owner to say where it lives. AC4 is an inspection
limitation, not a gap: example-org/example-dlp is unreadable from this account,
so that row is unresolved in either direction and this coverage section is
incomplete. RHOAIENG-1240 AC1 is tracked in
example-org/example-controller#88, which is owned by another team and has had no
activity since 2026-08-28. DoD1 is blocked on a product decision, not on
engineering: it requires a deprecation period whose length is still TBD.

#### Progress

2 of 4 child issues closed as completed; 4 pull requests merged.

| Child | Status | PRs |
| --- | --- | --- |
| example-org/example-gateway#413 — request routing | Closed (completed) | example-org/example-gateway#520 (merged 2026-09-18) |
| example-org/example-gateway#414 — tier config parsing | Closed (completed) | example-org/example-gateway#531 (merged 2026-09-30), example-org/example-gateway#536 (merged 2026-10-01), example-org/example-gateway#541 (merged 2026-10-02) |
| example-org/example-controller#88 — CRD plumbing | Open | — |
| example-org/example-tests#15 — e2e coverage | Open | example-org/example-tests#22 (open, 11d) |

#### Requirements coverage

5 acceptance criteria, 1 definition-of-done item.

| Requirement | Evidence | Evidence state | Coverage | Gap / next validation step |
| --- | --- | --- | --- | --- |
| AC1 (RHOAIENG-1234) "Requests for a tiered model are routed to the serving pool configured for that tier." | example-org/example-gateway#413, PR example-org/example-gateway#520 (merged 2026-09-18) | tested | Evidence found — PR #520 implements tier-to-pool selection; CI job e2e-routing passed on the merge commit and asserts pool assignment per tier | Downstream qualification pending; see below |
| AC2 (RHOAIENG-1234) "An unknown tier is rejected with HTTP 400, and tier configuration changes take effect without a gateway restart." | example-org/example-gateway#414, PRs #531, #536 (merged 2026-09-30, 2026-10-01) | merged | Partial evidence — the 400 on an unknown tier is covered: PR #536 adds tests/test_tier_reject.py asserting it. The no-restart clause is not. `internal/config/loader.go` at 4a7e9c2 (the #536 merge commit) reads the file once from `main()` and registers no watcher, and `config_test.go` at the same commit asserts parsing only | **Implementation gap** — add a reload path under #414 or open an issue for it |
| AC3 (RHOAIENG-1234) "Routing decisions, including denials, are recorded in the metering stream within 60 seconds." | — | — | No evidence found — no issue in example-org/example-gateway#412 or its four children maps to metering | Owner to identify upstream coverage or confirm this is a gap |
| AC4 (RHOAIENG-1234) "Streaming responses are subject to the same tier enforcement as non-streaming responses." | example-org/example-dlp#31 (referenced from the epic body; not readable) | — | Unable to assess — #31 is a candidate mapping from its title only. example-org/example-dlp returned 404 for this account, so its contents could not establish the enforcement behavior | **Inspection limitation** — grant read access, or have the owner confirm #31 covers streaming tier enforcement |
| DoD1 (RHOAIENG-1234) "The admin guide documents tier configuration, and the gateway logs a deprecation warning for the legacy per-model pool field for at least one release before removal (release count TBD with product)." | example-org/example-gateway#414, PRs #536 (merged 2026-10-01), #541 (merged 2026-10-02) | merged | Partial evidence — PR #541 adds docs/admin-tiers.md covering tier configuration, and PR #536 emits the deprecation warning (tests/test_legacy_warning.py asserts it). The deprecation period cannot be checked at all: the release count is left TBD in the criterion itself | Product to set the release count; the two landed clauses need no further upstream work |
| AC1 (RHOAIENG-1240) "Per-tier request counts and p99 latency are exposed on the controller /metrics endpoint." | example-org/example-controller#88 (open, no PR) | planned | No evidence found — #88 is open with no linked PR; the sources inspected show planned work, not implemented behavior | Engineering time on #88; owned by the controller team |

#### Downstream qualification

- AC1 (RHOAIENG-1234) — implementation merged to main on 2026-09-18. No
  downstream build or qualification run was inspected, so downstream integration
  is still required.
- AC2 (RHOAIENG-1234) — same; the covered half is not qualified downstream either.
- DoD1 (RHOAIENG-1234) — the docs and warning merged upstream on 2026-10-01 and
  2026-10-02; whether they appear in a downstream build was not inspected.
Requirements not listed above have no identified downstream step in the sources
inspected; that is not confirmation that none is required.

#### Coverage caveats

- 2 source files read as a bounded follow-up, at the revisions named:
  `example-org/example-gateway@4a7e9c2:internal/config/loader.go`,
  `example-org/example-gateway@4a7e9c2:internal/config/config_test.go`. Both at
  the #536 merge commit, not at the current default branch.
- example-org/example-dlp is not readable from this account (404 on
  example-org/example-dlp#31), so AC4 could not be assessed in either direction.
- **This investigation is incomplete.** One criterion (AC4) carries a clause
  that could not be inspected. The position on it is unresolved, not negative.
- AC3 has no upstream mapping in the reachable set. No search beyond the epic and
  its children was performed, so this is an absence in those sources, not a
  finding that the work does not exist.
- DoD1 leaves the deprecation period as "TBD with product". The clause is
  unassessable until someone sets a number; the rest of the item was assessed
  normally.
- Coverage was assessed against example-org/example-gateway#412, its four
  children, and example-org/example-dlp#31 only. No wider search was run.

#### Risks and blockers

- example-org/example-controller#88 has no linked PR and no activity since
  2026-08-28 (38 days). It is in a repository this team does not own, and it is
  the only tracking for RHOAIENG-1240 AC1.
- AC3 has no upstream issue in the reachable set, so nothing connects this
  requirement to work on metering. Whether such work exists elsewhere is not
  something this traversal can see.
- example-org/example-tests#22 has been open 11 days with no review.

#### Trend since previous snapshot

Baseline established — no prior snapshot available.

---

_Generated by the jira-github-rollup skill from example-org/example-gateway#412.
Read-only against GitHub; no Jira issues were created._
````

---

## What to notice

**The lede is the coverage gap, not the progress.** Four PRs merged and two
children closed, but the summary opens with the count of requirements that are
not covered. A program manager scanning the issue learns in the first sentence
that "routing is merged" and "the requirement is covered" are different claims.

**The counts are typed.** The table holds six rows: five acceptance criteria and
one definition-of-done item, and the counts line says exactly that. Calling it
"six acceptance criteria" would tell a reader that product committed to six
behaviors when it committed to five, and that the sixth — a release-engineering
condition — is the same kind of obligation. It is not, and it fails for a
different reason.

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

**AC2 shows what partial means, and that the question got answered.** The
criterion has two clauses. One has a named test file. For the other, the first
pass had only "nothing in #531 or #536 touches config reload" — which is a
statement about a changed-file list, not about the product. The file that would
settle it was named in evidence already collected and was readable, so it was
read, at the merge commit of the PR being assessed rather than at today's main.
That turned an open question into a finding: `loader.go` has no watcher, so the
clause is an **implementation gap** and the next action is engineering work on a
known file. Had the loader shown a watcher whose wiring was unclear, the same
read would have produced an **evidence gap** instead — inspected, still
unresolved — and the next action would have been another read, not a ticket.

**The three labels send the reader to three different people.** `Implementation
gap` (AC2) is engineering's. `Inspection limitation` (AC4) is whoever can grant
read access. `Decision needed` (DoD1) is product's. Collapsing them into
"partial" would be accurate and useless. The distinction also governs what the
rollup is allowed to claim: an unread file is never an implementation gap, and
the absence of a test is not by itself the absence of an implementation.

**DoD1 shows that a TBD does not void a row.** The item names three things: the
admin guide, the deprecation warning, and a deprecation period nobody has set.
Two of the three were checkable against the evidence and were checked — both
landed, both named. Only the third is unresolved, and the row says what it is
waiting on and who owns it. Marking the whole item `Unable to assess` on account
of one undecided number would have thrown away a real finding and sent the reader
to engineering for what is a product decision.

**Criteria are quoted, and sourced.** The last row is `AC1 (RHOAIENG-1240)`, not
`AC5 (RHOAIENG-1234)` — IDs are numbered per type per source issue, so the table
contains two different `AC1`s and the key is what tells them apart. Without it a
reader would hold the parent's owner accountable for the child's criterion. The
same numbering is why the parent's fifth row is `DoD1` and not `AC5`. The wording
is the Jira's, not a tidied-up version: a paraphrased criterion is a criterion
the skill made up.

**Status is `In progress`, not `Blocked`.** Real work merged recently. `Blocked`
is reserved for cases where nothing can proceed, and it always requires a named
blocker in the Risks section. It is also not `Complete`, which would require all
six requirements at `Evidence found` with no downstream work outstanding.

**The cross-repo child is called out three times** — in the Progress table
(different repo), in Risks (different owning team), and in the coverage table
(it is the only tracking for RHOAIENG-1240 AC1). That dependency is the most useful
thing in the rollup, and it is exactly what a single-repo traversal would have
missed.

**The trend section is one line, because this is the first run.** `Baseline
established — no prior snapshot available` — not a table of zeroes, and not a
delta reconstructed from the Jira's own history. There is no history to report
and the section says so. This run saves a snapshot to
`~/.jira-github-rollup/snapshots/RHOAIENG-1234/`, which is what the next run
compares against; see [`sample-rollup-rerun.md`](sample-rollup-rerun.md) for what
that looks like four weeks later. On that later run the skill also finds the
marker line at the bottom and offers to update this comment in place rather than
appending a second near-identical update — which is exactly why the baseline is
kept on disk and not parsed back out of the comment.

**No filler.** There is no "No other risks identified" line and no restatement of
the requirement's description. If a section has nothing evidenced to say, it is
omitted — but `Coverage caveats` is not optional when a source was unreadable.

**The draft is Markdown, not Jira markup.** A six-row five-column table written
as `||` header rows is unreviewable in a terminal, and approving what you cannot
read is not approval. The posted comment may well end up as `h3.` and `||` — that
conversion happens after you say yes, against whatever format the Jira tool takes,
and it changes nothing above except the punctuation.

---

## The same requirement with no upstream link

Identical Jira, except nobody added an `Upstream Development` section and there
is no GitHub URL anywhere on the issue. The skill does not stop; it reports the
half it can see.

````markdown
### Upstream Development Rollup

**Status:** Unknown — upstream mapping missing
**Source epic:** none recorded on RHOAIENG-1234
**Generated:** 2026-10-05

#### Summary

RHOAIENG-1234 records no link to upstream GitHub work, so no upstream state was
inspected: upstream progress could not be assessed, and neither could coverage
for any of its six requirements. The requirements below are reproduced from the
Jira as stated. This is a
statement about the issue, not about the work: upstream development may be
complete, in flight, or unstarted, and nothing reachable from this issue
distinguishes those.

#### Jira scope

RHOAIENG-1234 — Tiered model routing (In Progress, fix version 2.22)
Child requirements read: RHOAIENG-1240 — Tier observability (To Do)

#### Requirements coverage

5 acceptance criteria, 1 definition-of-done item.

| Requirement | Evidence | Evidence state | Coverage | Gap / next validation step |
| --- | --- | --- | --- | --- |
| AC1 (RHOAIENG-1234) "Requests for a tiered model are routed to the serving pool configured for that tier." | — | — | Unable to assess — upstream mapping missing | Link the upstream epic |
| AC2 (RHOAIENG-1234) "An unknown tier is rejected with HTTP 400, and tier configuration changes take effect without a gateway restart." | — | — | Unable to assess — upstream mapping missing | Link the upstream epic |
| AC3 (RHOAIENG-1234) "Routing decisions, including denials, are recorded in the metering stream within 60 seconds." | — | — | Unable to assess — upstream mapping missing | Link the upstream epic |
| AC4 (RHOAIENG-1234) "Streaming responses are subject to the same tier enforcement as non-streaming responses." | — | — | Unable to assess — upstream mapping missing | Link the upstream epic |
| DoD1 (RHOAIENG-1234) "The admin guide documents tier configuration, and the gateway logs a deprecation warning for the legacy per-model pool field for at least one release before removal (release count TBD with product)." | — | — | Unable to assess — upstream mapping missing | Link the upstream epic; separately, product to set the release count |
| AC1 (RHOAIENG-1240) "Per-tier request counts and p99 latency are exposed on the controller /metrics endpoint." | — | — | Unable to assess — upstream mapping missing | Link the upstream epic |

#### What is needed to complete this assessment

- The GitHub epic issue URL for this requirement, recorded on RHOAIENG-1234 in an
  `Upstream Development` description section or as a web link labelled
  `Upstream epic`. List several if this requirement spans more than one epic —
  all of them will be rolled up.
- RHOAIENG-1240 may carry its own epic link; it has none either, and its
  criterion is assessed against whatever is linked from the parent unless it gets
  its own.
- Nothing else is blocking. All six requirements were read cleanly and will be
  assessed as soon as an epic is supplied.

#### Trend since previous snapshot

Baseline established — no prior snapshot available.

---

_Generated by the jira-github-rollup skill. No upstream link was found on
RHOAIENG-1234. Read-only against GitHub; no Jira issues were created._
````

### What to notice here

**It is a draft, not a refusal.** The requirements table is the expensive part of
the rollup and none of it depended on GitHub. Withholding it because one input is
missing would throw away the extraction, the typing, the source attribution, and
the verbatim quoting — and leave the reader with nothing to act on but an error
message.

**No Progress section, and no zeros.** `0 of 0 child issues closed; 0 pull
requests merged` would be literally true and completely misleading. Nothing was
counted because nothing was looked at.

**Every Coverage cell says the same thing.** `Unable to assess — upstream mapping
missing`, not `No evidence found`. The second would claim a search took place and
came back empty, which is the single most dangerous sentence this skill could
write: a reader would act on it as a finding about the product. Every row here
is an inspection limitation of the same kind, from the same cause, which is why
they are stated once in `What is needed` rather than six times in the table.

**The Summary says the quiet part out loud.** "Upstream development may be
complete, in flight, or unstarted." A missing link is routine — the most common
cause is that a team is shipping fine and nobody updated the Jira. The draft
refuses to let the absence of a link read as absence of work.

**`What is needed` is specific enough to act on.** Not "add a link" but which
link, on which issue, in which section, and what happens next. It also notes what
is *not* blocking, so the reader does not assume the rest of the analysis is also
broken.

**The TBD still gets named.** DoD1's undecided release count is independent of
the missing epic, so it stays in the Gap column. Two different people are being
asked for two different things, and the draft keeps them separate.

**A snapshot is still saved.** Nothing upstream was inspected, but the
requirements, their types, and their verbatim text were all read successfully,
and those are what the next run matches against. The snapshot records child
completion as unknown rather than `0/0` — see
[`trend-fixture.md`](trend-fixture.md), variant 7, for what the trend section
does when a mapping disappears between runs.
