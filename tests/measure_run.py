#!/usr/bin/env python3
"""Measure the LLM-facing input for a full run and an incremental run.

Runs the same fixture the behaviour tests use, then reports the size of the
things a model would actually read. What is deliberately *not* counted as
LLM-facing is the raw-response cache: it is on disk precisely so that it never
enters context, and it is reported separately as the quantity that used to.

Output is tokens when a tokenizer is importable, bytes and characters
otherwise, labelled either way. Nothing here converts bytes to tokens by
dividing: an estimate is not a measurement.

    python3 tests/measure_run.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, ".claude", "skills", "jira-github-rollup")
SCRIPTS = os.path.join(SKILL, "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from jgr import measure as measure_mod  # noqa: E402

import test_rollup as fixture  # noqa: E402


def git_show(revision, path):
    proc = subprocess.run(
        ["git", "-C", ROOT, "show", f"{revision}:{path}"], capture_output=True, text=True
    )
    return proc.stdout if proc.returncode == 0 else None


def tree_bytes(directory):
    total = 0
    for base, _, names in os.walk(directory):
        for name in names:
            total += os.path.getsize(os.path.join(base, name))
    return total


def realistic_world():
    """The same shape, at the size a real epic actually is.

    The minimal fixture understates the raw side badly: its issue bodies are one
    sentence and its timelines are empty, which is not what `gh` returns for an
    epic with a dozen children. This one has twelve children across two
    repositories, multi-paragraph bodies, and the timeline traffic that comes
    with them.
    """
    world = fixture.base_world()
    body = ("## Background\n\n" + ("Context paragraph about the work. " * 40) + "\n\n"
            "## Plan\n\n" + ("- a planned step with some detail\n" * 25) + "\n"
            "## Notes\n\n" + ("Further discussion of the approach. " * 40))
    world["issues"][fixture.EPIC]["body"] = body
    children, prs = [], []
    for index in range(12):
        repo = "example-org/example-quota" if index % 3 else "example-org/example-meter"
        child = f"{repo}#{400 + index}"
        pr = f"{repo}#{600 + index}"
        closed = index % 2 == 0
        world["issues"][child] = fixture.issue(
            child, f"Child task {index}",
            state="CLOSED" if closed else "OPEN",
            reason="COMPLETED" if closed else None,
            closed="2026-09-18T10:00:00Z" if closed else None,
            body=body,
        )
        world["prs"][pr] = fixture.pull(pr, merged="2026-09-18T09:00:00Z" if closed else None)
        world["prFiles"][pr] = {
            "changedFiles": 18,
            "files": [{"path": f"pkg/area{n}/file{n}.go"} for n in range(18)],
            "closingIssuesReferences": [],
        }
        world["checks"][pr] = [{"name": f"check-{n}", "bucket": "pass"} for n in range(14)]
        # A real timeline is mostly labels, mentions and renames.
        world["timeline"][child] = [
            {"event": "labeled", "label": {"name": f"area/{n}"}, "actor": {"login": "someone"},
             "created_at": "2026-09-01T00:00:00Z"}
            for n in range(20)
        ] + [fixture.crossref(pr)]
        children.append(child)
        prs.append(pr)
    world["subIssues"][fixture.EPIC] += children
    world["timeline"][fixture.EPIC] = world["timeline"].get(fixture.EPIC, [])
    return world


def run(home, world=None):
    """One full run then one incremental run, returning the artifact paths."""
    os.environ["JGR_HOME"] = home
    os.environ["GH_BIN"] = os.path.join(ROOT, "tests", "fakegh.py")
    os.environ["GH_WORLD"] = os.path.join(home, "world.json")
    with open(os.environ["GH_WORLD"], "w", encoding="utf-8") as handle:
        json.dump(world or fixture.base_world(), handle)

    from jgr import assemble as assemble_mod
    from jgr import cache as cache_mod
    from jgr import collect as collect_mod
    from jgr import diff as diff_mod
    from jgr import snapshots as snapshots_mod
    from jgr.ghclient import Gh

    results = {}
    for label, generated_at in (("full", "2026-10-01T00:00:00Z"), ("incremental", "2026-10-08T00:00:00Z")):
        collector = collect_mod.Collector(fixture.KEY, gh=Gh(), cache=cache_mod.Cache(fixture.KEY))
        manifest = collector.inventory(
            [{"ref": fixture.EPIC, "linkSource": "upstream-development-section"}]
        )
        manifest = collector.evidence(
            manifest, [pr["ref"] for child in manifest["children"] for pr in child["prs"]]
        )
        baseline = snapshots_mod.select_baseline(fixture.KEY)
        plan = diff_mod.plan(
            baseline, manifest, fixture.REQUIREMENTS,
            [{"ref": fixture.EPIC, "linkSource": "upstream-development-section"}],
        )
        assessments = (
            [
                fixture.assessment("AC1", "Evidence found",
                                   [{"ref": fixture.PR_A, "kind": "pr", "state": "merged",
                                     "at": "2026-09-18T09:00:00Z"}], "merged", "confirmed"),
                fixture.assessment("AC2", "No evidence found", [], "none"),
            ]
            if label == "full"
            else []
        )
        built = assemble_mod.build(
            {
                "jira": {"key": fixture.KEY, "summary": "Tiered quota", "status": "In Progress"},
                "mappings": [
                    {
                        "ref": fixture.EPIC,
                        "url": f"https://github.com/{fixture.EPIC}",
                        "linkSource": "upstream-development-section",
                    }
                ],
                "manifest": manifest,
                "diff": plan,
                "baselineSnapshot": baseline.get("snapshot"),
                "requirements": fixture.REQUIREMENTS,
                "assessments": assessments,
                "summary": "Upstream work is partly complete.",
                "generatedAt": generated_at,
            }
        )
        # What a reassessment has to read: the bodies of the candidate
        # artifacts, through `excerpt`. Nothing to reassess means nothing to
        # read, and that is where an incremental run actually saves.
        excerptable = 0
        if plan["reassess"]:
            store = cache_mod.Cache(fixture.KEY, reuse=True)
            for child in manifest["children"]:
                data = store.read("issue", child["ref"]) or {}
                excerptable += len(data.get("body") or "")
                for pr in child["prs"]:
                    files = store.read("pr-files", pr["ref"]) or {}
                    excerptable += len(json.dumps(files.get("files") or []))

        paths = {}
        for name, payload in (("manifest", manifest), ("diff", plan)):
            path = os.path.join(home, f"{label}-{name}.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            paths[name] = path
        report_path = os.path.join(home, f"{label}-report.md")
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(built["report"])
        paths["report"] = report_path
        results[label] = {
            "paths": paths,
            "reassessed": len(plan["reassess"]),
            "reused": built["reused"],
            "excerptable": excerptable,
        }
    return results


def row(label, value, unit):
    print(f"  {label:<46} {value:>10,} {unit}")


def report_run(home, results, label_prefix, size, unit):
    for label in ("full", "incremental"):
        paths = results[label]["paths"]
        print(f"\n{label_prefix} - {label} run "
              f"({results[label]['reassessed']} reassessed, {results[label]['reused']} reused)")
        total = 0
        for name in ("manifest", "diff"):
            value = size(paths[name])
            total += value
            row(f"{name}.json (read by the model)", value, unit)
        row("evidence the model reads", total, unit)
        row("artifact text an assessment must read", results[label]["excerptable"], unit)
        row("  = manifest + diff + excerpts", total + results[label]["excerptable"], unit)
    raw = tree_bytes(os.path.join(home, "cache"))
    row("raw gh responses, cached, never in context", raw, "bytes")


def report_followups(home, unit):
    """What a bounded follow-up read costs the conversation.

    Measured on the command's own stdout, because that is the text that
    reaches the model: `followup.read` hands back the whole file and the
    window is applied on the way out. A matched read is the normal case and
    a whole small file is the worst case for a file this size; neither is a
    ceiling, which is `--max-chars` times the budget and is reported as such.
    """
    from jgr import followup as followup_mod

    env = dict(os.environ, JGR_HOME=home)
    print("\nBounded follow-up reads (what `source` puts in front of the model)")
    for label, extra in (
        ("one matched read, 4 lines of context", ["--match", "func.*Validate"]),
        ("one whole-file read of the same file", []),
    ):
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "rollup.py"), "source",
             "--key", fixture.KEY, "--repo", fixture.ROUTER_REPO,
             "--path", fixture.ROUTER_FILE, "--revision", fixture.MERGE_A] + extra,
            capture_output=True, text=True, env=env,
        )
        one = measure_mod.measure_text(proc.stdout)
        row(label, one["tokens"] if one["tokens"] is not None else one["bytes"], unit)
    # Not measured: a per-read cap times a read cap, which is the most the
    # follow-up stage can add to a run however large the files are.
    row(f"ceiling, not measured: {followup_mod.BUDGET} reads x 4,000", 48_000, "chars")


def main():
    home = tempfile.mkdtemp(prefix="jgr-measure-")
    try:
        results = run(home)

        instructions = {
            "SKILL.md": os.path.join(SKILL, "SKILL.md"),
            "references/requirements.md": os.path.join(SKILL, "references", "requirements.md"),
            "references/pipeline.md": os.path.join(SKILL, "references", "pipeline.md"),
            "references/rollup-format.md": os.path.join(SKILL, "references", "rollup-format.md"),
            "references/snapshots.md": os.path.join(SKILL, "references", "snapshots.md"),
        }
        measured = measure_mod.measure_paths(list(instructions.values()))
        unit = "tokens" if measured["total"]["tokens"] is not None else "bytes"

        def size(path):
            one = measure_mod.measure_paths([path])["total"]
            return one["tokens"] if one["tokens"] is not None else one["bytes"]

        print(f"\nUnit: {measured['total']['unit']}\n")

        print("Instruction surface")
        always = size(instructions["SKILL.md"])
        row("SKILL.md (loaded on every invocation)", always, unit)
        for name, path in list(instructions.items())[1:]:
            row(f"{name} (on demand)", size(path), unit)
        row("all of the above", sum(size(path) for path in instructions.values()), unit)

        previous = git_show("HEAD", ".claude/skills/jira-github-rollup/SKILL.md")
        if previous:
            before = measure_mod.measure_text(previous)
            row(
                "SKILL.md before this refactor",
                before["tokens"] if before["tokens"] is not None else before["bytes"],
                unit,
            )

        report_run(home, results, "Minimal fixture (3 children, 1 PR)", size, unit)
        report_followups(home, unit)

        bigger = tempfile.mkdtemp(prefix="jgr-measure-big-")
        try:
            report_run(
                bigger,
                run(bigger, realistic_world()),
                "Realistic fixture (15 children, 13 PRs, long bodies)",
                size,
                unit,
            )
        finally:
            shutil.rmtree(bigger, ignore_errors=True)

        print(
            "\n  Read these as measurements of this pipeline on these fixtures, not as a\n"
            "  saving. The raw figure is what a traversal would put in the conversation\n"
            "  if `gh` output were pasted; it is on disk instead. The incremental figure\n"
            "  is lower than the full one only in the last row - the manifest is the same\n"
            "  size either way, and the whole of the difference is artifact text that no\n"
            "  longer has to be read. No token or cost claim is made: no tokenizer was\n"
            "  installed when this ran, and one fixture is not a workload.\n"
        )
    finally:
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    main()
