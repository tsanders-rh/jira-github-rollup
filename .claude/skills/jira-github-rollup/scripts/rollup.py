#!/usr/bin/env python3
"""Command-line entry point for the deterministic half of the rollup.

    rollup.py refs      --in payload.json            normalize GitHub references
    rollup.py collect   --epics epics.json           traverse; write the manifest
    rollup.py diff      --manifest m.json ...        baseline, changes, what to reassess
    rollup.py metrics   --manifest m.json ...        the three ratios
    rollup.py assemble  --in assembly.json           both outputs + snapshot
    rollup.py rerender  --snapshot snap.json         both outputs from a saved snapshot
    rollup.py excerpt   --ref org/repo#1             a bounded read of one cached body
    rollup.py convert   --in draft.md --target gfm   post-time markup conversion
    rollup.py promote   --path snap.json --comment-id 123
    rollup.py measure   file [file ...]              size of what the model read

`assemble` and `rerender` produce two renderings of one assessment: the full
assessment for review, and the Jira summary draft that is the only thing ever
posted. They come from a single tally and are cross-checked against each other
before either is written.

Every subcommand reads JSON and writes JSON (or Markdown for `convert`), so
the model passes structured data in and gets structured data back without raw
API responses crossing the boundary in either direction.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jgr import assemble as assemble_mod  # noqa: E402
from jgr import cache as cache_mod  # noqa: E402
from jgr import collect as collect_mod  # noqa: E402
from jgr import convert as convert_mod  # noqa: E402
from jgr import diff as diff_mod  # noqa: E402
from jgr import measure as measure_mod  # noqa: E402
from jgr import metrics as metrics_mod  # noqa: E402
from jgr import refs as refs_mod  # noqa: E402
from jgr import snapshots as snapshots_mod  # noqa: E402
from jgr import util  # noqa: E402
from jgr.ghclient import Gh  # noqa: E402


def load(value, default=None):
    """Accept a path, `-` for stdin, or inline JSON."""
    if value is None:
        return default
    if value == "-":
        return util.load_stdin_json()
    if os.path.exists(value):
        return util.read_json(value)
    stripped = value.strip()
    if stripped[:1] in "[{\"":
        return json.loads(stripped)
    raise SystemExit(f"not a readable path or JSON value: {value}")


def read_text(value):
    if value == "-":
        return sys.stdin.read()
    with open(value, "r", encoding="utf-8") as handle:
        return handle.read()


# --- subcommands ---------------------------------------------------------


def cmd_refs(args):
    util.emit(refs_mod.collect(load(args.input, {})), args.out)


def cmd_collect(args):
    epics = load(args.epics, [])
    if isinstance(epics, dict):
        epics = epics.get("epics") or []
    epics = [{"ref": e} if isinstance(e, str) else e for e in epics]

    jira_key = args.key or (load(args.epics, {}) or {}).get("jiraKey")
    if not jira_key:
        raise SystemExit("--key is required")

    if not epics:
        util.emit(collect_mod.empty_manifest(jira_key), args.out)
        return

    cache = cache_mod.Cache(jira_key, root=args.cache_dir, reuse=args.offline)
    collector = collect_mod.Collector(jira_key, gh=Gh(), cache=cache)

    if args.stage == "evidence":
        manifest = load(args.manifest)
        if manifest is None:
            raise SystemExit("--manifest is required for --stage evidence")
        targets = load(args.targets, [])
        if isinstance(targets, dict):
            targets = targets.get("prs") or []
        if not targets:
            raise SystemExit(
                "--targets is required for --stage evidence: name the PRs that are "
                "candidate evidence for a requirement"
            )
        util.emit(collector.evidence(manifest, targets), args.out)
        return

    util.emit(collector.inventory(epics), args.out)


def cmd_diff(args):
    manifest = load(args.manifest)
    requirements = load(args.requirements, [])
    if isinstance(requirements, dict):
        requirements = requirements.get("requirements") or []
    mappings = load(args.mappings, []) or [
        {"ref": epic["ref"], "linkSource": epic.get("linkSource")} for epic in manifest.get("epics") or []
    ]
    baseline_info = snapshots_mod.select_baseline(manifest["jiraKey"], directory=args.snapshot_dir)
    plan = diff_mod.plan(baseline_info, manifest, requirements, mappings, full_refresh=args.full_refresh)
    if args.with_baseline and baseline_info.get("snapshot"):
        plan["baselineSnapshot"] = baseline_info["snapshot"]
    util.emit(plan, args.out)


def cmd_metrics(args):
    manifest = load(args.manifest, {})
    requirements = load(args.requirements, [])
    if isinstance(requirements, dict):
        requirements = requirements.get("requirements") or []
    computed = metrics_mod.compute(
        requirements,
        manifest.get("children") or [],
        observed=manifest.get("observed", bool(manifest.get("epics"))),
        unobserved_reason=manifest.get("unobservedReason"),
    )
    computed["rendered"] = {
        "children": metrics_mod.render_ratio(computed["children"]),
        "coverage": metrics_mod.render_ratio(computed["coverage"]),
        "downstream": metrics_mod.render_ratio(computed["downstream"]),
    }
    util.emit(computed, args.out)


def cmd_assemble(args):
    assembly = load(args.input, {})
    for name, attr in (("manifest", args.manifest), ("diff", args.diff)):
        if attr:
            assembly[name] = load(attr)
    if args.requirements:
        assembly["requirements"] = load(args.requirements)
    if args.assessments:
        assembly["assessments"] = load(args.assessments)
    if assembly.get("diff") and "baselineSnapshot" not in assembly:
        baseline = (assembly["diff"].get("baseline") or {}).get("path")
        if baseline:
            data, problem = snapshots_mod.load(baseline)
            if problem:
                raise SystemExit(f"baseline {baseline}: {problem}")
            assembly["baselineSnapshot"] = data

    result = assemble_mod.build(
        assembly,
        directory=args.snapshot_dir,
        write_snapshot=not args.no_snapshot,
        full_assessment_url=args.full_assessment_url,
    )
    _emit_outputs(result, args)


def _emit_outputs(result, args):
    """Write both renderings, then the result JSON describing where they went."""
    report = result.pop("report")
    summary = result.pop("summary")
    if args.report:
        with open(args.report, "w", encoding="utf-8") as handle:
            handle.write(report)
        result["reportPath"] = args.report
    else:
        sys.stdout.write(report)
        sys.stdout.write("\n")
    if args.summary:
        with open(args.summary, "w", encoding="utf-8") as handle:
            handle.write(summary)
        result["summaryPath"] = args.summary
    else:
        result["summaryText"] = summary
    result["reportBytes"] = len(report.encode("utf-8"))
    result["summaryBytes"] = len(summary.encode("utf-8"))
    util.emit(result, args.out)


def cmd_rerender(args):
    """Rebuild both outputs from a snapshot already on disk.

    Read-only against the store: it loads the snapshot, renders, and writes
    nothing back. That is what makes it safe to re-run on a published snapshot
    to see what was reported, and it is the path used to regenerate an output
    without re-collecting or re-assessing anything.
    """
    snapshot, problem = snapshots_mod.load(args.snapshot)
    if snapshot is None:
        raise SystemExit(f"{args.snapshot}: {problem}")

    scope = snapshot.get("scope") or {}
    assembly = {
        "generatedAt": snapshot.get("generatedAt"),
        "jira": {
            "key": snapshot.get("jiraKey"),
            "summary": args.title or snapshot.get("jiraKey"),
            "status": snapshot.get("jiraStatus"),
            "site": args.site,
            "fixVersions": [],
        },
        "mappings": [
            {
                "ref": mapping.get("epic"),
                "url": mapping.get("url"),
                "title": mapping.get("title"),
                "linkSource": mapping.get("linkSource"),
            }
            for mapping in snapshot.get("mappings") or []
        ],
        "manifest": {
            "jiraKey": snapshot.get("jiraKey"),
            "epics": (snapshot.get("inventory") or {}).get("epics") or [],
            "children": scope.get("children") or [],
            "dependencies": [{"ref": ref} for ref in scope.get("otherInspected") or []],
            "access": snapshot.get("access") or [],
            "traversalComplete": scope.get("traversalComplete", True),
            "traversalNotes": scope.get("traversalNotes") or [],
            "observed": scope.get("observed", True),
            "unobservedKind": scope.get("unobservedKind"),
            "unobservedReason": scope.get("unobservedReason"),
            "collectedAt": (snapshot.get("inventory") or {}).get("collectedAt"),
            "stage": (snapshot.get("inventory") or {}).get("stage"),
        },
        "requirements": snapshot.get("requirements") or [],
        # The stored assessments are the assessments. Re-rendering never
        # re-judges anything; passing them back in as `assessments` keeps the
        # merge's "one assessment per requirement" rule satisfied without
        # inventing a verdict for a row that has one.
        "assessments": snapshot.get("requirements") or [],
        "summary": args.narrative or "",
    }
    result = assemble_mod.build(
        assembly, write_snapshot=False, full_assessment_url=args.full_assessment_url
    )
    result["renderedFrom"] = args.snapshot
    _emit_outputs(result, args)


def cmd_excerpt(args):
    """A bounded, deliberate read of one cached body.

    Truncation is reported in the payload, never silent, and the path to the
    full text comes back with it so the next read can be wider.
    """
    cache = cache_mod.Cache(args.key, root=args.cache_dir, reuse=True)
    data = cache.read(args.kind, args.ref)
    if data is None:
        raise SystemExit(f"nothing cached for {args.kind} {args.ref}; run collect first")
    value = data
    for part in args.field.split("."):
        value = (value or {}).get(part) if isinstance(value, dict) else None
    if value is None:
        raise SystemExit(f"{args.ref}: no field {args.field!r} in the cached response")
    text = value if isinstance(value, str) else util.canonical(value)

    matched = None
    if args.match:
        pattern = re.compile(args.match, re.I)
        lines = text.splitlines()
        keep = set()
        for index, line in enumerate(lines):
            if pattern.search(line):
                keep.update(range(max(0, index - args.context), min(len(lines), index + args.context + 1)))
        matched = sum(1 for index, line in enumerate(lines) if pattern.search(line))
        text = "\n".join(lines[index] for index in sorted(keep))

    truncated = len(text) > args.max_chars
    util.emit(
        {
            "ref": args.ref,
            "kind": args.kind,
            "field": args.field,
            "matchedLines": matched,
            "text": text[: args.max_chars],
            "truncated": truncated,
            "fullChars": len(value) if isinstance(value, str) else len(text),
            "path": cache.path_for(args.kind, args.ref),
        },
        args.out,
    )


def cmd_convert(args):
    converted = convert_mod.convert(read_text(args.input), args.target)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(converted)
        print(args.out)
    else:
        sys.stdout.write(converted)


def cmd_promote(args):
    published_text = read_text(args.published_text) if args.published_text else None
    path = snapshots_mod.promote(args.path, args.comment_id, published_text=published_text)
    util.emit(
        {
            "path": path,
            "publication": "published",
            "jiraCommentId": args.comment_id,
            "publishedKind": "summary" if published_text else None,
        },
        args.out,
    )


def cmd_measure(args):
    util.emit(measure_mod.measure_paths(args.paths, label=args.label), args.out)


# --- wiring --------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(prog="rollup.py", description=__doc__)
    parser.add_argument("--out", help="write JSON here instead of stdout")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("refs", help="normalize and deduplicate GitHub references")
    p.add_argument("--in", dest="input", default="-")
    p.add_argument("--out")
    p.set_defaults(func=cmd_refs)

    p = sub.add_parser("collect", help="traverse the mapped epics")
    p.add_argument("--key", help="Jira key")
    p.add_argument("--epics", default="-", help="epic list, or the refs output")
    p.add_argument("--stage", choices=["inventory", "evidence"], default="inventory")
    p.add_argument("--manifest", help="manifest from the inventory stage")
    p.add_argument("--targets", help="PR refs to fetch evidence for")
    p.add_argument("--cache-dir")
    p.add_argument("--offline", action="store_true", help="reuse cached responses; do not call gh")
    p.add_argument("--out")
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("diff", help="compare against the baseline snapshot")
    p.add_argument("--manifest", required=True)
    p.add_argument("--requirements", required=True)
    p.add_argument("--mappings")
    p.add_argument("--full-refresh", action="store_true")
    p.add_argument("--with-baseline", action="store_true", help="include the baseline snapshot inline")
    p.add_argument("--snapshot-dir")
    p.add_argument("--out")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("metrics", help="compute the three ratios")
    p.add_argument("--manifest", required=True)
    p.add_argument("--requirements", required=True)
    p.add_argument("--out")
    p.set_defaults(func=cmd_metrics)

    p = sub.add_parser("assemble", help="render both outputs and write the snapshot")
    p.add_argument("--in", dest="input", default="-")
    p.add_argument("--manifest")
    p.add_argument("--diff")
    p.add_argument("--requirements")
    p.add_argument("--assessments")
    p.add_argument("--report", help="write the full assessment here")
    p.add_argument("--summary", help="write the Jira summary draft here")
    p.add_argument(
        "--full-assessment-url",
        help="durable URL a Jira reader can open; omitted from the summary if absent",
    )
    p.add_argument("--no-snapshot", action="store_true")
    p.add_argument("--snapshot-dir")
    p.add_argument("--out")
    p.set_defaults(func=cmd_assemble)

    p = sub.add_parser("rerender", help="rebuild both outputs from a saved snapshot")
    p.add_argument("--snapshot", required=True)
    p.add_argument("--site", help="Jira base URL, so criteria link to their issue")
    p.add_argument("--title", help="requirement name for the summary heading")
    p.add_argument("--narrative", help="the Summary paragraph for the full assessment")
    p.add_argument("--report", help="write the full assessment here")
    p.add_argument("--summary", help="write the Jira summary draft here")
    p.add_argument("--full-assessment-url")
    p.add_argument("--out")
    p.set_defaults(func=cmd_rerender)

    p = sub.add_parser("excerpt", help="read part of one cached artifact")
    p.add_argument("--key", required=True)
    p.add_argument("--ref", required=True)
    p.add_argument("--kind", default="issue", choices=["issue", "pr", "pr-files", "pr-checks"])
    p.add_argument("--field", default="body")
    p.add_argument("--match", help="regex; return only matching lines and their context")
    p.add_argument("--context", type=int, default=2)
    p.add_argument("--max-chars", type=int, default=4000)
    p.add_argument("--cache-dir")
    p.add_argument("--out")
    p.set_defaults(func=cmd_excerpt)

    p = sub.add_parser("convert", help="convert the approved draft for Jira")
    p.add_argument("--in", dest="input", default="-")
    p.add_argument("--target", required=True, choices=["gfm", "html", "wiki", "plain", "adf"])
    p.add_argument("--out")
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser("promote", help="mark a snapshot published after a successful post")
    p.add_argument("--path", required=True)
    p.add_argument("--comment-id", required=True, help="the id the Jira update returned")
    p.add_argument(
        "--published-text",
        help="the approved summary that was posted; recorded as a hash on the snapshot",
    )
    p.add_argument("--out")
    p.set_defaults(func=cmd_promote)

    p = sub.add_parser("measure", help="size of the files handed to the model")
    p.add_argument("paths", nargs="+")
    p.add_argument("--label")
    p.add_argument("--out")
    p.set_defaults(func=cmd_measure)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
