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
- *2026-10-10* — **`met` now has to be proved clause by clause.** Review raised
  the strongest objection available against this design: `Evidence found → met`
  let evidence that the *work exists* stand in for evidence that *every clause
  holds*, which is the one semantic error the whole skill is built to avoid.
  `requirements.md` already forbade `Evidence found` while a clause was
  undecided, and nothing enforced it — a prose rule with no teeth, which by the
  repo's own prose/code split is a coded rule in the wrong file.

  Assessments now carry a second clause list. `unresolvedClauses` is for
  clauses nobody has *decided*; `uncoveredClauses` is for clauses that are
  checkable but unsupported by anything inspected. Either one makes
  `Evidence found` a refusal. It refuses rather than downgrading to
  `Partial evidence` on purpose: the downgrade produces the right count beside
  a `coverageDetail` still written as though the criterion were established,
  which is the worse of the two errors. The two lists render separately,
  because one needs engineering or a link and the other needs a product call.

  Naming the clauses stays a judgement and stays with the model. Only the
  consequence — that an open clause is not `met` — moved into code.
- *2026-10-10* — **Reuse is invalidated for the two things the content hashes
  cannot see.** A child's `contentHash` covers its body, state and PRs, so it
  catches almost everything. Two gaps did not reach it.

  A stored `downstream: pending` is now always reassessed. Downstream artifacts
  are outside the traversal by design, so no hash computed here can ever
  contradict one, and carrying it forward republished "qualification
  outstanding" indefinitely after anyone last checked. `unknown` stays
  reusable: nobody looked then, nobody looked now, and repeating that is true.

  Declared dependencies are now stored in `scope.dependencies` with their state
  and compared between runs; a dependency closing, appearing, disappearing or
  changing readability invalidates any assessment resting on it. A baseline
  predating the field treats every dependency as changed, following the same
  rule as a missing content hash: unknown is not unchanged.
- *2026-10-10* — **A `confirmed-unmet` criterion is a finding, not a schedule
  item.** It was being rendered in the summary's Remaining bullet as "tracked
  and incomplete" — the same words as work still in flight. A reader skims
  Remaining as a list of things that will arrive, and this is a thing that will
  not. It moves to Attention needed, with the artifact that refutes it and an
  explicit "decide whether to reopen the work or revise the criterion".

  Two smaller corrections to the same bullet: an open decision now names the
  decision rather than reporting that one exists, and the trend line names its
  baseline as "the last update posted here" or "the last assessment … not
  posted here" instead of "draft snapshot", which is this tool's vocabulary and
  not a Jira reader's.
- *2026-10-10* — **"Append-only" was overclaiming, and is now stated exactly.**
  `promote` rewrites a snapshot in place and renames it, which the word
  disallowed as written. The accurate rule, now in `SKILL.md`,
  `pipeline.md` and `snapshots.md`: no run ever reads, rewrites or deletes
  another run's snapshot, and the assessment payload (`jira`, `mappings`,
  `scope`, `access`, `outcomes`, `requirements`, `inventory`) is immutable once
  written. `promote` is additive and touches only `publication`,
  `publishedAt`, `jiraCommentId` and `published`. Publication is a fact about a
  Jira comment and must never be able to edit what was judged.

  No behaviour changed here; the documentation was wrong about the code.
- *2026-10-10* — **The Jira summary carries narrative, and every claim in it
  names the rows it rests on.** The bullets were mechanical lists of criterion
  ids, and a real run against a six-issue requirement produced a summary that
  was arithmetically perfect and useless to the audience it is for: a manager
  cannot act on "4 criteria partly supported: AC1, AC3, SC2, DoD1". A shared
  tally guarantees consistent arithmetic, not correct interpretation, and the
  model is already making the interpretation — it was just not allowed to write
  it down.

  `assembly["narrative"]` (or `--narrative`) now carries one entry per claim:
  the bullet it belongs under, the sentence, the `(sourceKey, id)` rows it
  rests on, and the artifacts it links. `summary.narrative_problems` refuses
  the run when a claim cites a row that is not in this assessment, cites no row
  at all, links an artifact no cited row carries, or is filed under "Evidence
  established" while resting on an `unverified` row. The snapshot stores the
  narrative, so `rerender` reproduces the text that was approved.

  **Those checks establish traceability, not truth,** and there is a test
  asserting that a traceable-but-wrong claim still passes, so nobody later
  reads the validator as a fact checker. Judging the evidence stays in prose
  per the split in `CLAUDE.md`; only the structural half moved into code.

  Three readability rules came with it, because the same renderer has to work
  at 9 criteria and at 49: a criterion is named in at most one bullet and
  counted everywhere after, at most three explicit references appear per bullet
  with the remainder collapsed to counts grouped by owning issue, and every
  reference is qualified with its source key. A rollup spanning six Jira issues
  has six rows called `AC1`; a bare `AC1` pointed at none of them. The word
  budget is now reported (`summaryWordBudget`) rather than enforced — the
  renderer shrinks mechanical detail to fit and never truncates a claim.
- *2026-10-10* — **Supersedes the "Attention needed" entry above: a contradicted
  criterion raises a question, it does not answer one.** The previous fix moved
  `confirmed-unmet` out of Remaining, which was right, but rendered it as
  "decide whether to reopen the work or revise the criterion" — two possible
  answers, picked before anyone asked. The real case that prompted this had an
  issue proposing to reject a configuration and a criterion requiring it to
  work: both accurate, neither defective, and the open question was a product
  one. The bullet (now **Decisions needed**) states the question — does the
  criterion still describe intended behaviour — and leaves the answer to the
  people who own it. The four bullets are now `evidence-established`,
  `remaining-work`, `decisions-needed`, `next-actions`.
- *2026-10-10* — **Nested epics are traversed one level when a declared
  relation found them.** A run against a real six-issue requirement recorded a
  nested epic and stopped, and six criteria were reported with no upstream
  coverage when the work plausibly sat beneath it. Traversal now descends one
  further level through `sub-issue` and `task-list` only
  (`collect.DECLARED_RELATIONS`), with a visited set, a depth cap and
  grandchildren attributed to the nested epic.

  The rule keys on the **discovery relation**, not on nesting. A
  `timeline-cross-reference` establishes that something mentioned the epic
  once; descending through one would attach an unrelated tree of issues to this
  Jira issue's criteria, and every row they touched would be assessed against
  work nobody claimed was in scope. Everything left alone goes in
  `manifest.untraversed` as structured entries with the reason, which both
  renderings read — the full assessment names each one, the summary's scope
  caveat counts them. A limitation that existed only as free-text prose was one
  a reader could miss, and every absence claim in the run is scoped to it.

  A `403` on the sub-issue list of a readable issue is now recorded as a
  limitation rather than returning an empty child list, which used to hide a
  whole subtree behind "this epic has no children".
- *2026-10-10* — **Counts are qualified before they are compared.** Three
  related changes, all for the same failure: a number that is correct and read
  as something else.

  `render.type_breakdown` splits the four outcomes by requirement type, with no
  total column and no percentage. Eight met acceptance criteria beside zero met
  success criteria is a different situation from the reverse and both read as
  "8 of 16"; dividing across the types would produce the feature-completion
  figure this design exists to refuse.

  Downstream qualification gained an explicit three-state table with long
  labels (`metrics.DOWNSTREAM_LABELS`): *Not inspected*, *Inspected; no
  qualifying evidence found*, *Verified, with evidence*. The first two were
  being read as each other, which either overstates or understates what is
  known. Upstream coverage, downstream qualification and delivery confidence
  stay three separate answers.

  When the criteria set changes size, the summary's trend line reports the
  scope change and states that the outcome counts are not comparable across it,
  rather than printing a delta. Nine criteria becoming forty-nine rendered as
  `unverified 4→42`, which states forty-two problems, none of which anyone
  found. Like-for-like movement over the matched set stays in the full
  assessment, which has room to qualify it — and `metrics.like_for_like` now
  resolves a matched pair through `(sourceKey, id)` rather than id alone, which
  had been picking whichever `AC1` came first.
- *2026-10-10* — **An unscoped existence claim is refused in code.** "No
  upstream issue covers this" is a claim about every repository on GitHub, made
  from a walk of one epic — and after the traversal change, made from a walk
  that explicitly names what it did not cover. `assemble.unscoped_claims`
  rejects the phrasing in a `gap`, a `coverageDetail`, a note, or either
  rendered output. The honest form names the inspected set: "no upstream work
  in the traversed set is linked to …".

  This is mechanical and silently violated, which puts it in code by the
  `CLAUDE.md` split. What the evidence means stays in prose.
- *2026-10-10* — **The no-mapping procedure wrote `assembly.json` after the
  command that reads it.** `SKILL.md`'s partial path ran `assemble` against a
  file nobody had written, then sent the reader to step 6, which assembles
  again. It now writes the assembly first, assembles once, and says explicitly
  that step 6 is already done. The partial report is unchanged and still the
  point of the path: the Jira side in full, `unknown` upstream counts, every
  row `Unable to assess`, and the missing link named as the limitation.

*2026-10-10* — **A re-rendered snapshot has to be the same document.** Checking
the re-render requirement against a real snapshot showed it was not met: the
heading fell back to the Jira key, criterion references lost their links, and
the trend line reverted to "Baseline established." None of those were
reproducible from what the snapshot stored. The snapshot now also carries
`jiraSummary`, `jiraSite`, `summaryTrend` and `prose` (caveats, risks,
dependencies), and `rerender` reloads the baseline named in
`baseline.generatedAt` to rebuild the trend table. `--title` and `--site`
became overrides rather than required input. The Jira summary now reproduces
byte-for-byte; the full assessment can still differ by one bullet, because the
per-field `diff` detail behind "Mapping changed" is not stored and a re-render
cannot honestly reconstruct it.

*2026-10-10* — **Every rendering opens with one overall assessment.** A reader
had to assemble the position from the rows and the four bullets. All three
renderings now open with a single paragraph of 60–100 words: what the collected
evidence establishes, which required capabilities are explicitly unmet, which
are unverified or carry conflicting evidence, and what resolves the gaps.

The paragraph is the model's, because every one of those is judgement. What is
coded is the pinning and the scope. `assembly["overall"]` carries the text plus
three ref lists — `establishes`, `unmet`, `unverified` — and `assemble` refuses
the run unless each cited row exists and is in the bucket it is filed under: a
confirmed absence has to be a row something inspected contradicts, never a row
nothing covers. It also refuses a criterion id in the prose (the paragraph
groups into capability areas; enumerating is the bullets' and the table's job),
a percentage, a readiness or date claim, and the same unscoped existence claim
the rest of the prose is held to. The string is built once and asserted into
each of the three outputs, so the position cannot drift between them.

With no paragraph supplied, all three fall back to one built from the tally,
whose last sentence says nobody wrote a position. It is never wrong and never
useful, which is the right pressure.

The draft budget moved with it, 150–250 → 210–350 words. A required paragraph in
front of the bullets should move the range, not squeeze them.

*2026-10-10* — **The investigation finishes before the finding is written.**
Review found the failure the clause work left behind: an assessment could
identify exactly which question was open, name the file that answers it, have
access to that file, not open it, and report the leftover uncertainty as a gap
in the product. The reader is then told engineering owes them something when
what was missing was a read. The shape of the case that raised it is the one
in `examples/ac-coverage-fixture.md`, case 8: a criterion requires a component
to fail closed; the report cites the PR whose validator refuses the unsafe
configuration for members of a named list; nobody opens the list to see whether
the component is in it, and the criterion is marked Partial for that reason.
Two separate mistakes, and the fixture pins both — the unread list, and the
assumption that a configuration-time restriction says anything about runtime.

Three changes, each on the side of the prose/code split it belongs on.

`rollup.py source` is the bounded read: one named file, at one revision, within
a budget of twelve distinct reads per run, deduplicated through the cache and
ledgered in `cache/<KEY>/followups.json`. `--revision` is required and has no
default, which is the code-level form of "do not let today's `main` prove
something about a commit from September" — the collector now records each
merged PR's `mergeCommit` so there is always one to pass. It never raises and
never returns an empty body for a failed read: every call is `inspected: true`
with text or `inspected: false` with a `limitation` and a `reason`. There is no
search verb and no directory walk, because the difference between a follow-up
and a repository audit is that a follow-up only follows references the evidence
already produced.

`uncoveredClauses` entries became objects carrying a `kind`. Three kinds,
because "not covered" was being written for three findings that go to three
different people: `implementation-gap` (something inspected shows the behaviour
missing), `evidence-gap` (what was inspected does not settle it), and
`inspection-limitation` (the thing that would settle it could not be read). Two
of the three are enforced. An `implementation-gap` citing nothing is refused —
an unread file is not proof of missing functionality and an absent test is not
proof of an absent implementation, which is the `confirmed-unmet` rule at
clause scope. And an `evidence-gap` naming nothing `inspected` is refused,
which is the lever that makes the whole thing work: "what I read does not
establish this" is a claim about a read, so with nothing named the honest kind
is `inspection-limitation`, and having to write *that* down is what makes
opening the file the cheaper option. Every clause also owes a `nextAction`.

The reporting then has to carry the distinction. The full assessment groups
open clauses by kind with the basis, the revision and the next action on each;
the scope section names every source file read with its revision and states in
its own words when an investigation is incomplete. The summary gets the counts
and one line about unfinished inspection — not the clause list, which is the
full assessment's job — and `cross_check` refuses a run where the two disagree
about either.

What did **not** change: the four coverage assessments, the four outcomes, and
`Partial` staying conservative. A merged PR covering one clause of three is
still `Partial`; the reason the other two are open is reported beside it rather
than folded into the verdict. And the judgement stayed in prose — which clauses
a criterion has, which source would settle one, and what a source establishes
when read are all still the model's. `requirements.md` gains the generalized
form of the trap that produced the case: a configuration-time restriction
establishes which configurations are rejected and nothing about runtime, so
membership in a list is one clause and the behaviour when the thing runs is
another.

`RULES_VERSION` moved to `2026-10-10`. Stored assessments were made under rules
that let an unread source become a gap, so reusing them would carry exactly the
judgements this change exists to revisit.

*2026-10-11* — **An evidence citation is a ref; the pipeline supplies the rest.**
A 49-criterion run produced 64 citations over 13 distinct refs, each carrying
`kind`, `state` and `at` typed out by hand — and four of the thirteen `at`
values were the manifest's merge times rounded to the minute. Harmless in that
report, and not harmless in general: `at` is what the trend section compares
against the baseline to separate implementation progress from newly discovered
evidence, so a rounded copy can flip which of those two claims a reader is
given, with nothing downstream able to notice.

This is the `CLAUDE.md` split applied to a field at a time. *Which* artifact is
evidence for a criterion is a judgement and stays in prose. What that artifact
is — a PR or an issue, merged or open, and when it landed — is a mechanical
fact the collector already fetched, so `jgr/evidence.py` joins it: from the
manifest for an `owner/repo#123` ref, and from this run's source-read ledger
for an `owner/repo@revision:path` one. Anything outside the traversal, a CI job
name being the usual case, declares its own `kind` and is left as written.

Two consequences were settled rather than left open. A ref that resolves to
nothing is **refused by name** instead of being accepted with whatever fields
came with it — it is a typo or it is work nobody traversed, and both need a
person. And a supplied field that disagrees with the collected one is refused
rather than merged in either direction: picking a winner hides the case where
the manifest is not the document the assessment thought it was reading.
Declaring `kind: pr` on an untraversed ref is refused too, or the escape hatch
for a CI check would also be the hole in the check.

`createdAt` was added to the collected fields so `at` can mean *when the
artifact became the evidence it is* — merged, else closed, else opened.
`updatedAt` was the only alternative already on hand and is the wrong one: a
comment on an open PR would date the evidence to this week and report a reply
as work that landed.

`rerender` does not re-join. The stored items were resolved against the
manifest of the run that made them, and the manifest rebuilt from a snapshot is
thinner, so re-deriving would re-judge a reviewed document from a poorer record
of the world.

`RULES_VERSION` did **not** move. No verdict changes, and a stored rounded
timestamp cannot reach a trend classification: the classifier skips rows whose
assessment is unchanged, and a row whose assessment changed was reassessed
fresh this run and therefore carries joined values.

*2026-10-11* — **The summary ceiling stays at 350 words, and no mechanical
lever is pretending to meet it.** A 49-criterion run produced a 661-word draft
— 89% over — and the overrun reached the approval step as
`summaryWordBudget.within: false` in a file nobody reads.

Three options were on the table for what the summary does at scale: collapse
the bullets' enumeration past some criteria count, scale the ceiling with
scope, or keep the ceiling fixed and make the rewrite a step. The first was
the preference going in, because it reuses the collapse rule the coverage
table already applies above 12 requirements. Measurement killed it. On a
reconstruction of that run, the entire range between three criterion
references per bullet and none is **four words** — 724 to 720 — and the
one-reference version is the *longest* of the three at 729, because "and 9
more — 4 on RHOAIENG-2204, 3 on RHOAIENG-2205" costs more than the two names
it replaces. 563 of the 724 words were prose the model wrote: 478 in the four
bullets, 85 in the overall assessment. There is no collapse rule that recovers
311 words from 161 words of renderer-controlled text.

So the three readability rules in `summary.py` are readability rules and were
never a compression lever, and the `for cap in (3, 2, 1)` loop that re-rendered
the whole document hoping one of them would fit is gone. The cap is applied
once. What changed instead:

- `summaryWordBudget.condition` is `within-budget`, `under-floor` or
  `over-ceiling`, with `authored` splitting the count into the model's prose
  and the lines the renderer owns — because "the draft is long" and "what you
  wrote is long" lead to different next moves.
- `over-ceiling` prints a notice on **stderr**, since the draft is shown for
  approval by somebody reading the summary and not necessarily `result.json`.
  The notice derives the room the bullets actually have left in *this* draft
  (ceiling, less the overall assessment, less the fixed lines) rather than
  quoting a constant, because the fixed lines grow with the run.
- `SKILL.md` makes it a step: rewrite and re-assemble **before** showing the
  draft, and do not bring an `over-ceiling` draft to the approval step at all.
  At 49 criteria the four bullets have about a hundred words between them, so
  a bullet gives the shape of the finding — how many, whose, of what kind —
  and sends the reader to the full assessment.

Rejected along with option 1: scaling the ceiling with scope. The posted
comment would get longer exactly as the reader's patience gets shorter, and
the full assessment already exists for the detail. Also rejected: refusing to
render an over-budget draft. The run should finish and the draft should exist;
the defect was that the overrun was silent, not that the file was written. And
unchanged: the assembler never truncates a claim, never shortens the overall
assessment and never drops a bullet. Deciding which sentences carry their
weight is judgement, and it stays with the model.

*2026-10-11* — **An unanswered question is reported against the budget there
was to answer it with, and naming the file is counted rather than compelled.**
The same 49-criterion run produced 22 `evidence-gap` clauses and spent 4 of
its 12 follow-up reads. It did not stop because the budget ran out. Of the 22
next actions, 5 named a file `source` could open and were never opened, 16
named a subsystem — which `source` cannot take, by design — and 1 asked a
person to decide. The run wrote itself a to-do list it could not act on and
reported the leftover uncertainty as findings about the product. In a table
cell "nobody checked this" and "this behaviour is missing" are the same cell.

What went in, and what deliberately did not:

- **The arithmetic, in code.** `clauses.follow_up_standing` reports open
  evidence gaps, how many name a target, and how much read budget is unspent;
  `assemble` prints it on stderr when reads were left over, both long
  documents state the same sentence, and `cross_check` holds them to it. The
  budget now reaches the assembly at all — `_source_reads` was taking
  `ledger.reads` and discarding `ledger.remaining` — and is stored on the
  snapshot so a re-render states what the reviewer saw.
- **`nextRead` as an optional, counted field.** `{repo, path, revision}` — the
  three arguments `source` takes. The assembler refuses a partial one, and one
  naming a file the clause already inspected, but **never requires one**. The
  issue proposed making it mandatory for any clause whose next action is a
  read. Rejected: that condition is a model-declared flag, the same escape
  hatch shape the evidence join had closed the day before, and the
  unconditional version — a regex refusing a `nextAction` that names a path
  the run never opened — has an incentive pointing the wrong way. Its cheapest
  escape is a vaguer next action, and an unreadable instruction is worse for
  the reader than the unread file. Counting makes specificity something the
  report gives credit for: "22 open, 0 naming a target" is as visible as "5
  open, 5 naming one, 8 unspent", and the first is its own finding.
- **Resolve the subsystem to a path, in prose.** The issue routed the 16
  concept-named gaps to `inspection-limitation`. Amended: a PR's changed-file
  list is in scope, the manifest's sample is capped while the cache holds the
  whole list, and `excerpt --kind pr-files --field files` is the documented
  read of it. So a subsystem is usually one lookup from a path, and
  reclassifying those as "could not be read" swaps one misreport for another —
  a worse one, because `_clause_agreement` then makes the Jira summary declare
  the investigation incomplete. Only what genuinely does not resolve within
  the traversed set is a limitation. A clause asking a person to decide goes
  to `unresolvedClauses`, which already exists for exactly that; no new
  category was needed.

Held, not decided: the 12-read budget. Enforcement makes it binding by
construction at this scale, so the question is real — but `budget-spent` is
now a reported condition, and the next large run will say whether 12 was the
constraint instead of anyone guessing.
