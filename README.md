# jira-github-rollup

A Claude Code skill that drafts **upstream development rollups** for requirements
that already exist in Jira.

## The problem

Downstream requirements live in Jira. The actual development happens upstream in
GitHub, usually spread across several repositories. Keeping the Jira issue honest
about upstream state is manual, tedious, and therefore stale most of the time.

The common "fix" — mirroring every GitHub issue into Jira — creates two systems of
record and twice the bookkeeping. This skill deliberately does not do that.

## The approach

```
Jira requirement  ──(human adds link)──▶  GitHub epic
                                              │
                                              ├── child issue ──▶ PR(s)
                                              ├── child issue ──▶ PR(s)   (any repo)
                                              └── child issue ──▶ PR(s)
                                              │
       rollup comment  ◀──(skill drafts)──────┘
```

1. **A human** creates or identifies the GitHub epic for a requirement and links
   it from the Jira issue. This step stays manual — it is a judgment call, and
   getting it wrong poisons every rollup that follows. A requirement that spans
   two upstream efforts gets two links, and both are rolled up.
2. **The skill** reads those links, follows child issues and their pull requests
   across repositories, and drafts a concise status rollup. With no link to
   read, it drafts the Jira side and names what is missing.
3. **A human** approves the draft before it is posted as a comment on that same
   Jira issue.

### Requirement coverage

The rollup also answers the question progress counts cannot: *is the requirement
actually covered?* It quotes each statement the Jira commits to — acceptance
criteria, success criteria, and definition-of-done items, including those
inherited from child requirements — and reports, per statement, the upstream
evidence for it, how far that evidence got (planned, in progress, in review,
merged, tested), and one of four assessments:

| Assessment | Means |
| --- | --- |
| Evidence found | The evidence supports the requirement, and the row says what it establishes |
| Partial evidence | Part of it is covered; the rest is named |
| No evidence found | The sources inspected do not establish coverage |
| Unable to assess | Access failure, truncated results, or nothing checkable in the statement |

Whether downstream integration or qualification is still required is stated
separately, because it can be outstanding even when upstream coverage is
complete. A merged PR is landed implementation, not a shipped requirement.

Four distinctions do most of the work here:

- **"No evidence found" is never "not implemented."** It is a claim about the
  sources inspected, and it is written scoped to them.
- **A matching issue title is a candidate mapping, not coverage.** The issue has
  to say so. When a requirement has no mapping at all, the skill flags it for
  owner review rather than searching the org for something plausible.
- **The three kinds of requirement stay apart.** `AC`, `SC`, and `DoD` are
  numbered and counted separately. A total labelled "acceptance criteria" that
  includes definition-of-done items misstates what was agreed and sends the
  reader to the wrong person.
- **One undecided parameter does not void a whole criterion.** "Retained for the
  agreed window (TBD)" alongside two checkable clauses gets the two clauses
  assessed and the open decision named, with its owner.

See [`examples/sample-rollup.md`](examples/sample-rollup.md) for all four
assessments in context — and, below them, the same requirement rolled up with no
epic linked. [`examples/ac-coverage-fixture.md`](examples/ac-coverage-fixture.md)
holds the cases the rules are desk-checked against.

### What it will not do

- **It does not create Jira issues.** No mirroring, no sub-tasks, no linked
  issues. One Jira issue in, one comment out.
- **It does not guess the epic.** A title-matched guess produces a rollup that is
  confidently wrong. With no link on the Jira it drafts the half it can see — the
  scope and the requirements table — marks upstream coverage unassessable, and
  asks for the link.
- **It does not read a missing link as missing work.** No link means nothing
  upstream was inspected. The draft never says "not started".
- **It does not post without approval.** A Jira comment is visible to the whole
  project; that needs a human yes, on that specific draft. Asking for a draft is
  not asking for a post.
- **It does not invent criteria, mappings, or test results.** Requirements are
  quoted from the Jira or reported missing. Retrieval stays inside the linked
  epics, their children, and dependencies those artifacts reference directly.

## Usage

From a Claude Code session with this repo's `.claude/` directory in scope:

```
> roll up the upstream status for RHOAIENG-1234
> are the acceptance criteria on RHOAIENG-1234 covered upstream?
```

The skill will fetch the issue and its requirements, find the linked epics,
traverse them, map each requirement to the evidence it found, and show you a
draft. Nothing is written to Jira until you approve that draft.

## Requirements

| Dependency | Used for | Notes |
| --- | --- | --- |
| `gh` CLI, authenticated | Reading epics, issues, PRs | Read-only. `repo` + `read:org` scope is enough. |
| Atlassian MCP server | Reading the Jira issue, posting the comment | Must reach the relevant Jira site. |

Both need read access to every repository that hosts child issues — including
repos the epic itself does not live in. Where access is missing, the affected
requirements come back `Unable to assess` and the gap is named in the rollup
rather than quietly reducing coverage.

## Layout

```
.claude/skills/jira-github-rollup/
  SKILL.md                      # procedure, traversal, constraints
  references/rollup-format.md   # output contract and Jira markup notes
examples/
  jira-link-section.md          # how to link an epic, and how to write criteria
  sample-rollup.md              # an illustrative generated rollup
  ac-coverage-fixture.md        # coverage cases the rules are desk-checked against
docs/
  poc-plan.md                   # scope, open questions, success criteria
CLAUDE.md                       # repo conventions for Claude Code
```

## Status

Proof of concept. See [docs/poc-plan.md](docs/poc-plan.md) for current scope,
known gaps, and what would need to be true to use this on real requirements.
