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

### Trends across runs

Each run saves a dated snapshot of what it found, and the next run reports what
moved:

> Requirements with evidence found: 3/7 (43%), previously 1/6 (17%), +26 pp. One
> requirement gained evidence from a PR merged after the last snapshot; one moved
> because read access was restored to a repository, and its PR merged in August.
> Downstream qualification: 0 confirmed, 0 pending, 7 unknown.

Three unweighted ratios — child issues completed, requirements with evidence
found, requirements confirmed downstream — plus the counts behind them and a list
of what changed. The constraints are what make it worth reading:

- **Nothing is weighted or extrapolated.** `Partial evidence` gets no fractional
  credit, and there is no velocity, burn-down, or projected date. Two counts
  support none of that, and the section is built so nobody can read one out.
- **Progress and discovery are different news.** Restored access or a
  newly-added link can move four requirements in a month with no code written.
  Evidence dated before the last snapshot is reported as newly visible, not newly
  done.
- **Added scope is not regression.** When the denominator grows, the percentage
  falls with nothing having gone backwards — so the like-for-like figure over
  unchanged requirements is given alongside it.
- **Unassessable requirements stay in the denominator**, and children closed as
  *not planned* stay in scope and are named. Losing access or dropping scope must
  never render as an improvement.
- **Requirements are matched on source, type, and verbatim text**, never on ID.
  Inserting one criterion renumbers every criterion below it; an ID-based diff
  would report that as a wall of changes that never happened.
- **A first run says `Baseline established — no prior snapshot available`.** It
  does not reconstruct history from the Jira, and a previous rollup comment is
  prose, not a baseline.

Snapshots are JSON, one file per run, under
`~/.jira-github-rollup/snapshots/<JIRA-KEY>/`. They are append-only: posting a
rollup usually means editing the previous comment in place, so the baseline
cannot live in the comment. Draft runs save a snapshot too, marked as drafts,
and write nothing to Jira.
[`examples/sample-rollup-rerun.md`](examples/sample-rollup-rerun.md) shows a
second run end to end, including the file it wrote;
[`examples/trend-fixture.md`](examples/trend-fixture.md) holds the seven runs the
rules are desk-checked against.

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
- **It does not estimate effort or predict a date.** The trend section reports
  movement between two observations. It is not a burn-down and will not be
  turned into one.
- **It does not reuse a stale mapping.** A snapshot remembers which epic was
  linked last time; if that link is gone from the Jira, the skill reports what
  used to be mapped and declines to traverse it.

## Usage

From a Claude Code session with this repo's `.claude/` directory in scope:

```
> roll up the upstream status for RHOAIENG-1234
> are the acceptance criteria on RHOAIENG-1234 covered upstream?
```

The skill will fetch the issue and its requirements, find the linked epics,
traverse them, map each requirement to the evidence it found, and show you a
draft. Nothing is written to Jira until you approve that draft.

### How a run is split

The deterministic half runs as code, so that raw API responses never enter the
model's context and the counting rules cannot drift:

```
scripts collect and cache evidence  ─▶  scripts compute changes and metrics
                                             │
          scripts assemble the report  ◀─────┴──▶  the model assesses
          and write the snapshot                   affected requirements
```

What the model does is read the Jira, quote the requirements verbatim, judge
what the evidence establishes, and write the prose. What the scripts do is
traverse, cache, hash, diff, count, render, and store. Raw `gh` output goes to a
local cache; the model gets a compact manifest of identifiers, states,
timestamps, hashes, access failures and cache paths, and reads an artifact's
actual text only by asking for it, with any truncation reported back to it.

A second run on the same issue re-collects everything, compares content hashes
against the last snapshot, and asks for a fresh judgement only on requirements
whose evidence could have changed — but still assembles the **complete** current
report, reused rows included. `--full-refresh` reassesses everything.

## Requirements

| Dependency | Used for | Notes |
| --- | --- | --- |
| `gh` CLI, authenticated | Reading epics, issues, PRs | Read-only. `repo` + `read:org` scope is enough. |
| Atlassian MCP server | Reading the Jira issue, posting the comment | Must reach the relevant Jira site. |
| Python 3.9+ | The collection, diff, render and snapshot scripts | Standard library only; no packages to install, no new credential. |

Both need read access to every repository that hosts child issues — including
repos the epic itself does not live in. Where access is missing, the affected
requirements come back `Unable to assess` and the gap is named in the rollup
rather than quietly reducing coverage.

## Layout

```
.claude/skills/jira-github-rollup/
  SKILL.md                      # the procedure, and the invariants
  references/pipeline.md        # commands, storage, recovery
  references/requirements.md    # extraction and assessment — the model's half
  references/rollup-format.md   # output contract, and converting it for Jira
  references/snapshots.md       # snapshot store, schema, and trend metrics
  scripts/rollup.py             # one CLI: refs, collect, diff, assemble, excerpt, …
  scripts/jgr/                  # collection, caching, diff, metrics, render, snapshots
examples/
  jira-link-section.md          # how to link an epic, and how to write criteria
  sample-rollup.md              # an illustrative generated rollup, first run
  sample-rollup-rerun.md        # the same issue four weeks later, with the trend
  ac-coverage-fixture.md        # coverage cases the rules are desk-checked against
  trend-fixture.md              # seven runs the trend rules are desk-checked against
tests/
  test_rollup.py                # behaviour tests over a faked `gh`
  fakegh.py                     # a `gh` stand-in driven by a JSON world file
  measure_run.py                # LLM-facing input size, full run vs incremental
docs/
  poc-plan.md                   # scope, open questions, success criteria
CLAUDE.md                       # repo conventions for Claude Code
```

```bash
python3 -m unittest discover -s tests
```

Outside the repo, under `~/.jira-github-rollup/` (or `$JGR_HOME`): the
append-only snapshot store, and a cache of raw `gh` responses that may be
deleted at any time. Snapshots contain verbatim Jira text, including criteria
from private issues; both are local, unencrypted, and never transmitted
anywhere.

## Status

Proof of concept. See [docs/poc-plan.md](docs/poc-plan.md) for current scope,
known gaps, and what would need to be true to use this on real requirements.
