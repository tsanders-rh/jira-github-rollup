# Rollup format

The output contract for a drafted rollup. Structure is fixed; length is not — but
shorter is better. Target 15–30 lines of body text, plus one row per requirement.

"Requirement" here means any statement extracted in `SKILL.md` step 2 —
acceptance criterion (`AC`), success criterion (`SC`), definition-of-done item
(`DoD`), or unlabelled (`REQ`). The prefix is how the type survives into the
output; it is never dropped, and the types are never added together under the
label "acceptance criteria".

## Two renderings of one rollup

The content below is the contract. It gets rendered twice, in different markup,
and the two are not interchangeable:

| | Rendering | Markup |
| --- | --- | --- |
| **Draft** — shown in the conversation for review | always | **GitHub-flavored Markdown** |
| **Payload** — passed to the Jira comment tool after approval | only on approval | whatever that tool documents as its input format (see [Preparing the Jira payload](#preparing-the-jira-payload)) |

The draft is GFM because that is what the surrounding conversation renders. Jira
wiki markup shown in a terminal is unreadable — `||` header rows and `h3.` lines
do not render, so the reviewer is asked to approve a wall of punctuation instead
of the table they are actually approving. Conversion happens once, at post time,
against the format the tool actually accepts.

Everything else — sections, order, wording, what each cell contains — is
identical in both. The markup changes; the rollup does not.

## Audience and tone

Written for a program manager or EM scanning a Jira issue for risk. They want to
know, in order: is it on track, what moved since last time, and what is blocked.
They do not want a changelog.

- Plain declarative sentences. No marketing adjectives.
- Dates are absolute (`2026-10-02`), never relative (`last week`).
- Every claim traces to a linked issue, a PR, or the Jira issue itself. If it
  cannot be traced, do not say it.
- Uncertainty is stated, not smoothed over. "No activity since 2026-08-14" beats
  "progressing steadily."

## Structure

GitHub-flavored Markdown. This is what the reviewer sees.

````markdown
### Upstream Development Rollup

**Status:** <Not started | In progress | Blocked | Complete | Unknown — upstream mapping missing>
**Source epic:** [org/repo#N](https://github.com/org/repo/issues/N) — <epic title>
**Generated:** <YYYY-MM-DD>

#### Summary

<Two to five sentences. What is the state of this requirement upstream, what is
the single most important thing a reader should know, and which requirements are
materially uncovered or unassessable.>

#### Progress

<N of M> child issues closed as completed; <P> pull requests merged.

| Child | Status | PRs |
| --- | --- | --- |
| org/repo#12 — <title> | Closed | org/repo#45 (merged 2026-09-30) |
| org/repo#13 — <title> | Open | org/repo#51 (open, 9d) |
| other-org/other-repo#7 — <title> | Open | — |

#### Requirements coverage

<C> acceptance criteria, <D> success criteria, <E> definition-of-done items.

| Requirement | Evidence | Evidence state | Coverage | Gap / next validation step |
| --- | --- | --- | --- | --- |
| AC1 (RHOAIENG-1234) "<verbatim text>" | org/repo#413, org/repo#520 (merged 2026-09-18) | merged | Evidence found — <what the evidence establishes> | <what remains, or "—"> |
| DoD1 (RHOAIENG-1234) "<verbatim text>" | org/repo#530 (merged 2026-10-01) | merged | Partial evidence — <covered clause>; <unresolved clause> cannot be checked until <decision> | <who decides> |
| AC1 (RHOAIENG-1240) "<verbatim text>" | org/repo#88 (open) | planned | No evidence found — mapped issue is open; no implementation in the sources inspected | <next step> |

#### Downstream qualification

- AC1 (RHOAIENG-1234) — <what is still required downstream, or that downstream
  state was not inspected>

#### Coverage caveats

- <Inaccessible sources, truncated traversal, unresolved or unassessable
  requirements, requirements with no upstream mapping. Omit the section only
  when there are none.>

#### Risks and blockers

- <Only real, evidenced items. Omit the whole section if there are none —
  do not write "No risks identified" as filler.>

#### Trend since previous snapshot

Baseline: <published|draft> snapshot <YYYY-MM-DD>. This snapshot: <YYYY-MM-DD>.

| Indicator | Previous | Current | Change |
| --- | --- | --- | --- |
| Child issues completed | 2/4 (50%) | 4/7 (57%) | +2 issues, +7 pp |
| Requirements with evidence found | 1/6 (17%) | 3/8 (38%) | +2 requirements, +21 pp |
| Partial / no evidence / unable to assess | 1 / 3 / 1 | 1 / 2 / 2 | 0 / −1 / +1 |
| Downstream confirmed / pending / unknown | 0 / 0 / 6 | 0 / 0 / 8 | no change |

Not counted toward completion: <1 child closed as not planned, 1 child closed
with no reason recorded>.

- <What moved, one bullet per kind: implementation progress, newly discovered
  evidence, scope added or removed, requirement text changed, mapping changed,
  issue reopened, access gained or lost. Separate statements, never merged.>

_Unweighted counts of requirements and child issues. Not a measure of effort
completed, work remaining, or release readiness._

---

_Generated by the jira-github-rollup skill from org/repo#N. Read-only against
GitHub; no Jira issues were created._
````

Markdown specifics worth getting right:

- `###` for the title, `####` for sections. They map cleanly onto `h3.`/`h4.` at
  conversion time, which is why the levels are fixed.
- Full URLs on the **Source epic** line, so a reviewer can click through to the
  thing the rollup is derived from. Inside tables use the short `org/repo#N`
  form — full URLs make the cells unreadable, and the reference is unambiguous.
- A literal `|` inside any cell must be escaped as `\|`, or the row breaks.
  Verbatim criterion text is the likely source of one.
- Keep the blank line between a heading and the table under it. Some renderers
  swallow a table that starts immediately after a heading.

## Structure when no upstream mapping exists

Same contract, minus the sections nothing was inspected for, plus one that says
what is missing. Used when `SKILL.md` step 3 found no GitHub link at all.

````markdown
### Upstream Development Rollup

**Status:** Unknown — upstream mapping missing
**Source epic:** none recorded on RHOAIENG-1234
**Generated:** <YYYY-MM-DD>

#### Summary

RHOAIENG-1234 records no link to upstream GitHub work, so no upstream state was
inspected and upstream progress and coverage could not be assessed. The
requirements below are reproduced from the Jira as stated. This says nothing
about whether the work has been done — only that this issue does not record
where it is tracked.

#### Jira scope

RHOAIENG-1234 — <summary> (<status>, fix version <X>)
Child requirements read: RHOAIENG-1240 — <summary> (<status>)

#### Requirements coverage

<C> acceptance criteria, <D> success criteria, <E> definition-of-done items.

| Requirement | Evidence | Evidence state | Coverage | Gap / next validation step |
| --- | --- | --- | --- | --- |
| AC1 (RHOAIENG-1234) "<verbatim text>" | — | — | Unable to assess — upstream mapping missing | Link the upstream epic |
| AC1 (RHOAIENG-1240) "<verbatim text>" | — | — | Unable to assess — upstream mapping missing | Link the upstream epic |

#### What is needed to complete this assessment

- The GitHub epic issue URL for this requirement, recorded on RHOAIENG-1234 in an
  `Upstream Development` description section or as a web link labelled
  `Upstream epic`. Several URLs if the requirement spans more than one epic.
- Alternatively, the URL supplied directly in the request.
- Nothing else is blocking: the requirements were read successfully and will be
  assessed against whatever epic is supplied.

#### Trend since previous snapshot

Baseline: published snapshot <YYYY-MM-DD>. This snapshot: <YYYY-MM-DD>.

| Indicator | Previous | Current | Change |
| --- | --- | --- | --- |
| Child issues completed | 2/4 (50%) | unknown | unknown — no upstream mapping recorded this run |
| Requirements with evidence found | 1/6 (17%) | 0/6 (0%) | −1, −17 pp |
| Partial / no evidence / unable to assess | 1 / 3 / 1 | 0 / 0 / 6 | −1 / −3 / +5 |
| Downstream confirmed / pending / unknown | 0 / 0 / 6 | 0 / 0 / 6 | no change |

- The `Upstream Development` section present at the previous snapshot is no
  longer on RHOAIENG-1234. No upstream source was inspected this run, so no
  assessment carries over. This is a change to the Jira issue, not to the work:
  the evidence recorded on <YYYY-MM-DD> has not been withdrawn, and nothing
  observed this run says anything about the current state of the implementation.

_Unweighted counts of requirements and child issues. Not a measure of effort
completed, work remaining, or release readiness._

---

_Generated by the jira-github-rollup skill. No upstream link was found on
RHOAIENG-1234. Read-only against GitHub; no Jira issues were created._
````

Rules specific to this shape:

- **Jira scope** replaces Progress: the named issue with its status and fix
  version, then every child requirement that was read, by key. It establishes
  what *was* inspected, which is what makes the rest of the draft legible.
- **What is needed** is an instruction, not a complaint. Name the artifact (a
  GitHub epic issue URL), where it goes, that several are allowed, and what is
  not blocked. "Add an upstream link" is not enough to act on.
- **No Progress section.** Nothing upstream was inspected; `0 of 0 children
  closed` reads as zero progress, which is a claim about the work.
- **No Risks and blockers section** unless the risk is evidenced from the Jira
  alone. "No upstream link is recorded" is a tracking gap, and it is already the
  headline — do not restate it as a delivery risk.
- Every Coverage cell is `Unable to assess — upstream mapping missing`, the same
  wording in every row. Not `No evidence found`, which claims a search happened.
- Nothing is asserted about the state of the work. "Not started", "not
  implemented", "no progress", "behind", and "at risk" are all claims you have
  no basis for. Naming them as possibilities you cannot distinguish between —
  "may be complete, in flight, or unstarted" — is the opposite move, and it is
  the one sentence that keeps a reader from filling the silence themselves.
- Quoting, types, IDs, and source keys are unchanged — this is the part of the
  rollup that still works, and it is why the partial draft is worth producing.
- **The Trend section stays**, and child-issue completion in it reads `unknown` —
  never `0/0` and never `N/A`. A requirement that had upstream evidence at the
  previous snapshot and has none now, because the link was removed, is a change
  to the Jira issue. Say exactly that, and say that the previously recorded
  evidence has not been withdrawn. The drop in the coverage row is real as a
  measurement and says nothing about the implementation; if that sentence is not
  next to the number, do not print the number.

## Notes on each section

**Status** — derived from the evidence table in `SKILL.md` step 7. `Blocked`
requires a named blocker in the Risks section; do not use it loosely. `Complete`
additionally requires every requirement at `Evidence found` with no downstream
qualification outstanding. `Unknown — upstream mapping missing` is the only
value permitted when no epic was found, and it is never softened to `Not
started`.

**Source epic** — list **every** epic in scope, one per line, each with its
title. This is what makes the rollup auditable, and with multiple epics it is
also what lets a reader check which one a given child belongs to.

With more than one epic in scope, attribution has to survive into the body:

- the Progress table gets a leading `Epic` column, or one sub-table per epic
  with its own counts line;
- Evidence cells name the epic when the owning repo does not make it obvious;
- absence claims enumerate all of them — "no evidence in
  example-org/example-gateway#412 or example-org/example-controller#87 and their
  children". An absence scoped to one epic when two were inspected is a false
  statement about the other.

When an epic came from an unlabelled source (a bare URL in the description or a
comment, used because no explicit mapping existed), say so on the Source epic
line: `example-org/example-gateway#412 — <title> (from an unlabelled URL in the
description; confirm this is the intended mapping)`.

**Summary** — the only part most readers will read. Lead with the state, not the
history. If something is at risk, it goes in the first sentence.

It must also carry the material coverage gaps — any requirement at `No evidence
found` or `Partial evidence`, and any coverage that could not be assessed. Name
the kind, because the follow-ups differ and the reader is deciding who to ask:

| Kind | Phrase it as |
| --- | --- |
| Missing mapping | "RHOAIENG-1234 records no upstream link, so no upstream state was inspected." |
| Missing tracking | "No upstream work is linked for <requirement>." |
| Unresolved requirement | "<requirement> leaves <parameter> undecided; <who> has to set it before the clause can be checked." |
| Unfinished implementation | "<requirement> is tracked in org/repo#88 but unimplemented." |
| Downstream validation | "<requirement> landed upstream; downstream qualification is pending." |

Counts in the Summary follow the step 2 rule: break them down by type, or say
"requirements". "Two of five acceptance criteria are uncovered" is wrong when
one of the five is a definition-of-done item.

If a source was inaccessible, the Summary says coverage is incomplete and why.
Burying that below the table makes the rest of the section read as authoritative
when it is not.

**Progress** — the counts line is required; the table is required when there are
1–15 children. Above 15, drop the table and summarize by repo instead, listing
only children that are open or flagged. Omit the section entirely when no
upstream mapping was found — see the partial shape above.

Use `—` for a child with no PRs. Mark PR age for open PRs (`open, 9d`) because
that is the review-latency signal.

The counts line uses the same definition as the Trend section: **closed as
completed** only. A child closed as not planned, or closed with no reason
recorded, is counted in the total and named in the Status column
(`Closed (not planned)`, `Closed (reason not recorded)`) — never folded into the
closed count and never dropped from the denominator. `2 of 5 child issues closed
as completed; 1 closed as not planned` is the shape.

**Requirements coverage** — one row per requirement from `SKILL.md` step 2, in
the order they appear on the Jira: the named issue's requirements first, in
heading order, then each child requirement's. Required whenever any were found,
including when no upstream mapping exists.

The counts line above the table is by type (`3 acceptance criteria, 1
definition-of-done item`). Never give a single total labelled as acceptance
criteria.

Above 12 requirements the table stops being read, which is the same failure as a
rollup longer than a screen. Keep every row that is not `Evidence found`, and
collapse the rest into one line (`4 further requirements assessed Evidence found
with no downstream step outstanding: AC2, AC5, DoD1, SC2`). Never collapse a row
with `Partial evidence`, `No evidence found`, `Unable to assess`, an unresolved
clause, or an outstanding downstream step — those are the rows the section exists
for.

When no requirements were found, replace the table with a single line naming
where you looked:

```markdown
#### Requirements coverage

No acceptance criteria, success criteria, or definition of done found on
RHOAIENG-1234 (description, acceptance-criteria field, sub-tasks). Nothing to
assess coverage against.
```

Column by column:

| Column | Contains |
| --- | --- |
| Requirement | `AC<n>` / `SC<n>` / `DoD<n>` / `REQ<n>` + `(SOURCE-KEY)`, then the text **in quotes, verbatim** |
| Evidence | Issue and PR references with merge dates, attributed to their epic when more than one is in scope; `—` when nothing is mapped |
| Evidence state | One of: planned, in progress, in review, merged, tested; `—` when nothing is mapped |
| Coverage | One of the four assessments, an em dash, then what it rests on |
| Gap / next validation step | What remains, and who or what resolves it |

- The prefix carries the type and the key carries the source, and **neither is
  decoration.** IDs are numbered per type per source issue, so a table drawing on
  a parent and a child contains two rows labelled `AC1`, and a parent with both
  kinds of heading contains `AC1` and `DoD1`. Drop either part and a reader holds
  the wrong owner accountable for the wrong kind of commitment.
- Long text is quoted to a sentence boundary with a trailing `…`. Never
  paraphrase to fit the column.
- The Coverage cell is never bare. `Evidence found` alone is unverifiable;
  `Evidence found — PR #520 adds tier-based pool selection and merged to main on
  2026-09-18` can be checked.
- Absence is scoped in the cell itself: "no evidence in
  example-org/example-gateway#412 and its children," not "not implemented."
- `Evidence state` is `—` when nothing is mapped. Do not write `planned` for a
  requirement that has no upstream issue; that implies tracking that does not exist.
- A requirement with a checkable clause and an undecided one gets **one** row
  covering both: the assessment the checkable clauses earned, then the unresolved
  clause named in the same cell, with the decision it waits on in the Gap column.
  Do not split it into two rows, and do not let the TBD swallow the row —
  `Unable to assess` on a criterion that was half-checkable discards work already
  done.

**Downstream qualification** — one bullet per requirement that still needs
downstream integration or qualification, including those whose upstream coverage
is `Evidence found`. Merged upstream is not shipped downstream, and the reader
needs the two separated.

Close the section with the scope of the claim when it applies:

```
Requirements not listed above have no identified downstream step in the sources
inspected; that is not confirmation that none is required.
```

Do not name a downstream owner, build, or date that the sources did not provide.

Omit the section when no upstream mapping exists — with nothing established
upstream, there is no downstream question to raise yet.

**Coverage caveats** — this is where incomplete retrieval is admitted. Entries:

- A repository or issue that returned 404 or was otherwise unreadable, by name
- Truncated or unpaginated results, and what was therefore not checked
- Requirements with no checkable clause, quoted, with the restatement request
- Requirements with an undecided parameter, quoted, naming the decision and who
  owns it
- Requirements with no upstream mapping, flagged for owner review
- An epic taken from an unlabelled source, or explicit links the user has not yet
  confirmed are in scope

Each caveat says what it prevents. "example-org/example-dlp is not readable from
this account" is a fact; "so AC5 could not be assessed" is why the reader cares.

**Risks and blockers** — evidenced items only. Typical entries:

- A child open 30+ days with no linked PR
- A PR open 14+ days with no review
- A cross-repo dependency on a team that does not own this requirement
- A child closed without a merged PR (state why, or state that it is unclear)
- A requirement with no upstream mapping at all — that is a tracking gap, and it
  belongs here as well as in the coverage table

**Trend since previous snapshot** — movement against the previous saved
snapshot. `references/snapshots.md` defines the store, the schema, how
requirements are matched across runs, and exactly how each number is computed;
this section covers only how it is rendered. Never omit the section: on a first
run it is one line.

Always open with the baseline, because the delta means nothing without it:

| Situation | Opening line |
| --- | --- |
| Published baseline | `Baseline: published snapshot 2026-10-05. This snapshot: 2026-11-02.` |
| Draft baseline | `Baseline: draft snapshot 2026-10-05 (never published). This snapshot: 2026-11-02.` |
| No baseline | `Baseline established — no prior snapshot available.` and nothing else — no table, no zeroes, no bullets |
| Baseline unreadable | `A snapshot dated 2026-10-05 exists but could not be read (<reason>). Baseline established — no comparison is made.` |

The four table rows are fixed, in that order, present even when a row is
unchanged. A row that did not move says `no change`, not `0`, so the reader can
tell "measured and flat" from "nothing here".

- **Percentages always carry their fraction.** `4/7 (57%)` — never a bare
  percentage. Deltas in counts *and* percentage points, labelled `pp`, because a
  percentage change with a moving denominator is not a count change.
- **A zero denominator renders `N/A`** with the reason in the Change column, not
  `0%` and not `100%` — and only when the zero was observed.
- **A count that could not be observed renders `unknown`**, with the reason in
  the Change column. That is both the no-mapping case and the unreadable-epic
  case: a 404 is not a count of zero, and `0/0` claims a measurement that never
  succeeded.
- **`Partial` never earns fractional credit** and never appears inside the
  evidence-found ratio. It has its own column position and stays there.
- **Requirement types stay distinct.** When the type mix changed, add one line:
  `Requirement mix: 5 acceptance criteria, 1 definition-of-done item (previously
  4 and 1).` Only the aggregate may be called "requirements".
- The **not counted toward completion** line is required whenever any child is
  `not planned` or closed with no reason recorded. Those children stay in the
  denominator; this line is what keeps them visible rather than silently
  depressing the percentage.

The bullets are where the report earns its keep, and they have one job: keep
causes apart. Each of these is a separate bullet, never merged into a single
"progress" statement:

| Kind | Phrase it as |
| --- | --- |
| Implementation progress | "AC2 gained evidence from PR #536, merged 2026-10-01 — after the previous snapshot." |
| Newly discovered evidence | "AC4 moved to Evidence found on access to example-org/example-dlp being restored. PR #77 merged 2026-08-04, before the previous snapshot: this is evidence newly visible, not work newly done." |
| Scope added | "Two acceptance criteria were added to RHOAIENG-1234. The coverage denominator rose from 6 to 8; no requirement lost evidence." |
| Scope removed | "SC1 was removed from the Jira. It was `No evidence found` at the previous snapshot." |
| Text changed | "AC3's text changed; the previous assessment does not carry over and it is reassessed from scratch." |
| Mapping changed | "example-org/example-audit#12 was added to the Upstream Development section." |
| Reopened | "example-org/example-gateway#413 was closed at the previous snapshot and is open again." |
| Access changed | "example-org/example-dlp is readable again." / "example-org/example-meter returned 404 this run; it was readable on 2026-10-05." |

**A falling percentage caused by added scope is stated as scope, in the same
sentence as the number.** "Coverage fell from 40% to 36%" on its own is a true
sentence that misleads, and the reader acts on the first clause they read.
Whenever the denominator moved, give the like-for-like figure over the
requirements present and unchanged in both snapshots.

**Never derive a rate, a velocity, a burn-down, or a projected date.** Two
unweighted counts support none of them. The closing italic label is not optional
and is not softened — it is the one line that stops the section being read as a
release forecast.

**Marker line** — the trailing `_Generated by the jira-github-rollup skill…_` line
is load-bearing. It is how a later run finds and offers to update a prior rollup
in place instead of appending a duplicate. Match it on the sentence, not on the
markup around it — a comment posted as wiki markup or plain text carries the same
words without the underscores.

## Preparing the Jira payload

Only after the user approves the draft, and only for the string handed to the
Jira comment tool. Nothing in this section applies to what you show in the
conversation.

**Do not assume the format.** Jira Cloud sites may take wiki markup, Atlassian
Document Format, or plain text depending on the site's editor and on what the
MCP tool does with the value. Before converting, establish what the tool
documents as its input: read the comment tool's parameter description and schema
(`addOrEditJiraIssueComment`; its schema arrives with the tool definition). Let
that decide the target format. If the tool's documentation is silent or
ambiguous, prefer the plain-text structure below — it is the only rendering that
degrades gracefully everywhere — and say in one line which format you sent and
why, so a mis-render is diagnosable instead of mysterious.

**Never send the GFM draft verbatim** to a site that takes wiki markup. `###`
and `**bold**` are literal text there, the `| --- |` separator row renders as a
table row of dashes, and the result looks like a bug in the issue rather than a
report.

### If the target takes wiki markup

| Intent | GFM draft | Wiki payload |
| --- | --- | --- |
| Title heading | `### Title` | `h3. Title` |
| Section heading | `#### Title` | `h4. Title` |
| Bold | `**bold**` | `*bold*` |
| Italic | `_italic_` | `_italic_` (unchanged) |
| Table header | `\| A \| B \|` + `\| --- \| --- \|` | `\|\| A \|\| B \|\|`, no separator row |
| Table body | `\| a \| b \|` | `\| a \| b \|` (unchanged) |
| Link | `[text](https://url)` | `[text\|https://url]` |
| Rule | `---` | `----` |
| Inline code | `` `code` `` | `{{code}}` |

Dropping the GFM separator row is the step most easily missed; it has no wiki
equivalent and renders as a junk row if carried over.

Bare GitHub URLs auto-link in most Jira configurations and are more readable in
the raw comment than piped links — prefer them for issue and PR references, and
reserve `[text|url]` for the Source epic line.

### If the target takes ADF or you are unsure

Plain text with bare URLs renders acceptably everywhere; wiki markup does not.
Keep the section order and labels, drop the markup, and replace the tables.

The coverage table is five columns wide and is the first thing to render badly on
an ADF site or in a narrow comment pane. The fallback is one block per
requirement, same fields, same order — never drop a field to make the table fit:

```
AC1 (RHOAIENG-1234) "Requests for a tiered model are routed to the pool for that tier."
  Evidence: example-org/example-gateway#413, PR #520 (merged 2026-09-18)
  State: merged
  Coverage: Evidence found — PR #520 implements tier-based pool selection.
  Gap: Downstream qualification pending.
```

### What survives conversion unchanged

- Section order, section names, and which sections are present or omitted.
- Every verbatim criterion quote, its prefix, and its source key.
- The marker line's wording. It is matched as text when a later run looks for a
  prior rollup, so it has to survive in whatever markup was posted — which is
  also why the match is on the sentence, not on the italics around it.

If conversion would force any of those to change, send plain text instead. The
markup is the negotiable part.
