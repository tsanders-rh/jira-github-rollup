# PoC plan

Status: **proof of concept**, started 2026-10-05. Not yet run against a real
requirement.

## Goal

Determine whether an agent can produce a development rollup that an EM would
actually post to a Jira issue without rewriting it — working only from a
human-placed GitHub epic link.

The bar is not "produces output." It is **trustworthy enough to post unedited,
most of the time.** A rollup that needs verification every run costs more than
writing it by hand.

## Scope

### In scope

- One Jira issue in, one draft rollup out.
- Epic discovery from links a human already placed on the Jira issue, or supplied
  in the request. All explicitly linked epics are in scope, not just the first.
- A partial draft when no link exists at all: Jira scope and requirements
  reported, upstream coverage marked unassessable, the needed link named.
- Traversal of child issues via native sub-issues, epic-body task lists, and
  timeline cross-references.
- Child issues in repositories other than the epic's.
- PR resolution per child, including merge state and target branch.
- Requirement coverage: acceptance criteria, success criteria, and
  definition-of-done items quoted from the named issue and its child
  requirements with their types preserved, mapped to upstream evidence, with a
  per-requirement coverage assessment and a separate downstream-qualification
  statement.
- CI and changed-file evidence on PRs, used only to support a named behavior.
- Posting the approved draft as a comment on that same Jira issue.
- Updating a prior rollup comment in place instead of appending.
- A dated JSON snapshot per run, saved under
  `~/.jira-github-rollup/snapshots/<JIRA-KEY>/`, append-only, drafts
  distinguishable from published.
- A trend section reporting unweighted movement against the previous snapshot:
  child issues completed, requirements with evidence found, downstream
  qualification confirmed, the counts behind each, and a classified list of what
  changed.

### Explicitly out of scope

- **Creating mirrored Jira issues.** This is the premise of the approach, not a
  deferred feature. Mirroring creates two systems of record; the whole point is
  to avoid that.
- **Creating or linking the GitHub epic.** Deciding which epic corresponds to a
  requirement is a judgment call. A wrong link silently poisons every rollup
  after it, and the failure is invisible — the rollup looks fine.
- **Bulk rollups across a whole Jira project.** Single issue only until accuracy
  is established. Bulk amplifies a systematic error across dozens of issues.
- **Writing to GitHub.** Read-only, no exceptions.
- **Scheduled or unattended runs.** Every post needs a human yes.
- **Inferring a criterion-to-issue mapping.** Retrieval stops at the linked
  epics, their children, and dependencies those artifacts name directly. An
  unmapped criterion is flagged for owner review; it is never resolved by an
  org-wide or keyword search. The failure mode is the same as a wrong epic link —
  a confident mapping nobody checked.
- **Authoring acceptance criteria.** If the Jira has none, the rollup says so.
  Writing criteria is requirements work, and an agent-invented criterion that
  later reads as approved is worse than a blank.
- **Downstream qualification evidence.** The skill reports that downstream work
  is still required; it does not inspect downstream builds, payloads, or
  qualification runs. Whether it should is open question 8. A consequence worth
  stating plainly: until that changes, the downstream row of every trend section
  reads `0 confirmed, 0 pending, N unknown`.
- **Estimation and forecasting.** No effort weighting, no story points, no
  velocity, no burn-down, no projected completion date. The trend section
  reports movement between two observations and is deliberately built so that a
  rate cannot be read out of it.
- **Shared or synchronized snapshot storage.** Snapshots are local to one
  machine and one user. Two people rolling up the same issue keep separate
  histories — see open question 14.

## Open questions

These need answers from real data before this is more than a PoC.

1. **Do our upstream epics actually expose children in a traversable way?**
   If epics are maintained as prose rather than task lists or native sub-issues,
   traversal returns nothing and the whole approach fails. **This is the
   assumption most likely to be wrong, and it is cheap to check first.**

2. **How often are cross-repo children listed on the epic at all?**
   The skill can only follow links that exist. A child in another repo that
   nobody added to the epic is invisible — and the rollup will look complete
   while missing the actual blocker. There is no way to detect this from the
   epic alone.

3. **Do PRs reliably link to their issues?** Without `Closes #N`, the rollup can
   report open/closed but not merge state, which is most of its value.

4. **What does `addOrEditJiraIssueComment` actually accept?** Wiki markup, ADF,
   or plain text, depending on the site's editor and on what the MCP tool does
   with the string. It decides whether the posted coverage table renders or
   shows as literal pipes. The skill now reads the tool's own schema and falls
   back to plain text, but one test comment on a scratch issue would replace the
   fallback with a known answer — and would also tell us whether the five-column
   table survives at all.

5. **Does a rollup comment actually get read?** If the answer is no, the right
   output is a description section or a dashboard, not a comment. Worth asking
   before polishing the comment path.

6. **Nested epics** — the skill stops after one level. Is that the right depth,
   or do our requirements routinely nest deeper?

7. **Do our requirements carry explicit acceptance criteria at all?**
   The coverage section is worth nothing if criteria live in a linked design doc,
   a Slack thread, or an EM's head. Like question 1, this is cheap to check and
   likely to be the thing that decides whether this half of the skill is useful.
   The failure is benign — the rollup reports "no criteria found" — but the
   feature is then dead weight.

8. **Where does downstream qualification evidence live?**
   Every criterion that lands upstream raises the same question, and right now
   the rollup can only say "still required." If that answer is identical on every
   row forever, it is noise. If downstream state is readable from somewhere
   specific, that is the next increment.

9. **Is the 12-criterion collapse threshold right?**
   Requirements with fifteen criteria produce a table nobody reads, which is the
   same failure as a rollup that runs past a screen. `rollup-format.md` collapses
   `Evidence found` rows with no downstream step above 12 criteria. The number is
   a guess until some real requirements are measured.

10. **Do criteria on child requirements belong in the parent's rollup?**
    Currently yes, one level down, attributed to the child. If teams split
    requirements finely this could pull in criteria the parent's audience does
    not consider theirs.

11. **Is a partial draft worth posting, or only worth showing?**
    It is useful to the person who ran it. Whether a comment reading "nobody
    linked an epic" belongs on the issue, or is better handled by just adding
    the link, is unknown. If every partial draft gets discarded rather than
    posted, the right output may be a shorter prompt for the link.

12. **Do our requirements actually separate the three types?**
    The typing rule costs nothing if every issue has one `Acceptance Criteria`
    heading. It pays off only if teams genuinely use `Definition of Done` and
    `Success Criteria` with different meanings. Answerable from the same three
    real requirements as question 7.

13. **How common is the mixed criterion — part checkable, part TBD?**
    The split-assessment rule is the most intricate thing in step 8. If real
    criteria rarely carry an open parameter, it is complexity that never fires;
    if they routinely do, `Unresolved requirement` may deserve to be a column
    rather than prose in a cell.

14. **Is local-only snapshot storage enough?**
    Snapshots live on one machine under one home directory. If two people roll up
    the same issue, each sees only their own history, and the trend section each
    gets is correct but different. A shared store (a repo, an S3 prefix, a Jira
    attachment) would fix that and costs a sync mechanism, a merge policy, and a
    place for private criteria text to leak. Local-only is the right PoC answer;
    it may not survive a second user.

15. **Does anyone act on the trend section?**
    The parallel to question 5. A trend that nobody reads is three ratios of
    overhead on every rollup. Worth watching whether the first question after a
    posted rollup is ever "what changed since last time" — if it is always
    "what's left", the section is answering the wrong question.

16. **How often does requirement text change versus get replaced?**
    Match pass 2 pairs an edited criterion with its previous self; pass 3 gives
    up and reports a removal plus an addition. If real teams edit criteria in
    place constantly, the near-match heuristic carries more weight than it
    deserves and should probably be replaced by asking.

## Milestones

| # | Milestone | Done when |
| --- | --- | --- |
| 1 | Link conventions agreed | A real Jira issue carries an epic link in the documented form |
| 2 | Traversal validated | Skill enumerates the correct children, cross-repo included, verified by hand |
| 3 | Criteria extraction validated | Criteria quoted verbatim from three real requirements, with types, sources, and counts correct and nothing invented |
| 4 | Coverage assessments defensible | On three real requirements, an EM agrees with every assessment, or disagrees only about `Partial` vs `Evidence found` |
| 5 | Draft quality | Three consecutive rollups an EM would post with no edits |
| 6 | Round trip | An approved draft posts cleanly and renders correctly |
| 7 | Idempotence | A second run updates the prior comment rather than duplicating |
| 8 | Trend survives a real interval | Two runs a fortnight apart on the same real requirement, where every reported change is one a human confirms happened, and every unreported thing genuinely did not change |

Milestone 2 is the real gate. If traversal is unreliable, nothing downstream
matters — and questions 1 and 2 above are answerable in an afternoon against
three real epics.

Milestone 4 is the gate for the coverage half, and it is the harder one. The
tolerated disagreement is deliberate: `Partial` vs `Evidence found` is a judgment
call about how much of a criterion a PR covers. `Evidence found` where an EM says
`No evidence` is not a judgment call — it is the failure the coverage section
exists to prevent, and it fails the milestone outright.

## Success criteria

The PoC succeeds if, across five real requirements:

- Epic and child discovery is correct on at least four, with every miss traceable
  to a missing upstream link rather than a traversal bug.
- At least three rollups are postable with no edits.
- No rollup overstates progress. **A single "done" that was not done fails the
  PoC** — an inflated status update is worse than no status update, because it
  stops people from asking.
- No criterion is reported as covered on evidence that does not support it. A
  single `Evidence found` that an EM can refute fails the PoC, for the same
  reason and more sharply: a coverage table is read as a verification record.
- No criterion appears in a rollup that is not in the Jira, in any form, and no
  criterion is reported under a type the Jira did not state it under.
- Every absence claim in a shipped rollup is scoped to the sources inspected.
- No rollup describes work as unstarted, behind, or at risk on the strength of a
  missing link. A partial draft that reads as bad news fails the PoC the same way
  an overstated one does, in the opposite direction.
- Total time per rollup, including review, is under what writing it by hand costs.
- No trend section reports a change that did not happen, and none misses one that
  did. A false "+2 requirements covered" is the same failure as an overstated
  status, arriving by a different route.
- No trend section credits as progress work that merged before the baseline, and
  none presents a denominator change as a regression.
- No reader of a trend section infers a completion date from it. If one does, the
  section is wrong regardless of whether its numbers were right.

## Known risks

- **Garbage in.** Rollup quality is bounded by epic hygiene upstream. The skill
  cannot report on children nobody linked. This may turn into a case for
  improving epic hygiene rather than a case against the skill.
- **False confidence.** A well-formatted rollup reads as authoritative. The
  marker line, timestamp, and source-epic line exist so a reader can judge
  staleness and check the source — keep them.
- **A coverage table read as a verification record.** This is the sharpest
  version of the risk above. A five-column table with issue links looks like QA
  output, and someone will eventually cite it as evidence a requirement was
  verified. The scoped absence wording, the `Coverage caveats` section, and the
  separate downstream-qualification statement are the counterweights. They are
  load-bearing, not hedging, and trimming them for brevity defeats the feature.
- **Absence misread as completeness.** A criterion nobody linked and a criterion
  nobody implemented look identical from the epic. The rollup distinguishes them
  in wording only — it cannot detect the first case, which is why unmapped
  criteria are escalated to an owner rather than resolved by the skill.
- **A partial draft read as a status report.** It has the same heading, the same
  table, and the same marker line as a real rollup, and a reader skimming it may
  take a column of `Unable to assess` as a column of bad news. The `Unknown`
  status, the absent Progress section, and the explicit "this says nothing about
  whether the work exists" sentence are what hold that apart. They are the
  load-bearing parts of that shape, not padding.
- **A trend section read as a burn-down.** Three ratios and a set of deltas look
  like a projection whether or not one is offered, and the first thing anyone
  does with two data points is extrapolate. The unweighted-indicator label, the
  refusal to weight partial coverage, and the absence of any rate or date are
  the counterweights. This is the risk most likely to be realized by someone
  pasting the numbers into a different document, where the label does not travel.
- **Discovery credited as progress.** Restoring access to a repository, or
  someone finally adding an epic link, can move several requirements to
  `Evidence found` in a run where nothing was built. Reported as a month's
  progress, that is a false status update produced by an honest pipeline. The
  evidence-timestamp test is the guard, and it fails quietly when evidence
  carries no usable date — which is why `undetermined` exists and must not be
  collapsed into progress.
- **A stale mapping resurrected from the snapshot.** The store now remembers
  which epic was linked last run, which makes it mechanically easy to keep using
  a link a human deleted. That is the no-guessing constraint breached from a new
  direction, and it is why the rule is to report what used to be mapped and
  refuse to traverse it.
- **Snapshot drift from a hand-edited store.** The files are plain JSON in the
  user's home directory, and nothing stops them being edited or partially
  deleted. The schema version catches shape changes; it does not catch a
  plausible-looking lie. A baseline is trusted as far as the user's own disk is.
- **Rate limits.** Deep traversal across many repos makes a lot of API calls.
  Not a concern at single-issue scale; would be at bulk scale.
- **Scope creep toward mirroring.** The first time someone asks "can it just
  create the Jira sub-tasks too," the answer is no, and the reason is recorded
  here and in `CLAUDE.md`.

## Decisions

Record decisions that relax or clarify a constraint here, with the date and the
reasoning.

- *2026-10-05* — Initial scope. No Jira issue creation; epic linking stays manual.
- *2026-10-05* — Added acceptance-criteria coverage analysis. No hard constraint
  relaxed: GitHub stays read-only, no Jira issues are created, and the only write
  is still an approved comment on the one named issue. Criteria may be **read**
  from child requirements one level down; nothing is written to them.
- *2026-10-05* — Coverage retrieval is bounded to the linked epics, their
  children, and dependencies those artifacts reference directly. Rejected the
  alternative — searching GitHub for a plausible owner of an unmapped criterion —
  for the same reason the skill does not guess an epic: the wrong mapping is
  invisible in the output and poisons every rollup after it. Unmapped criteria
  are flagged for owner review instead.
- *2026-10-05* — Downstream qualification is reported as a separate statement
  per criterion rather than folded into the coverage assessment, so that
  `Evidence found` upstream can coexist with outstanding downstream work without
  either claim weakening the other.
- *2026-10-05* — Coverage assessment describes behavior; evidence state
  describes progress. An unmerged PR therefore raises the state to
  `in progress` / `in review` but leaves the assessment at `No evidence found`.
  The alternative — letting an open PR count as `Partial evidence` — makes
  `Partial` mean two different things and lets in-flight work read as coverage,
  which is the exact overstatement the section exists to prevent.
- *2026-10-05* — **A missing upstream mapping produces a partial draft rather
  than a stop.** This clarifies hard constraint 3 in `CLAUDE.md` without relaxing
  it: the prohibition on guessing an epic is unchanged, and the skill still asks
  for the link. What changed is that it no longer discards the work it already
  did. The Jira scope, the child requirements, and the verbatim requirements
  table cost nothing upstream and are the most useful part of the output;
  withholding them because one input is absent trades a usable artifact for an
  error message. The draft marks upstream progress and coverage
  `Unable to assess — upstream mapping missing`, names exactly what link would
  complete it, and is explicit that a missing mapping is not missing
  implementation. Status `Unknown — upstream mapping missing` was added for this
  and may never be softened to `Not started` — a team shipping fine that simply
  never updated the Jira is the most likely cause, and reporting them as
  unstarted is the worst available error.
- *2026-10-05* — **Requirement types are preserved end to end.** Acceptance
  criteria, success criteria, and definition-of-done items are extracted under
  separate ID prefixes (`AC`, `SC`, `DoD`; `REQ` for a list under no recognized
  heading), numbered per type per source issue, and counted separately in the
  output. Rejected the simpler alternative of normalizing everything to "AC":
  they are commitments of different kinds, made by different people, and a
  reader chases a failed DoD item differently from a failed acceptance criterion.
  A combined total labelled "acceptance criteria" misstates what was agreed.
- *2026-10-05* — **A criterion that mixes checkable clauses with an undecided
  parameter is assessed, not discarded.** The checkable clauses get the normal
  treatment; the unresolved clause is reported as a named clarification with its
  owner. `Unable to assess` is now reserved for a criterion with no checkable
  clause at all, plus access failures and truncated retrieval. The previous rule
  — any ambiguity makes the whole criterion unassessable — threw away real
  findings and, worse, pushed a product or compliance decision into the same
  bucket as an engineering gap. `Unresolved requirement` was added to the
  failure-kind list for exactly that reason. A row with an open clause still
  cannot reach `Evidence found`: the criterion as written cannot be met until
  someone says what it asks for.
- *2026-10-05* — **All explicitly linked epics are rolled up, without asking.**
  Link sources are now tiered: the `Upstream Development` section, a labelled
  GitHub web link, and a URL the user supplies in the request are explicit
  mappings; bare URLs elsewhere in the description and links in comments are
  incidental. Everything explicit is in scope — a requirement spanning a data
  plane and a control plane genuinely has two epics, and asking the user to pick
  one produces an under-reported rollup. Clarification is asked only where scope
  is genuinely unclear: several incidental links and nothing explicit, incidental
  links that would widen an explicit set, or a link pointing at a PR, board, or
  milestone. Every artifact stays attributed to the epic it came from, and
  absence claims enumerate all epics inspected — an absence scoped to one epic
  when two were traversed is a false statement about the other.
- *2026-10-05* — **The draft is GitHub-flavored Markdown; Jira markup is a
  conversion applied at post time.** The rollup now has one content contract and
  two renderings. Previously the draft was written in wiki markup because that
  is what the comment would eventually need, which meant the reviewer approving
  it saw `h3.` lines and `||` rows as literal punctuation in a terminal that
  renders Markdown — being asked to approve a table they could not read. The
  content, section order, and every verbatim quote are identical in both
  renderings; only the markup differs. Conversion happens once, after approval,
  and against what the comment tool documents as its input rather than an
  assumption: Jira Cloud sites take wiki markup, ADF, or plain text depending on
  the editor. Where that is unclear the payload is plain text with bare URLs,
  which degrades gracefully everywhere, and the skill says which format it sent
  so a mis-render is diagnosable. Open question 4 was rewritten to match.
- *2026-10-06* — **Snapshots are local JSON files, append-only, under
  `~/.jira-github-rollup/snapshots/<JIRA-KEY>/`.** This adds a write outside
  Jira, recorded as `CLAUDE.md` hard constraint 5 rather than left implicit.
  Rejected alternatives: *inside the Jira comment* — the skill edits that comment
  in place to avoid spam, which would destroy the baseline on every run, and it
  would mean parsing rendered prose back into data; *a Jira attachment or
  property* — a Jira write on every run, including draft-only runs, which breaks
  the approval rule for no benefit; *relative to the working directory* — the
  skill runs from wherever the user happens to be, so snapshots would scatter and
  occasionally be committed to an unrelated repository. Append-only is the part
  that matters: a run writes a new dated file and never overwrites or deletes
  one, and promotion from draft to published edits only the run's own file. The
  cost is accepted deliberately — snapshots are local to one machine and one
  user, so two people rolling up the same issue keep divergent histories
  (open question 14), and the files hold verbatim criteria from private issues
  in plaintext on disk, which the README states rather than hides.
- *2026-10-06* — **The trend section reports unweighted counts and refuses to
  forecast.** Three ratios — child issues completed, requirements with evidence
  found, requirements confirmed downstream — each with its fraction, its
  supporting counts, and a percentage-point delta. No effort weighting, no story
  points, no velocity, no burn-down, no projected date, and a mandatory label
  saying so. Rejected giving `Partial evidence` fractional credit: there is no
  basis for deciding a two-clause criterion is half met, the number would be
  invented, and a weighted ratio reads as progress toward release — which is the
  one reading the section must not support. `Partial` is counted in its own
  bucket where a reader can see it.
- *2026-10-06* — **Unassessable requirements and `NOT_PLANNED` children stay in
  the denominator.** Removing either would make losing access, or descoping work,
  render as an improvement. A child closed with an empty `stateReason` — GitHub
  recorded no reason before 2022 — is a fourth bucket, named and not counted as
  completed, rather than being silently normalized either way. Verified against
  `gh` 2.81.0: `gh issue view --json stateReason` returns `COMPLETED`,
  `NOT_PLANNED`, or `""`.
- *2026-10-06* — **An unobservable count is `unknown`; only an observed zero is
  `N/A`.** Initially both the no-mapping case and the unreadable-epic case were
  going to render `N/A`, which was wrong: a 404 is not a count of zero, and
  `0/0` or `0%` claims a measurement that never succeeded. `N/A` now means the
  epic was read and has no children. Same reasoning as `Unable to assess` versus
  `No evidence found`, applied to the numbers.
- *2026-10-06* — **Requirements are matched across snapshots on
  `(source key, type, verbatim text)`, never on ID.** IDs are per-type ordinals,
  so inserting one criterion renumbers every criterion below it and an ID-based
  diff reports a wall of changes that never happened. Verbatim text becomes
  load-bearing for a second reason beyond quoting: it is half the match key, so
  a tidied-up copy silently breaks the comparison against every future run.
- *2026-10-06* — **Assessment changes are split into implementation progress
  versus newly discovered evidence,** decided by comparing each new piece of
  evidence's date against the baseline's timestamp. Access restored or a link
  finally added can move several requirements in a month with no code written,
  and reporting that as progress would be a false status update produced by an
  honest pipeline. Where evidence carries no usable date the answer is
  `undetermined`, said out loud — never defaulted to progress.
- *2026-10-06* — **The baseline is the most recent published snapshot,** falling
  back to the most recent draft with an explicit "never published" label. A
  published snapshot is what a reader of the Jira issue last saw, and the trend
  section is addressed to them. With no snapshot at all the line is
  `Baseline established — no prior snapshot available`; the issue's history and
  a previous rollup comment are both available and neither is a baseline, since
  a comment is rendered prose rather than data. A mapping remembered from a
  previous snapshot is reported as *what used to be mapped* and is never
  traversed — otherwise the store would quietly reintroduce guessing from a new
  direction.
- *2026-10-06* — **`Since last rollup` is replaced by
  `Trend since previous snapshot`,** rather than both existing. The old section
  was a free-text delta against the prior comment; the new one is the quantified
  version of the same idea with a real data source behind it. Keeping both would
  have invited the two to disagree.
- *2026-10-08* — **The deterministic half of a run moves into scripts, and raw
  API responses stop entering the conversation.** The repo now contains code:
  `.claude/skills/jira-github-rollup/scripts/` (Python 3.9+, standard library
  only) and `tests/`. The division is that code does what is mechanical and
  fails silently when done by hand — reference normalization and
  deduplication, traversal, caching, content hashing, change detection,
  counting, percentages, rendering, and the snapshot store — while the model
  does what is judgement: reading the Jira, quoting requirements verbatim,
  deciding what evidence establishes, and writing the prose. No hard constraint
  is relaxed. GitHub access remains read-only (`gh` only, no mutating
  subcommand), no Jira issue is created, nothing in `scripts/` can reach Jira at
  all, and the posting step is unchanged: the model shows a draft, waits for
  approval of that specific draft, and posts it itself. No new dependency and no
  new credential; `gh` was already authenticated.

  Rejected alternatives: *having the scripts call Jira* — it is MCP-only, and
  giving a script its own Jira credential would add a write path the approval
  rule could not see; *letting the scripts decide coverage* — a script that
  rules on whether a merged PR satisfies a criterion is confidently wrong in a
  table cell, which is the failure this design exists to prevent; *trimming the
  instructions by deleting rules* — the reduction came from removing duplicated
  prose and moving detail into references read on demand, not from dropping
  safeguards.

  Two consequences recorded deliberately. The **cache** at
  `~/.jira-github-rollup/cache/<JIRA-KEY>/` is a second write outside Jira, so
  hard constraint 5 now names it; it holds raw `gh` responses, is overwritten
  freely, and is disposable — it is the mechanism by which payloads stay out of
  context. And collection does **not** read that cache by default: change
  detection depends on each run actually asking GitHub, so the cache saves
  context, not calls.
- *2026-10-08* — **A second run reuses unchanged assessments, and the bias on
  doubt is to reassess.** Snapshot schema v2 adds `rulesVersion`, per-child
  `contentHash` and `accessible`, `scope.observed` / `unobservedReason`, an
  `inventory` block, and per-requirement `reused` / `assessedAt` /
  `assessedFromSnapshot`. v1 snapshots stay readable and are not rewritten;
  lacking hashes, they force one full reassessment and the run after that is
  incremental.

  The hash deliberately **excludes `updatedAt`**. A PR merging, a check
  flipping, or a review landing changes the evidence without touching the
  issue, so an `updatedAt` comparison would miss exactly the changes a rollup
  exists to report. A requirement is reassessed when its text changed, when any
  artifact its evidence rests on changed or was added, removed, reopened, or
  lost access, when it was not previously `Evidence found` and anything upstream
  moved, when the mapping or the rules version changed, or when the dependency
  is simply unclear. A wasted assessment costs tokens; a wrongly reused one
  costs the report its credibility. `--full-refresh` reassesses everything.

  The report is always assembled complete, reused rows included and rendered
  identically to fresh ones — a run never emits only the rows that changed. A
  requirement with neither a fresh assessment nor a reusable one is an **error**
  from the assembler, not an automatic `Unable to assess`: filling a gap with a
  verdict nobody reached is the one failure this pipeline must not have.
- *2026-10-08* — **Savings are reported as measurements in the unit measured.**
  `tests/measure_run.py` prints the LLM-facing input for a full and an
  incremental run over a fixture, and reports bytes when no tokenizer is
  installed rather than dividing bytes by four. On the larger fixture (15
  children, 13 PRs, long bodies) a full run is 29,625 bytes of manifest plus
  1,855 of diff plus 51,444 of artifact text to read; the incremental run is
  29,625 + 2,793 + 0, with 77,759 bytes of raw `gh` responses staying on disk.
  `SKILL.md` went from 33,963 to 12,004 bytes, with the detail moved into
  references loaded on demand. No token or cost claim is made from these: one
  fixture is not a workload, and the whole of the incremental difference is
  artifact text that no longer has to be read — the manifest is the same size
  either way.
- *2026-10-09* — **One assessment, two outputs: a full assessment for review and
  a Jira summary draft for posting.** `rollup.py assemble` now takes both
  `--report` and `--summary`. The full assessment keeps the criterion-by-criterion
  evidence, downstream qualification, and the collection diagnostics; the summary
  is 150–250 words of prose with the outcome table, four fixed bullets, a trend
  line and at most one scope caveat. **Only the summary is ever posted.**

  They are rendered from one merge and one tally, and `assemble.cross_check`
  refuses to emit them if the outcome row is missing from either, if the counts
  do not sum to the criteria total, or if a local path reached the summary. The
  alternative — two passes over the data — is how a comment ends up claiming
  three met beside a table that says two, which destroys trust in both.

  Four mutually exclusive outcomes (`jgr/outcomes.py`) sit on top of the four
  coverage assessments: `Evidence found → met`, `Partial evidence → partial`,
  `No evidence found` and `Unable to assess → unverified`. `confirmed-unmet` is
  the only outcome the model may declare, and only with `refutingEvidence`;
  absence stays `unverified` however much of it there is. Collapsing the two
  would turn an untracked requirement into a failed one and send a reader to
  argue with a team that may have shipped the work somewhere nobody linked.

  `RULES_VERSION` was **not** bumped. The stored assessments map onto the new
  outcomes by construction, so bumping would discard every reusable assessment
  to produce identical judgements.

  Delivery confidence is deliberately not a function of the counts.
  `outcomes.confidence()` returns `Not assessed` when there is no fix version,
  when any criterion lacks downstream qualification evidence, or when anything
  is unverified — and names which applied. Nine met criteria with no release
  target is not "on track".

  Two things are now blocked in code rather than asked for in prose. `links.py`
  refuses a local path or `file://` URL in publishable text, because the
  manifest is full of cache paths and one interpolated into a comment publishes
  the shape of someone's home directory to a whole project. And
  `snapshots.promote` requires a non-blank Jira comment id, because promoting on
  intent rather than on a returned id is how a failed post advances the
  published baseline and silently destroys the next run's comparison.
- *2026-10-09* — **The Jira comment tool takes Markdown, so the default path
  converts nothing.** `addOrEditJiraIssueComment` documents `commentBody` as
  Markdown by default with `contentFormat: "markdown" | "html"`; wiki markup is
  not an input format for it. `convert` gains an `html` target as the fallback,
  emitting only the elements the Atlassian editor accepts — headings, `p`,
  `ul/li`, `table/thead/tbody`, `a`, `strong`, `em`, `code`, `hr` — and escaping
  cell text before inserting any of them. Layout wrappers (`<section
  data-type="layout-*">`) are refused by Jira outright and are never emitted.
  The `wiki` and `plain` targets stay for other doors: the REST v3 comment API
  takes ADF and nothing else.
