#!/usr/bin/env python3
"""Command-line entry point for the deterministic half of the rollup.

    rollup.py refs      --in payload.json            normalize GitHub references
    rollup.py collect   --epics epics.json           traverse; write the manifest
    rollup.py diff      --manifest m.json ...        baseline, changes, what to reassess
    rollup.py metrics   --manifest m.json ...        the three ratios
    rollup.py assemble  --in assembly.json           all three outputs + snapshot
    rollup.py rerender  --snapshot snap.json         all three from a saved snapshot
    rollup.py excerpt   --ref org/repo#1             a bounded read of one cached body
    rollup.py source    --path a/b.py --revision sha one file at one revision, within budget
    rollup.py convert   --in draft.md --target gfm   post-time markup conversion
    rollup.py promote   --path snap.json --comment-id 123
    rollup.py measure   file [file ...]              size of what the model read

`assemble` and `rerender` produce three renderings of one assessment: the full
assessment for review, the Jira summary draft that is the only thing ever
posted, and a standalone HTML file. They come from a single tally and are
cross-checked against each other before any of them is written.

Every subcommand reads JSON and writes JSON (or Markdown for `convert`), so
the model passes structured data in and gets structured data back without raw
API responses crossing the boundary in either direction.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jgr import assemble as assemble_mod  # noqa: E402
from jgr import cache as cache_mod  # noqa: E402
from jgr import collect as collect_mod  # noqa: E402
from jgr import convert as convert_mod  # noqa: E402
from jgr import diff as diff_mod  # noqa: E402
from jgr import followup as followup_mod  # noqa: E402
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
    if args.narrative:
        narrative = load(args.narrative)
        assembly["narrative"] = (
            narrative.get("narrative") if isinstance(narrative, dict) else narrative
        )
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
    """Write the renderings, then the result JSON describing where they went."""
    report = result.pop("report")
    summary = result.pop("summary")
    # Always rendered, written only when asked for. It never goes to stdout:
    # a quarter of a megabyte of markup in the conversation is exactly the
    # kind of raw payload the cache exists to keep out of it.
    document = result.pop("html", None)
    if document is not None:
        result["htmlBytes"] = len(document.encode("utf-8"))
        if getattr(args, "html", None):
            with open(args.html, "w", encoding="utf-8") as handle:
                handle.write(document)
            result["htmlPath"] = args.html
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
    """Rebuild the outputs from a snapshot already on disk.

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
            # The flags override; the snapshot is the default. A snapshot
            # written before these fields existed still falls back to the key.
            "summary": args.title or snapshot.get("jiraSummary") or snapshot.get("jiraKey"),
            "status": snapshot.get("jiraStatus"),
            "site": args.site or snapshot.get("jiraSite"),
            "fixVersions": snapshot.get("jiraFixVersions") or [],
        },
        # Whether the comment was ever posted. A re-render of a published
        # snapshot must not print "Draft - not published" over text that is
        # sitting on the issue.
        "publication": snapshot.get("publication"),
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
            "untraversed": scope.get("untraversed") or [],
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
        # The stored prose is the prose. Re-rendering a reviewed summary has to
        # reproduce what was reviewed, not write a fresh one from the same
        # rows - otherwise the text on the issue and the text this command
        # prints can differ while both claim to come from one snapshot.
        # `--narrative` overrides only when the caller asks for it.
        "summary": args.narrative or snapshot.get("summaryNarrative") or "",
        # Restored rather than regenerated, for the same reason. A snapshot
        # written before this field existed has none, and the renderings fall
        # back to the mechanical paragraph - which says less than the one that
        # was reviewed, and does not pretend otherwise.
        "overall": snapshot.get("overall"),
        "narrative": snapshot.get("narrative") or [],
        # The follow-up reads this run made. Replayed from the snapshot rather
        # than re-derived from the cache ledger, which may have been cleared
        # since - a re-render must not describe a shallower investigation than
        # the one whose conclusions it is printing.
        "sourceReads": snapshot.get("sourceReads") or [],
        # Likewise the trend sentence: it was computed against a baseline that
        # is not in this file, so it is replayed rather than recomputed.
        "summaryTrend": snapshot.get("summaryTrend"),
        # Caveats, risks and declared dependencies, restored as written.
        **(snapshot.get("prose") or {}),
    }

    # The full assessment's trend table needs the baseline's contents, not just
    # its date. Reload it from the store; if it has been removed, the section
    # says a baseline existed and could not be read rather than claiming this
    # was the first run.
    recorded = snapshot.get("baseline") or {}
    if recorded.get("generatedAt"):
        prior = snapshots_mod.find(snapshot.get("jiraKey"), recorded["generatedAt"])
        if prior is not None:
            assembly["baselineSnapshot"] = prior
            assembly["diff"] = {"baseline": recorded}
        else:
            assembly["diff"] = {
                "baselineProblem": {
                    "generatedAt": recorded["generatedAt"],
                    "detail": "no longer in the snapshot store",
                }
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
    if args.field:
        # An empty --field means the whole document, which is the only way to
        # read a payload cached as a bare list: `pr-checks` is one, and walking
        # a field path into it has no meaning.
        for part in args.field.split("."):
            value = (value or {}).get(part) if isinstance(value, dict) else None
        if value is None:
            # Name what is there. Without this the caller cannot tell a field
            # that was never collected from one that is empty on this artifact,
            # and the obvious next move - re-running collect - fixes neither.
            raise SystemExit(
                f"{args.ref}: no field {args.field!r} in the cached {args.kind} response"
                + (
                    "; this payload is a list, so pass --field '' to read all of it"
                    if isinstance(data, list)
                    else "; it carries " + ", ".join(sorted(data))
                    if isinstance(data, dict) and data
                    else ""
                )
            )
    # Indented rather than canonical: --match and --context are line-based, and
    # a compact dump is one line, so every match would return the whole payload.
    # canonical() is the hashing format and stays untouched.
    text = value if isinstance(value, str) else json.dumps(value, indent=1, sort_keys=True)
    read = util.window(text, args.match, args.context, args.max_chars)
    util.emit(
        dict(
            read,
            ref=args.ref,
            kind=args.kind,
            field=args.field,
            fullChars=len(value) if isinstance(value, str) else read["fullChars"],
            path=cache.path_for(args.kind, args.ref),
        ),
        args.out,
    )


def cmd_source(args):
    """A bounded follow-up read of one source file at one revision.

    The one retrieval in this pipeline that exists to *close* a question
    rather than to collect evidence, and the only one with a budget attached.
    It always answers: `inspected` true with the window, or false with the
    constraint to record. See `jgr/followup.py` for why each bound is there.
    """
    cache = cache_mod.Cache(args.key, root=args.cache_dir, reuse=True)
    result = followup_mod.read(
        Gh(), cache, args.repo, args.path, args.revision, budget=args.budget
    )
    if result["inspected"]:
        read = util.window(result.pop("body"), args.match, args.context, args.max_chars)
        result.update(read)
    util.emit(result, args.out)


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

    p = sub.add_parser("assemble", help="render the outputs and write the snapshot")
    p.add_argument("--in", dest="input", default="-")
    p.add_argument("--manifest")
    p.add_argument("--diff")
    p.add_argument("--requirements")
    p.add_argument("--assessments")
    p.add_argument(
        "--narrative",
        help="summary bullet claims: [{bullet, text, refs:[{sourceKey,id}], links:[ref]}]",
    )
    p.add_argument("--report", help="write the full assessment here")
    p.add_argument("--summary", help="write the Jira summary draft here")
    p.add_argument(
        "--html",
        help="write the standalone HTML full assessment here (local file, not a Jira link)",
    )
    p.add_argument(
        "--full-assessment-url",
        help="durable URL a Jira reader can open; omitted from the summary if absent",
    )
    p.add_argument("--no-snapshot", action="store_true")
    p.add_argument("--snapshot-dir")
    p.add_argument("--out")
    p.set_defaults(func=cmd_assemble)

    p = sub.add_parser("rerender", help="rebuild the outputs from a saved snapshot")
    p.add_argument("--snapshot", required=True)
    p.add_argument("--site", help="Jira base URL, so criteria link to their issue")
    p.add_argument("--title", help="requirement name for the summary heading")
    p.add_argument("--narrative", help="the Summary paragraph for the full assessment")
    p.add_argument("--report", help="write the full assessment here")
    p.add_argument("--summary", help="write the Jira summary draft here")
    p.add_argument("--html", help="write the standalone HTML full assessment here")
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

    p = sub.add_parser("source", help="read one source file at one revision, within budget")
    p.add_argument("--key", required=True)
    p.add_argument("--repo", required=True, help="owner/name, already in the assessment scope")
    p.add_argument("--path", required=True, help="one file; this command does not search")
    # Required on purpose. The question is what the code did at the revision
    # the evidence was produced at, and today's default branch is a different
    # document at the same path.
    p.add_argument("--revision", required=True, help="commit sha, tag or branch to read at")
    p.add_argument("--match", help="regex; return only matching lines and their context")
    p.add_argument("--context", type=int, default=4)
    p.add_argument("--max-chars", type=int, default=4000)
    p.add_argument(
        "--budget",
        type=int,
        default=followup_mod.BUDGET,
        help=f"distinct source reads allowed for this key (default {followup_mod.BUDGET})",
    )
    p.add_argument("--cache-dir")
    p.add_argument("--out")
    p.set_defaults(func=cmd_source)

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
