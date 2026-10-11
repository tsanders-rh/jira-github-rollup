"""Thin read-only wrapper around the `gh` CLI.

Only read verbs are ever constructed here: `issue view`, `pr view`,
`pr checks`, `api` GETs, and `search prs`. There is no code path in this file
that creates, edits, or comments on anything, and adding one would be a change
to the skill's constraints, not a refactor.

Authentication is whatever `gh` already has. No new credential is introduced.
"""

from __future__ import annotations

import json
import os
import subprocess

NOT_FOUND = ("404", "not found", "could not resolve", "resolve to a repository")
FORBIDDEN = ("403", "forbidden", "must have admin", "saml", "sso")


class GhResult:
    def __init__(self, ok, data=None, error=None, status=None):
        self.ok = ok
        self.data = data
        self.error = error
        self.status = status  # "unreadable" | "forbidden" | "error" | None

    def __bool__(self):
        return self.ok


class Gh:
    def __init__(self, binary=None, timeout=120, dry_run=False):
        self.binary = binary or os.environ.get("GH_BIN", "gh")
        self.timeout = timeout
        self.dry_run = dry_run
        self.calls = []

    def _classify(self, stderr: str) -> str:
        low = (stderr or "").lower()
        if any(token in low for token in NOT_FOUND):
            return "unreadable"
        if any(token in low for token in FORBIDDEN):
            return "forbidden"
        return "error"

    def run(self, args, allow_nonzero=()):
        """Run `gh <args>` and parse stdout as JSON.

        `allow_nonzero` exists for `gh pr checks`, which exits 8 when checks are
        pending and 1 when one failed. Those are findings, not failures, and the
        JSON on stdout is the answer.
        """
        self.calls.append(args)
        if self.dry_run:
            return GhResult(False, error="dry run", status="error")
        try:
            proc = subprocess.run(
                [self.binary, *args],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except FileNotFoundError:
            return GhResult(False, error=f"{self.binary} not found on PATH", status="error")
        except subprocess.TimeoutExpired:
            return GhResult(False, error=f"timed out after {self.timeout}s", status="error")

        usable = proc.returncode == 0 or proc.returncode in allow_nonzero
        if not usable and not proc.stdout.strip():
            return GhResult(
                False,
                error=(proc.stderr or "").strip().splitlines()[0] if proc.stderr else "gh failed",
                status=self._classify(proc.stderr),
            )
        text = proc.stdout.strip()
        if not text:
            return GhResult(True, data=None)
        try:
            return GhResult(True, data=json.loads(text))
        except ValueError:
            # `gh api --paginate` concatenates JSON arrays across pages.
            merged = []
            decoder = json.JSONDecoder()
            index = 0
            while index < len(text):
                while index < len(text) and text[index] in " \t\r\n":
                    index += 1
                if index >= len(text):
                    break
                try:
                    chunk, index = decoder.raw_decode(text, index)
                except ValueError:
                    return GhResult(False, error="unparseable gh output", status="error")
                merged.extend(chunk if isinstance(chunk, list) else [chunk])
            return GhResult(True, data=merged)

    # --- read verbs -----------------------------------------------------

    def issue_view(self, repo, number, fields):
        return self.run(
            ["issue", "view", str(number), "--repo", repo, "--json", ",".join(fields)]
        )

    def sub_issues(self, repo, number):
        return self.run(["api", f"repos/{repo}/issues/{number}/sub_issues", "--paginate"])

    def timeline(self, repo, number):
        return self.run(["api", f"repos/{repo}/issues/{number}/timeline", "--paginate"])

    def pr_view(self, repo, number, fields):
        return self.run(["pr", "view", str(number), "--repo", repo, "--json", ",".join(fields)])

    def pr_checks(self, repo, number):
        return self.run(
            [
                "pr",
                "checks",
                str(number),
                "--repo",
                repo,
                "--json",
                "name,state,bucket,workflow,link,completedAt",
            ],
            allow_nonzero=(1, 8),
        )

    def file_contents(self, repo, path, revision):
        """One source file at one revision. Still a GET; still read-only.

        `revision` is required rather than defaulting to the default branch.
        The question a follow-up read answers is what the code did at the point
        the evidence was produced, and today's `main` is a different document
        that happens to live at the same path.
        """
        return self.run(["api", f"repos/{repo}/contents/{path}?ref={revision}"])

    def search_prs(self, query):
        return self.run(
            ["search", "prs", query, "--json", "number,title,state,url,repository", "--limit", "30"]
        )
