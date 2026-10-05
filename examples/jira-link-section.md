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

The skill will roll up both. If it finds multiple epics that look unrelated and
they were not listed this way, it asks before merging them.

## Also recognized

The skill falls back through these in order, so an existing issue usually works
without reformatting:

1. The `Upstream Development` description section (above).
2. **Jira remote / web links** pointing at `github.com` — the "Link → Web Link"
   dialog. Use a label like `Upstream epic` so a human reading the issue can
   tell what it is.
3. Any bare `github.com/<org>/<repo>/issues/<n>` URL elsewhere in the description.
4. GitHub URLs in comments, most recent first.

Option 2 is the most discoverable for people who are not reading the raw
description, and it survives description rewrites. Option 1 is the most explicit.
Using both is fine — the skill de-duplicates.

## What does not work

| Written as | Why it fails |
| --- | --- |
| `example-org/example-gateway#412` | Shorthand without a URL is not matched in Jira text. |
| A link to the epic's *project board* | Boards are not issues; there are no children to traverse. |
| A link to a milestone or release page | Same — no epic body, no sub-issue graph. |
| A link to a PR instead of the epic | Rolls up one PR, not the requirement. |
| Only an epic title, no link | The skill stops and asks. It will not search by title. |

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
