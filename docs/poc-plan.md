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
- Epic discovery from links a human already placed on the Jira issue.
- Traversal of child issues via native sub-issues, epic-body task lists, and
  timeline cross-references.
- Child issues in repositories other than the epic's.
- PR resolution per child, including merge state and target branch.
- Acceptance-criteria coverage: criteria quoted from the named issue and its
  child requirements, mapped to upstream evidence, with a per-criterion coverage
  assessment and a separate downstream-qualification statement.
- CI and changed-file evidence on PRs, used only to support a named behavior.
- Posting the approved draft as a comment on that same Jira issue.
- Updating a prior rollup comment in place instead of appending.

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
  qualification runs. Whether it should is open question 8.

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

4. **Wiki markup or ADF?** Depends on the Jira site's editor. Affects whether the
   table in `references/rollup-format.md` renders or shows as literal pipes.
   One test comment on a scratch issue answers this.

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

## Milestones

| # | Milestone | Done when |
| --- | --- | --- |
| 1 | Link conventions agreed | A real Jira issue carries an epic link in the documented form |
| 2 | Traversal validated | Skill enumerates the correct children, cross-repo included, verified by hand |
| 3 | Criteria extraction validated | Criteria quoted verbatim from three real requirements, with sources correct and nothing invented |
| 4 | Coverage assessments defensible | On three real requirements, an EM agrees with every assessment, or disagrees only about `Partial` vs `Evidence found` |
| 5 | Draft quality | Three consecutive rollups an EM would post with no edits |
| 6 | Round trip | An approved draft posts cleanly and renders correctly |
| 7 | Idempotence | A second run updates the prior comment rather than duplicating |

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
- No criterion appears in a rollup that is not in the Jira, in any form.
- Every absence claim in a shipped rollup is scoped to the sources inspected.
- Total time per rollup, including review, is under what writing it by hand costs.

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
