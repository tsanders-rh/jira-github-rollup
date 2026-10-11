# jira-github-rollup

A Claude Code skill that drafts evidence-backed **upstream development rollups**
for requirements that already exist in Jira.

## Purpose

Downstream requirements live in Jira. The development happens upstream in
GitHub, usually across several repositories, so the Jira issue goes stale.
Mirroring every GitHub issue into Jira fixes that by creating two systems of
record; this skill deliberately does not.

Instead a human links the GitHub epic from the Jira issue. The skill follows
that link, reads the child issues and their pull requests, and drafts a rollup
in which every claim is tied to an artifact it inspected. Nothing reaches Jira
without approval.

## Outputs

One assessment, rendered three ways.

| Output | Audience | Contents |
| --- | --- | --- |
| Full Markdown assessment (`--report`) | You, in the session | Criterion by criterion: the evidence, what it establishes, the gaps, the collection limitations, the trend |
| Jira summary (`--summary`) | The project, on the issue | 210–350 words; posted only after you approve that specific text |
| Standalone HTML report (`--html`) | Anyone you forward the file to | The same detailed assessment, with search, outcome and type filters, and expandable per-criterion evidence |

All three come from one merge and one tally. Before writing anything, the
assembler checks that counts agree across renderings, that per-type rows sum to
the totals, that numbers in prose match the table, and that no local path is
about to be published. That is a check on counts, not on judgement — three
renderings can agree exactly and still rest on an assessment that read the
evidence wrong.

## Prerequisites

| Dependency | Used for |
| --- | --- |
| `gh` CLI, authenticated | Reading epics, issues and PRs. Read-only; `repo` + `read:org` is enough |
| Atlassian MCP server | Reading the Jira issue and posting the approved comment |
| Python 3.9+ | Collection, diff, rendering, snapshots. Standard library only |

Nothing to install and no build step. The `gh` account needs read access to
every repository hosting a child issue, not only the one the epic lives in — an
unreadable repo is reported as a limitation on the criteria it would have
covered, never as absent work.

**And one thing on the Jira issue.** A human records which GitHub epic
corresponds to the requirement, as an `Upstream Development` description
section or a web link labelled `Upstream epic`. The skill never infers that
mapping from a title: with no link it drafts the Jira half in full and marks
upstream coverage unassessable. See
[`examples/jira-link-section.md`](examples/jira-link-section.md) for the format
and for the multi-epic case.

## Usage

From a Claude Code session with this repo's `.claude/` directory in scope:

```
> roll up the upstream status for RHOAIENG-1234
> are the acceptance criteria on RHOAIENG-1234 covered upstream?
> generate an HTML report for RHOAIENG-1234
```

The skill shows you the draft, then asks whether to post that exact text.
Approval of an earlier draft never carries forward, and only the summary is ever
posted.

The HTML is written only when `--html` names a path, and it is a local file:
self-contained, no network at runtime. The summary carries a "Full assessment"
link only when you supply an absolute `http(s)` URL that already serves the
document — the skill does not host or publish it. Any stored run re-renders
offline with `rollup.py rerender --snapshot <path>`, which rebuilds the outputs
from the saved assessment and makes no new judgement.

## How it works

The model does what is a judgement; the scripts do what is mechanical.

1. **Read the issue** — the model quotes every acceptance criterion, success
   criterion and definition-of-done item verbatim, plus one level of child
   requirements.
2. **Collect** — `refs` and `collect` walk the linked epics, their children and
   those children's pull requests, caching every raw response and returning a
   manifest of refs, states, timestamps, content hashes and access failures.
3. **Diff** — `diff` picks the baseline and matches requirements on `(source
   issue, type, verbatim text)` rather than on ID, splitting them into reassess
   and carry-forward.
4. **Assess** — the model judges what the inspected evidence establishes for
   each requirement in the reassess set, reading artifacts via `excerpt`. Where
   a specific question is left open and a source already in scope would settle
   it, `source` opens that one file at the revision the evidence was produced
   at, within a budget of twelve reads per run.
5. **Assemble** — `assemble` merges, tallies, cross-checks, renders, and writes
   a dated snapshot.
6. **Post** — only after approval; `promote` records the returned comment id, so
   the published baseline advances only when a comment actually landed.

Raw API responses never enter the conversation — the model reads excerpts it
asks for.

**Baseline.** The most recent *published* snapshot. With none, the most recent
snapshot is used and labelled as never published — so draft runs, and runs whose
traversal was incomplete, can become baselines. A snapshot that cannot be read
or whose schema is unrecognised is skipped and reported.

**Reuse.** A requirement is reassessed when it is new or its text changed, when
evidence it rests on changed, was removed, reopened or changed access, when new
work appeared in a repository its evidence comes from, when a declared
dependency moved, when downstream qualification was `pending`, or when the
mapping, the rules version or the baseline itself is unusable. A stored
`confirmed` qualification is reused — it is an event that already happened —
and `--full-refresh` reassesses everything regardless.

## How to interpret results

Each requirement gets exactly one coverage assessment:

| Assessment | Means |
| --- | --- |
| Evidence found | Every checkable clause of the criterion is supported by evidence that was read, and no clause is undecided |
| Partial evidence | Some clauses are supported; the rest are named, each with why it is open |
| No evidence found | The sources inspected do not establish coverage |
| Unable to assess | Access failure, truncated results, no checkable clause, or no upstream mapping |

Alongside it, two further questions are answered separately and never folded
in: **evidence state** (planned, in progress, in review, merged, tested) and
**downstream qualification** (`confirmed`, `pending` where someone looked and
found nothing qualifying, or `unknown` where nobody looked). So `Evidence found`
says the inspected upstream evidence supports every clause — not that the
requirement is implemented, tested, released or qualified. An open issue is
planned work, a merged PR is landed implementation, and qualification is its own
question.

The trend section reports three unweighted ratios — child issues completed,
requirements with evidence found, requirements confirmed downstream.
**Requirements with evidence found** counts criteria assessed `Evidence found`
over all extracted criteria: a measure of upstream evidence, not a completion
percentage. `Partial evidence` earns no fractional credit. Four distinctions it
preserves:

- **"No evidence found" is scoped to the sources inspected**, never proof that
  the work does not exist.
- **A question nobody answered is not a feature nobody built.** Every clause
  left open says which of three things it is: something inspected shows the
  behaviour missing, what was inspected does not settle it, or the source that
  would settle it could not be read. Only the first is a finding about the
  product.
- **Newly visible is not newly done.** Evidence dated before the baseline is
  reported as newly discovered, not as progress.
- **Added scope is not regression.** A growing denominator drops the percentage
  with nothing having gone backwards, so a like-for-like figure over unchanged
  requirements is given alongside it.
- **AC, SC and DoD stay apart.** Counted and labelled separately; a pooled total
  called "acceptance criteria" misstates what was agreed.

Worked examples: [`sample-rollup.md`](examples/sample-rollup.md),
[`sample-rollup-rerun.md`](examples/sample-rollup-rerun.md), and the desk-check
fixtures in [`examples/`](examples/).

## Limitations

- **The epic link must already be on the Jira issue.** The skill never guesses
  and never title-searches. With no link it drafts the Jira side, marks upstream
  coverage unassessable, and asks for the link — it never reports the work as
  unstarted.
- **Traversal is bounded** to the mapped epics, their children, those children's
  pull requests, and directly referenced dependencies. A nested epic is
  traversed one further level, and only when a sub-issue or task-list entry
  declared it; one merely cross-referenced is recorded as untraversed and named
  in all three renderings. Anything deeper stays outside the assessment.
- **Collection failures are reported, not absorbed.** Unreadable repos and
  truncated results come back `Unable to assess` and are named prominently; a
  count that was not observed is `unknown`, never zero.
- **No forecasting.** No velocity, burn-down, effort estimate or projected date;
  the trend compares two observations and nothing more.
- **No automatic posting and no workflow changes.** One comment, on the one
  issue you named, after you approve the text. The skill never creates Jira
  issues, and GitHub access is read-only.
- **Reuse is scoped by repository.** New work reassesses the requirements whose
  evidence comes from that repository, not every requirement. A criterion
  covered by evidence in one repo and quietly undone by a change in another is
  the case `--full-refresh` exists for.

## References

The scripted half has tests, which stub `gh` with a JSON world file and need no
network and no credentials:

```bash
python3 -m unittest discover -s tests
```

Everything lives under `.claude/skills/jira-github-rollup/`:
[`SKILL.md`](.claude/skills/jira-github-rollup/SKILL.md) is the procedure and
the invariants; `scripts/` is the Python. The references cover
[commands, storage and recovery](.claude/skills/jira-github-rollup/references/pipeline.md),
[extraction and assessment rules](.claude/skills/jira-github-rollup/references/requirements.md),
[the output contract](.claude/skills/jira-github-rollup/references/rollup-format.md)
and [the snapshot store and metrics](.claude/skills/jira-github-rollup/references/snapshots.md).
Tests are in `tests/`.

**Data handling.** Under `~/.jira-github-rollup/` (or `$JGR_HOME`) the skill
keeps an append-only snapshot store and a disposable cache of raw `gh`
responses. Both are local and unencrypted, and both can hold verbatim text from
private Jira issues and GitHub repositories. Data does leave your machine during
a run: `gh` and the Atlassian MCP server make the API calls, selected excerpts
enter Claude's context, and an approved summary is posted to Jira.

**Status.** Proof of concept. See [`docs/poc-plan.md`](docs/poc-plan.md) for
scope, known gaps, and what would need to be true to use this on real
requirements.
