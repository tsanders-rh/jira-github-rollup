# Example: linking a GitHub epic from a Jira issue

This is the **manual** step. A human decides which GitHub epic corresponds to a
downstream requirement and records that decision on the Jira issue. The skill
reads what you write here; it never guesses.

Everything below is illustrative — placeholder orgs, repos, and issue keys.

## Recommended: a dedicated description section

Add this near the bottom of the Jira issue description. The heading text
`Upstream Development` is what the skill looks for first.

```
h2. Upstream Development

Epic: https://github.com/example-org/example-gateway/issues/412

Upstream work for this requirement is tracked in the epic above. Child issues
may live in other repositories under example-org.
```

That is the whole contract: a recognizable heading and a full GitHub issue URL.

### Multiple epics

Some requirements genuinely span two upstream efforts. List them explicitly:

```
h2. Upstream Development

Epic (data plane): https://github.com/example-org/example-gateway/issues/412
Epic (control plane): https://github.com/example-org/example-controller/issues/87
```

**The skill rolls up all of them.** Multiple links in this section are a mapping,
not a conflict — it will not ask you to pick one, and it will not quietly use the
first. Each child, PR, and piece of evidence stays attributed to the epic it came
from, and the `Source epic` line lists both.

The parenthetical labels are optional but worth writing: they end up giving the
reader a reason why two epics are in scope.

It asks for clarification in narrower cases — when the only GitHub URLs it can
find are incidental ones (a bare link in the description body, a link in a
comment) and there is more than one, or when a URL points at a PR, board, or
milestone rather than an issue. In both cases it tells you what it found and
where, rather than deciding for you.

You can also supply the link in the request itself — "roll up RHOAIENG-1234
against https://github.com/example-org/example-gateway/issues/412" — which counts
as an explicit mapping for that run. It does not get written back to the Jira;
the skill makes no Jira edits beyond an approved comment.

## Also recognized

An existing issue usually works without reformatting. The skill reads all of
these, but it treats two of them as a deliberate mapping and two as a lucky find:

| | Source | Treated as |
| --- | --- | --- |
| 1 | The `Upstream Development` description section (above) | Explicit mapping |
| 2 | **Jira remote / web links** to `github.com` — the "Link → Web Link" dialog — labelled `Upstream epic` or similar | Explicit mapping |
| 3 | Any bare `github.com/<org>/<repo>/issues/<n>` URL elsewhere in the description | Incidental |
| 4 | GitHub URLs in comments, most recent first | Incidental |

Everything in the explicit tier is rolled up, all of it, without asking. The
incidental tier is a fallback: used when nothing explicit exists, flagged in the
draft as unconfirmed, and queried rather than merged in when there are several or
when it would add epics beyond the explicit set. A link someone dropped in a
comment two years ago is not the same statement as a link in the Upstream
Development section, and the skill does not pretend otherwise.

Option 2 is the most discoverable for people who are not reading the raw
description, and it survives description rewrites. Option 1 is the most explicit.
Using both is fine — the skill de-duplicates.

## If you link nothing

The skill does not refuse to run. It produces a **partial rollup**: the Jira
scope, the child requirements, every criterion quoted verbatim with its type and
source, and `Unable to assess — upstream mapping missing` against each one. Its
status line is `Unknown — upstream mapping missing`, and it closes with a
`What is needed` section naming the one thing that would complete it.

What it will not do is read your missing link as bad news. A requirement with no
recorded epic may be finished, in flight, or untouched — nothing the skill can
reach distinguishes those, so the draft says the mapping is missing and stops
there. It never writes "not started" or "no progress", and it never goes looking
for an epic whose title sounds right.

## What does not work

| Written as | Why it fails |
| --- | --- |
| `example-org/example-gateway#412` | Shorthand without a URL is not matched in Jira text. |
| A link to the epic's *project board* | Boards are not issues; there are no children to traverse. |
| A link to a milestone or release page | Same — no epic body, no sub-issue graph. |
| A link to a PR instead of the epic | Rolls up one PR, not the requirement. The skill names it and asks for the epic issue. |
| Only an epic title, no link | The skill will not search by title. You get the partial rollup described below, and a request for the URL. |

## Requirements: criteria, success criteria, and definition of done

The rollup also reports, statement by statement, what upstream evidence exists
for each requirement on the issue. That only works if the Jira states them
explicitly — the skill quotes what is there and never writes a criterion of its
own.

It reads a description section headed `Acceptance Criteria`, `Success Criteria`,
or `Definition of Done`; a dedicated acceptance-criteria custom field if the site
has one; `Given / When / Then` blocks; and the same sources on sub-tasks and
child requirements, one level down.

```
h2. Acceptance Criteria

# Requests for a tiered model are routed to the serving pool configured for that tier.
# An unknown tier is rejected with HTTP 400, and tier configuration changes take effect without a gateway restart.
# Routing decisions, including denials, are recorded in the metering stream within 60 seconds.
# Streaming responses are subject to the same tier enforcement as non-streaming responses.

h2. Definition of Done

# The admin guide documents tier configuration, and the gateway logs a deprecation warning for the legacy per-model pool field for at least one release before removal (release count TBD with product).
```

### The three headings stay three headings

`Acceptance Criteria`, `Success Criteria`, and `Definition of Done` are different
commitments — usually made by different people, and acted on differently when
they are missed. The skill keeps them apart end to end: IDs are prefixed `AC`,
`SC`, and `DoD`, numbered separately within each source issue, and the rollup's
counts line breaks them out by type. It never adds them up and calls the total
acceptance criteria — the block above is four acceptance criteria and one
definition-of-done item, not five acceptance criteria.

A criterion list under no recognized heading is kept too, prefixed `REQ` and
labelled unlabelled — reported rather than silently reclassified as acceptance
criteria.

IDs are assigned in order of appearance and tagged with the issue they came from,
so a criterion inherited from a child requirement is attributed to that child.
[`sample-rollup.md`](sample-rollup.md) shows what these five statements come back
as, alongside a sixth inherited from a child requirement.

### What makes a statement usable

- **Checkable wording.** "Rejected with HTTP 400" can be matched against a PR
  and a test. "Performance should be acceptable" cannot — with nothing checkable
  in it at all, the skill keeps it verbatim, reports `Unable to assess`, and asks
  for a restatement.
- **One behavior per statement.** AC2 above has two clauses, and in
  `sample-rollup.md` it comes back `Partial evidence` — the rejection path has a
  test, the reload path has nothing. Upstream work tends to land one clause at a
  time, so a compound criterion tends to sit at partial for a long while.
- **A TBD costs you one clause, not the whole statement.** DoD1 above pairs two
  checkable requirements (the admin guide, the deprecation warning) with an
  undecided one (how many releases). The skill assesses the first two against the
  evidence and reports the third as a named decision for product — it does not
  discard the row because one number is open. Writing the TBD down explicitly is
  better than leaving it implicit: it is what tells the skill, and the reader,
  that someone still owes an answer.

If the issue has none of these at all, the rollup says so and names where it
looked. It does not fall back to inferring criteria from the description.

## On the GitHub side

For the traversal to find anything, the epic needs children expressed in a way
GitHub exposes. Any of these work, and they can be mixed:

- **Native sub-issues** — the GitHub Issues hierarchy feature. Best signal.
- **A task list in the epic body** referencing issues:

  ```markdown
  - [x] example-org/example-gateway#413 — request routing
  - [ ] example-org/example-controller#88 — CRD plumbing
  - [ ] https://github.com/example-org/example-tests/issues/15 — e2e coverage
  ```

- **Cross-references** from children back to the epic (`Tracked by #412`).

Children in other repositories are expected and handled — note that
`example-org/example-controller#88` above lives in a different repo than the
epic. Whoever maintains the epic should make sure those cross-repo children are
actually listed, since nothing else will surface them.

Linking PRs to their child issue (`Closes #413`) is what lets the rollup report
merge state rather than just open/closed.
