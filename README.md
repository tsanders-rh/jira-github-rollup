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
   getting it wrong poisons every rollup that follows.
2. **The skill** reads that link, follows child issues and their pull requests
   across repositories, and drafts a concise status rollup.
3. **A human** approves the draft before it is posted as a comment on that same
   Jira issue.

### What it will not do

- **It does not create Jira issues.** No mirroring, no sub-tasks, no linked
  issues. One Jira issue in, one comment out.
- **It does not guess the epic.** No link on the Jira means it stops and asks.
  A title-matched guess produces a rollup that is confidently wrong.
- **It does not post without approval.** A Jira comment is visible to the whole
  project; that needs a human yes.

## Usage

From a Claude Code session with this repo's `.claude/` directory in scope:

```
> roll up the upstream status for RHOAIENG-1234
```

The skill will fetch the issue, find the linked epic, traverse it, and show you a
draft. Nothing is written to Jira until you approve it.

## Requirements

| Dependency | Used for | Notes |
| --- | --- | --- |
| `gh` CLI, authenticated | Reading epics, issues, PRs | Read-only. `repo` + `read:org` scope is enough. |
| Atlassian MCP server | Reading the Jira issue, posting the comment | Must reach the relevant Jira site. |

Both need read access to every repository that hosts child issues — including
repos the epic itself does not live in.

## Layout

```
.claude/skills/jira-github-rollup/
  SKILL.md                      # procedure, traversal, constraints
  references/rollup-format.md   # output contract and Jira markup notes
examples/
  jira-link-section.md          # how to link an epic from a Jira issue
  sample-rollup.md              # an illustrative generated rollup
docs/
  poc-plan.md                   # scope, open questions, success criteria
CLAUDE.md                       # repo conventions for Claude Code
```

## Status

Proof of concept. See [docs/poc-plan.md](docs/poc-plan.md) for current scope,
known gaps, and what would need to be true to use this on real requirements.
