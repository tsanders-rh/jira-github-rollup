# Rollup format

The output contract for a drafted rollup. Structure is fixed; length is not — but
shorter is better. Target 15–30 lines of body text, plus one row per requirement.

**`jgr/render.py` emits this shape**, driven by `rollup.py assemble`. You do not
write the report by hand: you supply the judgement fields — the Summary, each
requirement's assessment and its evidence, caveats, risks, extra trend notes —
and the renderer places them in the sections, formats every ratio, and derives
the status line. Read this file to know what a cell is claiming and what belongs
in the text you supply; read it before changing the renderer. If the rendered
draft disagrees with this document, that is a bug in one of the two, not a
licence to retype the report.

"Requirement" here means any statement extracted in `SKILL.md` step 2 —
acceptance criterion (`AC`), success criterion (`SC`), definition-of-done item
(`DoD`), or unlabelled (`REQ`). The prefix is how the type survives into the
output; it is never dropped, and the types are never added together under the
label "acceptance criteria".

## One assessment, rendered three ways

`rollup.py assemble` renders from one merged assessment and one tally. The
renderings have different jobs and different readers:

| | Audience | Length | Posted? |
| --- | --- | --- | --- |
| **Full assessment** (`--report`) | An engineer reviewing the evidence, in this conversation | As long as the evidence needs | Never |
| **Jira summary** (`--summary`) | An EM or exec scanning the issue | 150–250 words of prose | Only this one, only on explicit approval |
| **HTML full assessment** (`--html`) | Someone reading or forwarding it outside this conversation | The full assessment, with the evidence behind disclosures | Never; it is a file, not a link |

The first two are GitHub-flavored Markdown, because that is what the
conversation renders *and* what the Jira comment tool documents as its default
input. A reviewer asked to approve wiki markup in a terminal is approving a wall
of punctuation rather than the table they will get.

**They can never disagree.** All three are built from one `outcomes.tally()`
call, and `assemble.cross_check` refuses to emit anything if the outcome row is
absent from one of them or if the counts do not sum to the criteria total. The
HTML is checked twice over: its by-type rows come from `metrics.by_type` and its
totals from `outcomes.tally`, so a type whose rows do not add up fails the run
even though both numbers are individually right. Do not hand-edit one rendering
to match another — fix the assessment and re-render.

The HTML is rendered on **every** run whether or not `--html` asked for a file,
so the cross-check covers it every time rather than only on the runs that happen
to write it out. It never goes to stdout: `result.json` reports `htmlBytes`, and
`htmlPath` only when a path was named.

The split is about detail, not about honesty. Everything in the summary is also
in the full assessment. What stays out of the summary is the per-criterion
analysis and the collection diagnostics; what stays out of the full assessment
is nothing.

### The four outcomes

Both outputs count criteria into four mutually exclusive buckets that sum to the
total. `jgr/outcomes.py` owns the mapping; it is not re-derived in prose.

| Outcome | Means | Comes from |
| --- | --- | --- |
| `met` | Every clause supported at the stated assessment level | `Evidence found` |
| `partial` | Some clauses supported, others incomplete or unverified | `Partial evidence` |
| `confirmed-unmet` | **Affirmative evidence the outcome is not satisfied** | A declared `outcome` plus `refutingEvidence`; never inferred |
| `unverified` | Insufficient evidence, or collection did not reach it | `No evidence found`, `Unable to assess` |

The caption travels with the counts, every time: *Upstream evidence assessment,
not release completion.* These count what the sources inspected establish, not
what shipped, and they are never turned into a percentage of a feature.

`unverified` is the default for absence and stays there however much is missing.
A criterion nobody linked work to is unverified with a tracking clarification —
not unmet, and not a finding about whether the work exists.

`met` is held to its definition rather than trusted to it. "Every clause
supported" is checked: a requirement carrying `uncoveredClauses` (checkable,
nothing supports it) or `unresolvedClauses` (nobody has decided it) cannot be
`Evidence found`, and `assemble` refuses the run rather than downgrading the
count behind a detail cell that still reads as fully established. Those two
lists stay separate in the output — one needs engineering or a link, the other
needs a product decision.

### Delivery confidence

A judgement line, **not** a function of the counts. `outcomes.confidence()`
returns `Not assessed` whenever the issue has no fix version, any criterion has
no downstream qualification evidence, or anything is unverified — and it says
which of those applied. Nine met criteria with no release target is still
`Not assessed`; green in the table is not a delivery signal.

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

## Structure of the full assessment

GitHub-flavored Markdown. This is what the reviewer sees, and it is never
posted.

````markdown
### Upstream Development Rollup

**Status:** <Not started | In progress | Blocked | Complete | Unknown — ‹why nothing was observed›>
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

| Outcomes met | Partial | Confirmed unmet | Unverified |
| --- | --- | --- | --- |
| 1 | 1 | 0 | 1 |

_Upstream evidence assessment, not release completion. 3 criteria in total; the
four columns are mutually exclusive and sum to that. These are the same counts
the Jira summary carries._

| Type | Total | Outcomes met | Partial | Confirmed unmet | Unverified |
| --- | --- | --- | --- | --- | --- |
| Acceptance criteria | 2 | 1 | 1 | 0 | 0 |
| Definition-of-done items | 1 | 0 | 0 | 0 | 1 |

_Counted separately by type. They are not summed into a completion figure: an
acceptance criterion, a success criterion and a definition-of-done item are not
interchangeable units of delivery._

| Requirement | Outcome | Evidence | Evidence state | Coverage | Gap / next validation step |
| --- | --- | --- | --- | --- | --- |
| AC1 (RHOAIENG-1234) "<verbatim text>" | Met | org/repo#413, org/repo#520 (merged 2026-09-18) | merged | Evidence found — <what the evidence establishes> | <what remains, or "—"> |
| DoD1 (RHOAIENG-1234) "<verbatim text>" | Partial | org/repo#530 (merged 2026-10-01) | merged | Partial evidence — <covered clause>; <unresolved clause> cannot be checked until <decision> | <who decides> |
| AC1 (RHOAIENG-1240) "<verbatim text>" | Unverified | org/repo#88 (open) | planned | No evidence found — mapped issue is open; no implementation in the sources inspected | <next step> |

#### Downstream qualification

| Qualification | Criteria |
| --- | --- |
| Verified, with evidence | 0 |
| Inspected; no qualifying evidence found | 1 |
| Not inspected | 2 |

_Qualification is a separate question from upstream coverage, and neither is a
release-readiness verdict. A criterion with upstream evidence and no
qualification is not partly released._

- **Not inspected.** AC1 (RHOAIENG-1234) — <what is still required downstream,
  or that downstream state was not inspected>

#### Dependencies, decisions, and tracking gaps

- **Decision needed** — SC4 (RHOAIENG-1234): <the undecided parameter>. Until it
  is recorded, this clause is unassessable rather than unmet.
- **Tracking clarification** — no upstream work in the traversed set maps to
  SC6 (RHOAIENG-1234). Identify and link the work covering SC6 on RHOAIENG-1234.
  Absence in the sources inspected is not a finding that the work does not exist.
- **Dependency** — SC9: <linked Jira or epic>. <What the source that named it
  said.>

#### Collection scope and limitations

- Jira sources read for requirements: description, sub-tasks.
- Traversed 1 epic, 23 child issues across 3 repositories.
- **Not traversed:** [org/repo#1445](…) — <title>. Identified as a nested epic
  (task-list); reached only by timeline-cross-reference, which establishes a
  mention rather than membership.
- Criteria owned by work beneath the epics above are not in this assessment at
  all. Any row below reading as unevidenced may be covered there: that is a
  limit of the traversal, not a finding about the work.
- Not readable: org/other#40 (404) — <detail>.
- Evidence basis: issue and pull-request metadata, changed-file lists, and CI
  check results. No diffs were read, so a changed file or a passing job locates
  the work; it does not by itself verify a behaviour.
- No downstream build, payload, or qualification run was inspected.

The discovery relation appears once on a **Not traversed** line. The mention
reason names it already; the depth-cap reason (`already 1 level below the
mapped epic`) does not, so `render` adds `reached by <relation>` only there.

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

## Structure of the Jira summary draft

`jgr/summary.py` emits this. It is the only thing ever posted, and it is a
second rendering of the same assessment — not a shortened report and not a
progress bar.

````markdown
### <Requirement name> — Upstream rollup

**Updated:** <YYYY-MM-DD>
**Source:** [org/repo#N — <epic title>](https://github.com/org/repo/issues/N)
**Delivery confidence:** <value> — <brief reason>

| Outcomes met | Partial | Confirmed unmet | Unverified |
| --- | --- | --- | --- |
| 1 | 1 | 0 | 1 |

_Upstream evidence assessment, not release completion. 3 criteria in total._

_Scope: 2 acceptance criteria, 1 definition-of-done item, counted separately._

- **Evidence established:** Tier-based pool selection routes paid-tier requests
  and merged on 2026-09-18 ([RHOAIENG-1234 AC1](...); [PR example-quota#520](...)).
- **Remaining work:** Per-tier metering is tracked but unimplemented; the
  counter increments on admission only ([RHOAIENG-1234 AC2](...);
  [issue example-quota#88](...)).
- **Decisions needed:** Whether a denied request is metered is unrecorded, so
  the retention clause cannot be checked ([RHOAIENG-1234 DoD1](...)).
- **Next actions:** Record the metering decision and link the owning work for
  the 1 criterion with none. No owner or date for these is recorded in the
  sources inspected.

**Trend:** since the last update posted here on 2026-10-01, outcomes met 1→3,
unverified 4→2.

**Scope:** 2 nested epics were recorded but not traversed
([org/repo#1445](...), [org/repo#1501](...)). Criteria owned by that work would
not appear here, so an unverified row is not evidence that the work is missing.

[Full assessment](https://durable.example/rollups/RHOAIENG-1234.md)
````

### The four bullets

**Fixed order, fixed labels, always all four.** A summary missing "Decisions
needed" is a different document, not a shorter one. The slug is what a
narrative claim is filed under; the label is what the reader sees.

| Slug | Label | Answers |
| --- | --- | --- |
| `evidence-established` | Evidence established | What the inspected sources show has been built |
| `remaining-work` | Remaining work | What is identified and outstanding |
| `decisions-needed` | Decisions needed | What nobody has decided, and what inspected evidence contradicts |
| `next-actions` | Next actions | What to do, with owners and dates only where a source named one |

A `confirmed-unmet` criterion belongs under **Decisions needed**, with what
refutes it — never under Remaining work, where "tracked and incomplete" would
file a thing found to be wrong alongside work still in flight. And the finding
raises a question; it does not answer one. "Confirm whether the criterion still
describes intended behaviour" is the item. "Reopen the work" and "revise the
criterion" are two possible answers to that question and neither is yours to
pick from an assessment row.

### Narrative, and what the model owes for it

The bullets carry prose the model wrote. Mechanical counts are the fallback for
a bullet nobody wrote, not the goal: a reader who wanted the tally has it two
lines above, and "4 criteria partly supported: AC1, AC3, SC2, DoD1" tells an EM
nothing about what the system now does.

Supply it as `assembly["narrative"]`, or as `--narrative narrative.json`:

```json
[
  {"bullet": "evidence-established",
   "text": "Tier-based pool selection routes paid-tier requests and merged on 2026-09-18",
   "refs": [{"sourceKey": "RHOAIENG-1234", "id": "AC1"}],
   "links": ["example-org/example-quota#520"]}
]
```

Several claims may share a bullet; they are rendered as consecutive sentences
in the order given, each with its own traceability tail.

`summary.py:narrative_problems` refuses the run when a claim cites a
requirement that is not in this assessment, cites no row at all, links an
artifact that is not evidence on any row it cites, is filed under
`evidence-established` while resting on an `unverified` row, or names a bullet
that does not exist. **Those checks establish traceability, not truth.** A
sentence that misreads what a merged PR does passes all of them. Whether the
evidence establishes the claim is a judgement and it stays with you.

### Readability at scale

Nine criteria and forty-nine criteria are the same document. Three rules keep
it that way, all enforced in `summary.py`:

- **A criterion is named explicitly in at most one bullet.** After that it is
  counted. The same eight ids under three headings reads as twenty-four
  problems, and the bullet that was meant to say what to *do* repeats what the
  reader already has.
- **At most three explicit references per bullet.** The rest collapse to counts
  grouped by owning issue: `RHAIGW-399 AC1, RHAIGW-399 AC6, RHAIGW-400 AC2, and
  7 more — 4 on RHAIGW-400, 3 on RHAIGW-401`. Past three, the enumeration stops
  being a pointer and becomes the content. The tail carries no brackets of its
  own; the whole trace is already parenthesised after the sentence.
- **Every reference is qualified with its source key.** `AC1` is ambiguous
  across six Jira issues. `RHAIGW-399 AC1` is not. This holds in both outputs,
  including the collapsed-row line in the full assessment.

The complete per-criterion lists live in the full assessment, which is the
document that has room for them.

### The rest of the contract

- **150–250 words** of prose; URLs and the tables are scanned, not read, so
  neither counts. Over budget, the renderer names fewer criteria per bullet.
  It never truncates narrative and never drops a bullet — `result.json` reports
  `summaryWordBudget.within` instead, because a half-finished claim is worse
  than a long one.
- **`_Scope:_` counts AC, SC and DoD separately** and never sums them. There is
  no feature-completion percentage in either output.
- **1–2 targeted links per bullet**, with descriptive labels (`PR
  example-gateway#1605`, not a bare URL and not "click here"). The full
  inventory stays in the detailed assessment.
- **What a link points at depends on the outcome.** For `met` or `partial`, the
  artifact that landed the work — strongest first: merged PR, closed issue, open
  PR. For anything else, the issue that *owns* the work — open issue first,
  merged PR last. A merged PR hung off an unverified criterion reads as though
  the criterion shipped.
- **Criteria have no anchors in Jira**, so a criterion is pointed at by linking
  the parent issue and naming the criterion in the link text: `RHOAIENG-1234 SC5`.
  This needs `jira.site` in the assembly; without it the text is unlinked rather
  than linked to a guess.
- **The trend names its baseline in the reader's terms** — "the last update
  posted here on <date>", or "the last assessment on <date>, which was not
  posted here". Movement since the last comment and movement since the last
  time anyone looked are different claims, and "draft snapshot" is this tool's
  vocabulary, not a Jira reader's.
- **A changed criteria set is reported as scope, not movement.** When the total
  moved, the trend line gives the scope change and says the outcome counts are
  not comparable across it. `unverified 4→21` beside "since the last
  assessment" reads as twenty-one things going wrong; the like-for-like figure
  over criteria present in both runs is in the full assessment, which has room
  to qualify it.
- **The scope caveat is conditional and names what it omits** — unreadable
  sources, nested epics recorded but not traversed, or incomplete traversal,
  each by reference. It exists so an unverified count is not read as a finding
  about the work.
- **The "Full assessment" link is omitted unless a durable, reader-accessible
  URL was supplied.** A local path is dropped, not published; `links.py` and
  `assemble.cross_check` both refuse one.
- **No existence claim is left unscoped.** "No upstream issue covers this" is a
  statement about every repository on GitHub, made from a walk of one epic.
  `assemble.unscoped_claims` rejects it in either output; write "no upstream
  work in the traversed set is linked to …".
- **No collection diagnostics, no authentication notes, no per-criterion
  analysis.** Those are what the full assessment is for.

## Structure of the HTML full assessment

`jgr/htmlreport.py` emits it; `jgr/htmlassets.py` holds the stylesheet and the
script. Written when `rollup.py assemble` or `rollup.py rerender` is given
`--html <path>`. Nothing in either module classifies a criterion, decides what
evidence shows, or writes prose — every sentence of judgement in the output
arrived in the assembly, which is what makes re-rendering an old snapshot safe.

Seven sections, in this order:

| | Contains |
| --- | --- |
| **Header** | Requirement title, linked Jira key, assessment date, draft-or-published state, the linked upstream epics, and the expand/collapse control |
| **Limitations banner** | Incomplete traversal, unreadable sources, an uncomputable coverage ratio, a missing mapping. **Omitted entirely when there are none** |
| **Overview** | Left: outcome counts by requirement type. Right: release target, baseline, scope change, comparable movement, child-issue ratio |
| **Decisions and follow-up** | The narrative claims under their four bullet labels, with qualified criterion references and the links they were validated against; then dependencies a source actually named |
| **Requirement review** | Criteria grouped by source Jira issue, searchable and filterable, each row expanding to its evidence |
| **Changes since baseline** | Outcome movement for matched requirements, scope change kept separate |
| **Collection scope and limitations** | Sources read, repositories traversed, nested epics skipped, access failures, timestamps, rules and schema version |

What the HTML is strict about, beyond the shared tally:

- **No combined completion figure.** The outcome card is counts by type with no
  denominator and no percentage, because the three types are not interchangeable
  units of delivery.
- **Movement is withheld rather than approximated.** When the requirement
  inventory changed, the card says numerical movement is unavailable and why,
  instead of printing a ratio whose denominator moved. Scope growth is labelled
  scope, never progress.
- **Missing is said to be missing.** No field falls back to a plausible value.
  An unrecorded release target reads "Not recorded on the Jira issue"; an
  uninspected downstream step reads "Not inspected" and says that is not
  confirmation none is required.
- **Scope change is reported only against a baseline.** A first run's diff lists
  every criterion as added, which is true of the file and false of the work.
- **Evidence state is glossed from what collection records** — `planned`,
  `in progress`, `in review`, `merged`, `tested`. *Documented* and *test
  present* are not states this pipeline can distinguish, so they are never
  reported, and the collection section says so.
- **File references are commit-pinned or omitted.** A path without a recorded
  commit points at whatever that file says today, which is not what was read.

### Safety properties of the HTML

Jira and GitHub content is untrusted input. The renderer treats it that way:

- Every source string goes through `htmlreport.text()` → `html.escape(...,
  quote=True)`. There is no second path, because there is **no embedded JSON
  payload and no client-side templating** — every row is static escaped markup
  carrying `data-*` attributes, and the script only toggles `hidden` and `open`.
- Every URL goes through `links.safe_url()`, which admits absolute `http` and
  `https` and nothing else. A `javascript:`, `data:` or `file:` ref recorded
  upstream renders as inert text rather than as a link. External links carry
  `rel="noreferrer noopener"`.
- `links.unpublishable()` runs over the finished document in
  `assemble.cross_check`, so a cache path or a home directory fails the run
  rather than shipping in a file someone forwards.
- Nothing leaves the document at runtime: no font import, no CDN, no `fetch`,
  one inline `<script>`. It opens on a laptop with no network.

Interaction is native and keyboard-accessible: `<details>`/`<summary>` rows that
work with JavaScript off, a `<input type="search">`, two `<select>`s and a
checkbox. The live count and each group heading both update under a filter —
a heading left at its unfiltered total is how a reader concludes a source has
nine criteria needing attention when it has two. The print stylesheet opens
every row, unclamps the finding text, drops the controls, and appends each
link's URL in parentheses.

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

| Outcomes met | Partial | Confirmed unmet | Unverified |
| --- | --- | --- | --- |
| 0 | 0 | 0 | 2 |

| Requirement | Outcome | Evidence | Evidence state | Coverage | Gap / next validation step |
| --- | --- | --- | --- | --- | --- |
| AC1 (RHOAIENG-1234) "<verbatim text>" | Unverified | — | — | Unable to assess — upstream mapping missing | Link the upstream epic |
| AC1 (RHOAIENG-1240) "<verbatim text>" | Unverified | — | — | Unable to assess — upstream mapping missing | Link the upstream epic |

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
- Every Coverage cell is `Unable to assess`, the same wording in every row, with
  the same Gap in every row. Not `No evidence found`, which claims a search
  happened. The Gap names the action the specific failure calls for — add the
  link, or get read access to the link already there.
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
qualification outstanding. When nothing upstream was observed the status is
`Unknown`, qualified by the reason (`references/pipeline.md` has the four), and
it is never softened to `Not started`.

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

Below the caption, `render.type_breakdown` splits the same four outcomes by
type whenever more than one type is present. It has no total column and no
percentage on purpose: eight met acceptance criteria beside zero met success
criteria is a different situation from the reverse, both read as "8 of 16", and
dividing across the types would produce exactly the feature-completion number
this whole design refuses to emit.

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
| Requirement | `AC<n>` / `SC<n>` / `DoD<n>` / `REQ<n>` + `(SOURCE-KEY)`, linked to the parent Jira when `jira.site` is known, then the text **in quotes, verbatim** |
| Outcome | `Met` / `Partial` / `Confirmed unmet` / `Unverified` — derived from Coverage, never set by hand except a declared `confirmed-unmet` |
| Evidence | Issue and PR references with merge dates, attributed to their epic when more than one is in scope; `—` when nothing is mapped |
| Evidence state | One of: planned, in progress, in review, merged, tested; `—` when nothing is mapped |
| Coverage | One of the four assessments, an em dash, then what it rests on |
| Gap / next validation step | What remains, and who or what resolves it |

Outcome and Coverage are the same judgement at two resolutions: Outcome is what
gets counted in the table above and carried into the Jira summary; Coverage is
the sentence that makes it checkable. They cannot disagree, because the renderer
derives the first from the second.

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

**Downstream qualification** — a three-state table, then one bullet per
requirement that still needs downstream integration or qualification, including
those whose upstream coverage is `Evidence found`. Merged upstream is not
shipped downstream, and the reader needs the two separated.

The three states are not interchangeable and the labels are deliberately long:

| `downstream.state` | Rendered as | Means |
| --- | --- | --- |
| `unknown` | Not inspected | Nobody looked. An open question. |
| `pending` | Inspected; no qualifying evidence found | Somebody looked and found nothing. A negative result. |
| `confirmed` | Verified, with evidence | A named build, payload or run establishes it. |

Reading the first as the second overstates what is known; reading the second as
the first understates it. `unknown` is the default and stays there until a
source says otherwise — a criterion nobody checked downstream is not pending.

Neither this table nor the outcome counts is a release-readiness verdict. That
is what `Delivery confidence` is for, and it is `Not assessed` for as long as
any of this is outstanding.

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

Only after the user approves the summary, and only for the string handed to the
Jira comment tool. **What is posted is the summary, never the full assessment.**
Nothing in this section applies to what you show in the conversation.

**Check the tool, do not assume the format.** The Atlassian MCP tool in use here
is `addOrEditJiraIssueComment`, and its schema documents `commentBody` as
**Markdown by default**, with `contentFormat: "markdown" | "html"` selecting
between the two. Wiki markup is not an input format for it. So the normal path
is to send `jira-summary.md` as written, with no conversion at all.

That is a fact about this tool, not about Jira. A different site, a different
MCP server, or a REST call goes through a different door — the REST v3 comment
API takes Atlassian Document Format and nothing else. Re-read the schema that
arrived with the tool definition rather than trusting this paragraph, and say in
one line which format you sent, so a mis-render is diagnosable instead of
mysterious.

**Never send the GFM draft verbatim** to a target that takes wiki markup. `###`
and `**bold**` are literal text there, the `| --- |` separator row renders as a
table row of dashes, and the result looks like a bug in the issue rather than a
report.

`rollup.py convert --in jira-summary.md --target gfm|html|wiki|plain|adf`
applies the rules below. The decision is yours; the transcription is not worth
doing by hand. The subsections that follow describe what `convert` produces, and
are what to check a surprising payload against.

### If the target takes HTML

`--target html` is the fallback when Markdown comes back mangled. It emits only
the element set the Atlassian editor accepts: `<h1>`–`<h6>`, `<p>`, `<ul><li>`,
`<table><thead><tr><th>` / `<tbody><tr><td>`, `<a href>`, `<strong>`, `<em>`,
`<code>`, `<hr>`. Cell text is escaped before any of those are re-inserted, so
a criterion quoting `<script>` posts as text rather than markup.

Layout wrappers are not in the set. Jira refuses `<section data-type="layout-*">`
and the comment fails rather than degrading, which is why the converter never
emits one.

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

The coverage table is six columns wide and is the first thing to render badly on
an ADF site or in a narrow comment pane. The fallback is one block per
requirement, same fields, same order — never drop a field to make the table fit:

```
AC1 (RHOAIENG-1234) "Requests for a tiered model are routed to the pool for that tier."
  Outcome: Met
  Evidence: example-org/example-gateway#413, PR #520 (merged 2026-09-18)
  State: merged
  Coverage: Evidence found — PR #520 implements tier-based pool selection.
  Gap: Downstream qualification pending.
```

This only arises for the full assessment, which is not posted. The summary has
one four-column table of integers and survives every target.

### What survives conversion unchanged

- Section order, section names, and which sections are present or omitted.
- Every verbatim criterion quote, its prefix, and its source key.
- The marker line's wording. It is matched as text when a later run looks for a
  prior rollup, so it has to survive in whatever markup was posted — which is
  also why the match is on the sentence, not on the italics around it.

If conversion would force any of those to change, send plain text instead. The
markup is the negotiable part.
