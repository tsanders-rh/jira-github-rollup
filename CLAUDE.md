# CLAUDE.md

Conventions for working in this repository.

## What this repo is

A single Claude Code skill, `jira-github-rollup`: instructions in `SKILL.md` and
`references/`, the Python that does the deterministic half in
`.claude/skills/jira-github-rollup/scripts/`, tests in `tests/`, and
illustrative `examples/`. There is no build and nothing to install.

The deliverable is still mostly prose that an agent follows correctly, so the
editing bar is different from a normal repo: **ambiguity in these files is a
bug.** A sentence that an agent can read two ways will eventually be read the
wrong way, against someone's real Jira issue.

## The split between prose and code

A rule belongs in code when it is mechanical and its violation is silent:
counting, percentages, deduplication, content hashing, section order, the
snapshot store. A rule stays in prose when it is a judgement: what text is a
requirement, what a piece of evidence establishes, what to say about it.

Two consequences:

- **Do not restate a coded rule as an instruction to follow by hand.** Two
  copies of a counting rule drift, and the prose copy is the one that gets
  applied wrong. Reference files describe what the code does so the output can
  be interpreted and the code can be changed; they are not a manual procedure.
- **Do not move a judgement into code.** A script that decides whether a merged
  PR covers a criterion is a script that will be confidently wrong in a table
  cell, which is the failure this whole design exists to avoid.

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
5. **The only things written outside Jira are a snapshot and a cache**, both
   under `~/.jira-github-rollup/` (or `$JGR_HOME`). Snapshots are append-only: a
   run writes a new dated file and never overwrites or deletes an existing one,
   because editing the Jira comment in place must not destroy the comparison
   baseline. The cache under `cache/<JIRA-KEY>/` holds raw `gh` responses, is
   overwritten freely, and is disposable — it exists so that raw payloads stay
   out of the conversation. Nothing else on disk is touched.
6. **The trend report is unweighted counts, never a forecast.** No partial
   credit, no velocity, no burn-down, no projected dates. An unobservable count
   is `unknown`; it is never zero.

If a change would weaken any of these, say so plainly rather than making it.

## Editing the skill

`SKILL.md` is loaded into context when the skill fires, so it pays rent on every
invocation. It is the orchestration guide: the invariants, the numbered
procedure, the commands, and a pointer to the reference that covers each step.
Everything else is read on demand:

| Goes in | What |
| --- | --- |
| `references/pipeline.md` | Command options, storage layout, what to do when something fails |
| `references/requirements.md` | Extraction and assessment — the rules the model applies |
| `references/rollup-format.md` | The output contract, and converting it for Jira |
| `references/snapshots.md` | The store, the schema, matching, and the metric definitions |

- Frontmatter `description` is what the model matches against. It must name the
  trigger phrases a user would actually type, not describe the implementation.
- Prefer a table or a numbered procedure over a paragraph.
- Every command in the skill should be runnable as written. Verify a changed
  flag against the installed `gh`, or against `rollup.py --help`.
- When you add a rule, decide where it belongs by the split above. If it stays
  in prose and an agent could plausibly violate it, add it to the failure-modes
  list too; if it goes in code, add a test.
- Shortening the instructions is worth doing. Deleting a safeguard to do it is
  not — move it to a reference instead.

## Scripts and tests

Python 3.9+, standard library only. No new dependency and no new credential:
`gh` is already authenticated, and nothing in `scripts/` can reach Jira — Jira
is MCP-only, so the model passes its fields in as structured input.

- Raw API responses go to the cache, never into the conversation. A script that
  prints a full body, timeline or CI log to stdout has defeated the point;
  `excerpt` is the only deliberate read, and it always reports its own
  truncation.
- Add a test for any behaviour change. `tests/fakegh.py` stands in for `gh` via
  `GH_BIN`, driven by a JSON world file, so command construction and exit codes
  are exercised with only the network faked.

```bash
python3 -m unittest discover -s tests
python3 tests/measure_run.py      # LLM-facing input size, full run vs incremental
```

Report sizes in whatever unit was actually measured. Do not convert bytes to
tokens by dividing, and do not state a cost saving without measuring one.

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
