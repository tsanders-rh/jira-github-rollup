# CLAUDE.md

Conventions for working in this repository.

## What this repo is

A single Claude Code skill, `jira-github-rollup`, plus its reference material and
examples. There is no application code, no build, and no test suite. The
deliverable is prose that an agent follows correctly.

That makes the editing bar different from a normal repo: **ambiguity in these
files is a bug.** A sentence that an agent can read two ways will eventually be
read the wrong way, against someone's real Jira issue.

## Hard constraints

These are the reason the skill exists in this shape. Do not relax them without an
explicit decision recorded in `docs/poc-plan.md`.

1. **The skill never creates Jira issues.** Not mirrors, not sub-tasks, not linked
   issues. The only permitted Jira write is a comment on the one issue the user
   named.
2. **The skill never posts to Jira without explicit approval of the draft.**
   Approval of a previous draft does not carry forward.
3. **The skill never guesses which GitHub epic corresponds to a Jira issue.**
   The human-created link is the only acceptable source. No link means a partial
   draft — the Jira side reported in full, upstream coverage marked unassessable,
   and the needed link named. It never means a title search, and it never means
   reporting the work as unstarted.
4. **GitHub access is read-only.** No issue creation, no comments, no edits.
5. **The only thing written outside Jira is a snapshot**, under
   `~/.jira-github-rollup/snapshots/<JIRA-KEY>/`. Snapshots are append-only: a
   run writes a new dated file and never overwrites or deletes an existing one,
   because editing the Jira comment in place must not destroy the comparison
   baseline. Nothing else on disk is touched.
6. **The trend report is unweighted counts, never a forecast.** No partial
   credit, no velocity, no burn-down, no projected dates. An unobservable count
   is `unknown`; it is never zero.

If a change would weaken any of these, say so plainly rather than making it.

## Editing the skill

`.claude/skills/jira-github-rollup/SKILL.md` is loaded into context when the skill
fires, so it pays rent on every invocation. Keep it procedural and tight. Detail
that is only needed at output time belongs in `references/rollup-format.md`;
the snapshot store, its schema, and the metric definitions belong in
`references/snapshots.md`. Both are read on demand.

- Frontmatter `description` is what the model matches against. It must name the
  trigger phrases a user would actually type, not describe the implementation.
- Prefer a table or a numbered procedure over a paragraph.
- Every `gh` command in the skill should be runnable as written. If you change a
  flag, verify it against the installed `gh` version rather than assuming.
- When you add a rule, add it to the failure-modes list too if an agent could
  plausibly violate it.

## Examples

`examples/` files are illustrative, not real. Keep them that way:

- Use placeholder orgs and repos (`example-org/…`) and the `RHOAIENG-1234` style
  for Jira keys.
- Do not paste real issue titles, real PR links, or anything from a private repo.
- Keep them consistent with each other — `sample-rollup.md` should look like what
  the skill would actually produce from `jira-link-section.md`.

## Commits

Conventional-ish and specific about what changed in the behavior, not just which
file moved:

```
skill: stop traversal at one level of nested epics
docs: record decision on cross-repo child resolution
```

Do not commit or push unless asked.
