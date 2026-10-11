"""Bounded follow-up reads: one source file, at one revision, within budget.

The failure this exists for is specific. An assessment identifies a question
it could answer - "is this filter in the list the restriction applies to?" -
has an accessible file that answers it, does not open the file, and reports
the leftover uncertainty as a gap in the requirement. The reader is then told
the product is missing something, when what is missing is a read.

So the read has to be cheap enough to do and bounded enough to be safe:

* **One file, named.** There is no search here and no directory walk. A
  follow-up follows a concrete reference the evidence already produced - a
  path in a PR's changed-file list, a symbol a description names.
* **A revision, required.** `gh` would happily serve the default branch, which
  is a different document from the one the merged PR produced. A read whose
  revision is not stated proves nothing about the evidence it was done for.
* **A budget, enforced.** `BUDGET` distinct reads per Jira key. Past that the
  command stops answering and says so, and the honest report of what follows
  is an inspection limitation, not a requirement gap.
* **Deduplicated.** A file already read at a revision is served from the cache
  and costs nothing. Re-reading the same source to re-ask the same question is
  the other half of an unbounded audit.

The ledger lives beside the rest of the cache, under `cache/<JIRA-KEY>/`, and
is as disposable as the cache is: deleting it resets the budget, which is a
decision a person makes, not one the pipeline makes for itself.
"""

from __future__ import annotations

import base64
import os

from . import util

# Per Jira key, per cache. Twelve is chosen to be enough for the follow-ups a
# real criterion generates - a definition, its registration, the error path,
# and a test, which is four, across two or three contested criteria - and
# small enough that it cannot become a repository audit. Raise it with
# `--budget` for one command when a run genuinely needs more, and say in the
# report that you did.
BUDGET = 12

LEDGER = "followups.json"


def source_ref(repo, path, revision):
    """How a source read is named everywhere: in the cache, the ledger, the report."""
    return f"{repo}@{revision}:{path}"


class Ledger:
    """What has been read this run, and how much budget is left."""

    def __init__(self, cache, budget=BUDGET):
        self.path = os.path.join(cache.root, LEDGER)
        self.budget = budget
        self.reads = []
        if os.path.exists(self.path):
            try:
                stored = util.read_json(self.path)
            except (ValueError, OSError):
                stored = None
            if isinstance(stored, dict):
                self.reads = list(stored.get("reads") or [])

    @property
    def spent(self):
        return len(self.reads)

    @property
    def remaining(self):
        return max(0, self.budget - self.spent)

    def has(self, ref):
        return any(read.get("ref") == ref for read in self.reads)

    def record(self, ref, repo, path, revision, sha, chars):
        if self.has(ref):
            return
        self.reads.append(
            {
                "ref": ref,
                "repo": repo,
                "path": path,
                "revision": revision,
                "sha": sha,
                "chars": chars,
                "at": util.iso(util.utcnow()),
            }
        )
        util.write_json(self.path, {"budget": self.budget, "reads": self.reads})


def decode(payload):
    """The file body out of a contents response, or None with a reason.

    GitHub answers this endpoint three ways and only one of them is a file: a
    directory comes back as a list, a file over 1 MB comes back with an empty
    `content` and a download URL, and a file comes back base64-encoded. The
    first two are inspection limitations and have to be reported as such
    rather than read as an empty file.
    """
    if isinstance(payload, list):
        return None, "that path is a directory, not a file; name the file that defines the symbol"
    if not isinstance(payload, dict):
        return None, "the contents response was not a file object"
    encoding = payload.get("encoding")
    content = payload.get("content")
    if encoding != "base64" or not content:
        if payload.get("size") and not content:
            return None, (
                f"the file is {payload['size']} bytes, which this endpoint will not inline; "
                "read the relevant part through the pull request's changed files instead"
            )
        return None, f"the contents response carried no base64 body (encoding {encoding!r})"
    try:
        return base64.b64decode(content).decode("utf-8", "replace"), None
    except (ValueError, TypeError) as exc:
        return None, f"the file body could not be decoded ({type(exc).__name__})"


def read(gh, cache, repo, path, revision, budget=BUDGET):
    """Fetch one file at one revision, or say why it could not be inspected.

    Always returns a payload, never raises, and `inspected` is the field that
    matters: false means the question stands unanswered and the reason is an
    inspection limitation the report has to carry, not a silent empty read.
    """
    ref = source_ref(repo, path, revision)
    ledger = Ledger(cache, budget)
    base = {
        "ref": ref,
        "repo": repo,
        "path": path,
        "revision": revision,
        "budget": {"limit": ledger.budget, "spent": ledger.spent, "remaining": ledger.remaining},
    }

    cached = cache.read("source", ref)
    if cached is not None:
        # Already paid for. Re-reading it is how a bounded follow-up turns
        # into a loop, so this neither spends budget nor asks GitHub again.
        return dict(base, inspected=True, reused=True, body=cached.get("body") or "",
                    sha=cached.get("sha"), path_in_cache=cache.path_for("source", ref))

    if ledger.remaining <= 0:
        return dict(
            base,
            inspected=False,
            reused=False,
            limitation=(
                f"the follow-up retrieval budget of {ledger.budget} source reads for this run is "
                f"spent, so {path} at {revision} was not inspected. Record this as an inspection "
                "limitation on the clause it would have settled, or re-run the command with "
                "--budget raised and say in the report that you did"
            ),
            reason="budget",
        )

    result = gh.file_contents(repo, path, revision)
    if not result.ok:
        return dict(
            base,
            inspected=False,
            reused=False,
            limitation=(
                f"{path} at {revision} in {repo} could not be read ({result.error}). Record this "
                "as an inspection limitation; it is not evidence about the behaviour"
            ),
            reason=result.status or "error",
        )

    body, problem = decode(result.data)
    if body is None:
        return dict(base, inspected=False, reused=False,
                    limitation=f"{path} at {revision} in {repo}: {problem}", reason="unreadable")

    sha = (result.data or {}).get("sha")
    cache.put("source", ref, {"repo": repo, "path": path, "revision": revision,
                              "sha": sha, "body": body})
    ledger.record(ref, repo, path, revision, sha, len(body))
    base["budget"] = {"limit": ledger.budget, "spent": ledger.spent, "remaining": ledger.remaining}
    return dict(base, inspected=True, reused=False, body=body, sha=sha,
                path_in_cache=cache.path_for("source", ref))
