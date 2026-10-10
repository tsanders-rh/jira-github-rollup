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
    missing     ["org/repo#3", "org/other"]   -> 404
    forbidden   ["org/private"]               -> 403
    noSubIssues ["org/legacy"]                -> 404 on /sub_issues only

`noSubIssues` is the repo that has never had GitHub's sub-issue feature. It
404s that one endpoint while reading normally, which is the case where "no
sub-issues" and "we cannot tell" have to stay distinguishable.
"""

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
