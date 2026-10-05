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

## Milestones

| # | Milestone | Done when |
| --- | --- | --- |
| 1 | Link conventions agreed | A real Jira issue carries an epic link in the documented form |
| 2 | Traversal validated | Skill enumerates the correct children, cross-repo included, verified by hand |
| 3 | Draft quality | Three consecutive rollups an EM would post with no edits |
| 4 | Round trip | An approved draft posts cleanly and renders correctly |
| 5 | Idempotence | A second run updates the prior comment rather than duplicating |

Milestone 2 is the real gate. If traversal is unreliable, nothing downstream
matters — and questions 1 and 2 above are answerable in an afternoon against
three real epics.

## Success criteria

The PoC succeeds if, across five real requirements:

- Epic and child discovery is correct on at least four, with every miss traceable
  to a missing upstream link rather than a traversal bug.
- At least three rollups are postable with no edits.
- No rollup overstates progress. **A single "done" that was not done fails the
  PoC** — an inflated status update is worse than no status update, because it
  stops people from asking.
- Total time per rollup, including review, is under what writing it by hand costs.

## Known risks

- **Garbage in.** Rollup quality is bounded by epic hygiene upstream. The skill
  cannot report on children nobody linked. This may turn into a case for
  improving epic hygiene rather than a case against the skill.
- **False confidence.** A well-formatted rollup reads as authoritative. The
  marker line, timestamp, and source-epic line exist so a reader can judge
  staleness and check the source — keep them.
- **Rate limits.** Deep traversal across many repos makes a lot of API calls.
  Not a concern at single-issue scale; would be at bulk scale.
- **Scope creep toward mirroring.** The first time someone asks "can it just
  create the Jira sub-tasks too," the answer is no, and the reason is recorded
  here and in `CLAUDE.md`.

## Decisions

Record decisions that relax or clarify a constraint here, with the date and the
reasoning.

- *2026-10-05* — Initial scope. No Jira issue creation; epic linking stays manual.
