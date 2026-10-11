#!/usr/bin/env python3
"""A stand-in for `gh`, driven by a JSON world file.

Pointed at by `GH_BIN` so the collector's real command construction is
exercised - the flags, the `--json` field lists, the `--paginate` calls and the
exit codes `gh pr checks` actually uses. Only the network is faked.

The world file is a dict of:

    issues      {"org/repo#1": {...gh issue view JSON...}}
    subIssues   {"org/repo#1": ["org/repo#2", ...]}
    timeline    {"org/repo#1": [...timeline events...]}
    prs         {"org/repo#9": {...gh pr view JSON...}}
    prFiles     {"org/repo#9": {...files/changedFiles/closingIssuesReferences...}}
    checks      {"org/repo#9": [{"name":..,"bucket":..}, ...]}
    searchPrs   {"org/repo#2": [...]}
    sources     {"org/repo@sha:path/to/file.py": "...file body..."}
    sourceDirs  ["org/repo@sha:path/to"]      -> the directory listing GitHub
                                                 returns for a path that is
                                                 not a file
    sourcesTooLarge ["org/repo@sha:big.bin"]  -> the empty-content payload
                                                 GitHub returns over 1MB
    missing     ["org/repo#3", "org/other"]   -> 404
    forbidden   ["org/private"]               -> 403
    noSubIssues ["org/legacy"]                -> 404 on /sub_issues only
    forbiddenSubIssues ["org/repo#3"]         -> 403 on /sub_issues only

`noSubIssues` is the repo that has never had GitHub's sub-issue feature. It
404s that one endpoint while reading normally, which is the case where "no
sub-issues" and "we cannot tell" have to stay distinguishable.

A `sources` key is `repo@revision:path`, the same string `followup.source_ref`
builds, so a test names the revision it expects to be read. A file present at
one revision and absent at another is spelled as two keys, which is the case
that catches a read against the wrong revision.
"""

import base64
import json
import os
import re
import sys


def world():
    with open(os.environ["GH_WORLD"], "r", encoding="utf-8") as handle:
        return json.load(handle)


def blocked(data, ref):
    repo = ref.split("#")[0]
    if ref in data.get("missing", []) or repo in data.get("missing", []):
        return "GraphQL: Could not resolve to an Issue with the number (404)"
    if ref in data.get("forbidden", []) or repo in data.get("forbidden", []):
        return "HTTP 403: Resource protected by organization SAML enforcement"
    return None


def fail(message, code=1):
    sys.stderr.write(message + "\n")
    sys.exit(code)


def emit(payload, code=0):
    sys.stdout.write(json.dumps(payload))
    sys.exit(code)


def emit_contents(data, repo, file_path, revision):
    """The four shapes `GET /repos/{repo}/contents/{path}` comes back as.

    A file, a directory listing, the empty-content payload for something too
    large to inline, and a 404. The reader has to tell them apart, so the fake
    has to be able to produce all four.
    """
    if repo in data.get("forbidden", []):
        fail("HTTP 403: Resource protected by organization SAML enforcement")
    ref = f"{repo}@{revision}:{file_path}"
    if ref in data.get("sourceDirs", []):
        emit([{"name": "a.py", "path": f"{file_path}/a.py", "type": "file"}])
    if ref in data.get("sourcesTooLarge", []):
        emit({"name": file_path.rsplit("/", 1)[-1], "path": file_path,
              "encoding": "none", "content": "", "size": 2_000_000})
    body = data.get("sources", {}).get(ref)
    if body is None:
        fail("HTTP 404: Not Found")
    emit(
        {
            "name": file_path.rsplit("/", 1)[-1],
            "path": file_path,
            "sha": revision,
            "encoding": "base64",
            "content": base64.b64encode(body.encode("utf-8")).decode("ascii"),
            "size": len(body.encode("utf-8")),
        }
    )


def main(argv):
    data = world()

    if argv[0] == "issue" and argv[1] == "view":
        number = argv[2]
        repo = argv[argv.index("--repo") + 1]
        ref = f"{repo}#{number}"
        problem = blocked(data, ref)
        if problem:
            fail(problem)
        issue = data.get("issues", {}).get(ref)
        if issue is None:
            fail("GraphQL: Could not resolve to an Issue with the number (404)")
        emit(issue)

    if argv[0] == "pr" and argv[1] == "view":
        number = argv[2]
        repo = argv[argv.index("--repo") + 1]
        ref = f"{repo}#{number}"
        problem = blocked(data, ref)
        if problem:
            fail(problem)
        fields = argv[argv.index("--json") + 1].split(",")
        if "files" in fields:
            payload = data.get("prFiles", {}).get(ref)
            if payload is None:
                fail("HTTP 404: Not Found")
            emit(payload)
        pr = data.get("prs", {}).get(ref)
        if pr is None:
            fail("GraphQL: Could not resolve to a PullRequest with the number (404)")
        emit(pr)

    if argv[0] == "pr" and argv[1] == "checks":
        number = argv[2]
        repo = argv[argv.index("--repo") + 1]
        ref = f"{repo}#{number}"
        checks = data.get("checks", {}).get(ref)
        if checks is None:
            fail("no checks reported on this branch")
        buckets = {check.get("bucket") for check in checks}
        code = 1 if "fail" in buckets else (8 if "pending" in buckets else 0)
        emit(checks, code)

    if argv[0] == "api":
        path = argv[1]
        contents = re.match(r"repos/([\w.-]+/[\w.-]+)/contents/(.+)\?ref=(.+)$", path)
        if contents:
            repo, file_path, revision = contents.groups()
            emit_contents(data, repo, file_path, revision)

        match = re.match(r"repos/([\w.-]+/[\w.-]+)/issues/(\d+)/(sub_issues|timeline)", path)
        if not match:
            fail("HTTP 404: Not Found")
        repo, number, kind = match.groups()
        ref = f"{repo}#{number}"
        problem = blocked(data, ref)
        if problem:
            fail(problem)
        if kind == "sub_issues":
            if repo in data.get("noSubIssues", []):
                fail("HTTP 404: Not Found (sub-issues unavailable)")
            # A readable issue whose sub-issue list is refused. Distinct from
            # `forbidden`, which blocks the issue too: this is the shape that
            # used to come back as "no children" and hide a whole branch.
            if ref in data.get("forbiddenSubIssues", []):
                fail("HTTP 403: Resource protected by organization SAML enforcement")
            refs = data.get("subIssues", {}).get(ref, [])
            emit(
                [
                    {
                        "number": int(child.split("#")[1]),
                        "repository_url": "https://api.github.com/repos/" + child.split("#")[0],
                    }
                    for child in refs
                ]
            )
        emit(data.get("timeline", {}).get(ref, []))

    if argv[0] == "search" and argv[1] == "prs":
        emit(data.get("searchPrs", {}).get(argv[2], []))

    fail(f"fakegh: unsupported command {' '.join(argv)}")


if __name__ == "__main__":
    main(sys.argv[1:])
