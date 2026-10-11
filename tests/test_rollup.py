#!/usr/bin/env python3
"""Behaviour tests for the scripted half of the rollup.

Each test is one of the situations the refactor had to not break: a first run,
an unchanged rerun, evidence that moved, scope that grew or shrank, a PR that
merged without its issue being touched, access that went away and came back,
evidence that is new to the report but old in the world, the same child
reachable from two epics, and counts that are genuinely unknown.

The assertions are about report semantics, not implementation detail: what the
numbers say, what the trend section claims, and what gets reassessed.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from html import parser as html_parser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, ".claude", "skills", "jira-github-rollup", "scripts")
sys.path.insert(0, SCRIPTS)

from jgr import assemble as assemble_mod  # noqa: E402
from jgr import cache as cache_mod  # noqa: E402
from jgr import clauses as clauses_mod  # noqa: E402
from jgr import collect as collect_mod  # noqa: E402
from jgr import convert as convert_mod  # noqa: E402
from jgr import diff as diff_mod  # noqa: E402
from jgr import followup as followup_mod  # noqa: E402
from jgr import htmlreport as htmlreport_mod  # noqa: E402
from jgr import measure as measure_mod  # noqa: E402
from jgr import links as links_mod  # noqa: E402
from jgr import metrics as metrics_mod  # noqa: E402
from jgr import outcomes as outcomes_mod  # noqa: E402
from jgr import refs as refs_mod  # noqa: E402
from jgr import scope as scope_mod  # noqa: E402
from jgr import snapshots as snapshots_mod  # noqa: E402
from jgr import summary as summary_mod  # noqa: E402
from jgr import util  # noqa: E402
from jgr.ghclient import Gh  # noqa: E402

KEY = "RHOAIENG-7001"
EPIC = "example-org/example-quota#300"
CHILD_A = "example-org/example-quota#301"
CHILD_B = "example-org/example-quota#302"
CHILD_C = "example-org/example-meter#40"
PR_A = "example-org/example-quota#500"
PR_B = "example-org/example-quota#501"

# The revision PR_A merged as, and the files a follow-up read of it opens.
# Both paths are already in PR_A's changed-file list, which is the only kind
# of reference a follow-up is allowed to follow: one the evidence produced.
MERGE_A = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
ROUTER_REPO = "example-org/example-quota"
ROUTER_FILE = "pkg/router/tier.go"
ROUTER_TEST = "pkg/router/tier_test.go"

# A configuration-time restriction and nothing else. Membership in
# `TieredPools` establishes which configs are rejected; it establishes nothing
# about where a live request is routed, and the gap between those two is the
# one this fixture exists to keep visible.
ROUTER_SOURCE = """package router

// TieredPools is the set of pools a tiered model may be assigned to.
var TieredPools = []string{"gold", "silver", "bronze"}

// Validate rejects a configuration that lets a tiered model overflow.
func Validate(c Config) error {
\tif contains(TieredPools, c.Pool) && c.Overflow == "any" {
\t\treturn fmt.Errorf("overflow: any is not permitted for a tiered pool")
\t}
\treturn nil
}
"""

ROUTER_TEST_SOURCE = """package router

func TestValidateRejectsOverflowAny(t *testing.T) {
\terr := Validate(Config{Pool: "gold", Overflow: "any"})
\tif err == nil {
\t\tt.Fatal("expected overflow: any to be rejected for a tiered pool")
\t}
}
"""


def issue(ref, title, state="OPEN", reason=None, body="", closed=None, updated="2026-09-01T00:00:00Z",
          created="2026-08-01T00:00:00Z", labels=None):
    repo, number = ref.split("#")
    return {
        "number": int(number),
        "title": title,
        "state": state,
        "stateReason": reason,
        "body": body,
        "labels": labels or [],
        "assignees": [],
        "url": f"https://github.com/{repo}/issues/{number}",
        # What dates the issue as evidence while it is open, and what dates it
        # once it is not. The assembler joins one of the two onto every cited
        # ref; nothing is typed in beside the ref.
        "createdAt": created,
        "closedAt": closed,
        "updatedAt": updated,
    }


def pull(ref, state="OPEN", merged=None, updated="2026-09-01T00:00:00Z",
         created="2026-08-01T00:00:00Z", commit=None):
    repo, number = ref.split("#")
    return {
        "number": int(number),
        "title": f"PR {number}",
        "state": "MERGED" if merged else state,
        "isDraft": False,
        "createdAt": created,
        "mergedAt": merged,
        # The revision a follow-up read of this PR's code has to use. Only a
        # merged PR has one, which is the same thing the collector records.
        "mergeCommit": {"oid": commit} if (merged and commit) else None,
        "author": {"login": "someone"},
        "url": f"https://github.com/{repo}/pull/{number}",
        "baseRefName": "main",
        "reviewDecision": "APPROVED" if merged else "",
        "updatedAt": updated,
    }


def crossref(ref, kind="pull"):
    repo, number = ref.split("#")
    return {
        "event": "cross-referenced",
        "source": {
            "issue": {
                "html_url": f"https://github.com/{repo}/{'pull' if kind == 'pull' else 'issues'}/{number}",
                "pull_request": {} if kind == "pull" else None,
            }
        },
    }


def base_world():
    return {
        "issues": {
            EPIC: issue(EPIC, "Tiered quota enforcement", body="Epic body."),
            CHILD_A: issue(
                CHILD_A, "Route by tier", state="CLOSED", reason="COMPLETED", closed="2026-09-18T10:00:00Z"
            ),
            CHILD_B: issue(CHILD_B, "Expose quota metrics"),
            CHILD_C: issue(CHILD_C, "Meter integration"),
        },
        "subIssues": {EPIC: [CHILD_A, CHILD_B, CHILD_C]},
        "timeline": {CHILD_A: [crossref(PR_A)], CHILD_B: [], CHILD_C: []},
        "prs": {PR_A: pull(PR_A, merged="2026-09-18T09:00:00Z", commit=MERGE_A)},
        "prFiles": {
            PR_A: {
                "changedFiles": 4,
                "files": [
                    {"path": "pkg/router/tier.go"},
                    {"path": "pkg/router/tier_test.go"},
                    {"path": "docs/quota.md"},
                ],
                "closingIssuesReferences": [
                    {"number": 301, "repository": {"nameWithOwner": "example-org/example-quota"}}
                ],
            }
        },
        "checks": {PR_A: [{"name": "unit", "bucket": "pass"}, {"name": "e2e", "bucket": "pass"}]},
        "searchPrs": {},
        # The file PR_A's changed-file list already names, at the revision it
        # merged as. It establishes a configuration restriction on tiered
        # pools and says nothing about what the router does with a live
        # request, which is the shape the follow-up tests turn on.
        "sources": {
            f"{ROUTER_REPO}@{MERGE_A}:{ROUTER_FILE}": ROUTER_SOURCE,
            f"{ROUTER_REPO}@{MERGE_A}:{ROUTER_TEST}": ROUTER_TEST_SOURCE,
        },
    }


REQUIREMENTS = [
    {
        "id": "AC1",
        "sourceKey": KEY,
        "type": "AC",
        "text": "Requests for a tiered model are routed to the pool for that tier.",
    },
    {
        "id": "AC2",
        "sourceKey": KEY,
        "type": "AC",
        "text": "Quota consumption is exposed as a metric.",
    },
]


def assessment(requirement_id, verdict, evidence=(), state=None, downstream="unknown", gap=None):
    return {
        "id": requirement_id,
        "sourceKey": KEY,
        "type": "AC",
        "text": next(r["text"] for r in REQUIREMENTS if r["id"] == requirement_id)
        if any(r["id"] == requirement_id for r in REQUIREMENTS)
        else None,
        "assessment": verdict,
        "evidence": list(evidence),
        "evidenceState": state,
        "coverageDetail": "as judged by the model",
        "gap": gap,
        "downstream": {"state": downstream, "detail": "none identified" if downstream else None},
    }


def clause(text, kind="evidence-gap", **fields):
    """An open clause in the shape `clauses.problems` accepts.

    The defaults are the cheapest thing that passes, so a test that cares
    about one field can set that field and ignore the rest.
    """
    built = {"text": text, "kind": kind, "nextAction": "read the handler and say which it is"}
    if kind == "evidence-gap":
        built["inspected"] = [PR_A]
    if kind == "implementation-gap":
        built["evidence"] = [PR_A]
    if kind == "inspection-limitation":
        built["limitation"] = "the file is in a repository this token cannot read"
    built.update(fields)
    return built


class PipelineTest(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="jgr-test-")
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        os.environ["JGR_HOME"] = self.home
        os.environ["GH_BIN"] = os.path.join(ROOT, "tests", "fakegh.py")
        self.world_path = os.path.join(self.home, "world.json")
        os.environ["GH_WORLD"] = self.world_path
        self.world = base_world()

    # --- harness --------------------------------------------------------

    def write_world(self):
        with open(self.world_path, "w", encoding="utf-8") as handle:
            json.dump(self.world, handle)

    def cite_pr(self, ref=PR_B, child=CHILD_B, merged="2026-09-20T09:00:00Z"):
        """Put a second pull request where the traversal will find it.

        Evidence refs are joined against the manifest, so a ref a test invents
        is refused exactly as a mistyped one is. A test that wants to cite a
        second PR has to add it to the world first - which is the behaviour
        under test as much as it is setup.
        """
        self.world["prs"][ref] = pull(ref, merged=merged)
        self.world["timeline"].setdefault(child, []).append(crossref(ref))
        self.world["prFiles"][ref] = {
            "changedFiles": 1, "files": [{"path": "pkg/meter/usage.go"}],
            "closingIssuesReferences": [],
        }
        self.world["checks"][ref] = [{"name": "unit", "bucket": "pass"}]
        return ref

    def collect(self, epics=(EPIC,), key=KEY):
        self.write_world()
        collector = collect_mod.Collector(key, gh=Gh(), cache=cache_mod.Cache(key))
        manifest = collector.inventory([{"ref": ref, "linkSource": "upstream-development-section"} for ref in epics])
        pr_refs = [pr["ref"] for child in manifest["children"] for pr in child["prs"]]
        if pr_refs:
            manifest = collector.evidence(manifest, pr_refs)
        return manifest

    def plan(self, manifest, requirements, full_refresh=False, key=KEY):
        baseline = snapshots_mod.select_baseline(key)
        mappings = [{"ref": epic["ref"], "linkSource": epic.get("linkSource")} for epic in manifest["epics"]]
        plan = diff_mod.plan(baseline, manifest, requirements, mappings, full_refresh=full_refresh)
        plan["_baselineSnapshot"] = baseline.get("snapshot")
        return plan

    def run_once(self, requirements, assessments, epics=(EPIC,), generated_at=None, full_refresh=False, key=KEY,
                 overall=None):
        manifest = self.collect(epics, key=key)
        plan = self.plan(manifest, requirements, full_refresh=full_refresh, key=key)
        assembly = {
            "jira": {"key": key, "summary": "Tiered quota", "status": "In Progress"},
            "mappings": [
                {"ref": epic["ref"], "url": epic.get("url"), "title": epic.get("title"),
                 "linkSource": epic.get("linkSource")}
                for epic in manifest["epics"]
            ],
            "manifest": manifest,
            "diff": plan,
            "baselineSnapshot": plan.pop("_baselineSnapshot"),
            "requirements": requirements,
            "assessments": assessments,
            "summary": "Upstream work is partly complete.",
            "generatedAt": generated_at,
        }
        if overall is not None:
            assembly["overall"] = overall
        result = assemble_mod.build(assembly)
        return manifest, plan, result, result["report"]

    # --- scenarios ------------------------------------------------------

    def test_first_run_establishes_a_baseline_and_assesses_everything(self):
        _, plan, result, report = self.run_once(
            REQUIREMENTS,
            [
                assessment("AC1", "Evidence found", [{"ref": PR_A, "kind": "pr", "state": "merged",
                                                      "at": "2026-09-18T09:00:00Z"}], "merged", "confirmed"),
                assessment("AC2", "No evidence found", [], "none"),
            ],
            generated_at="2026-10-01T00:00:00Z",
        )
        self.assertIn("no baseline snapshot: this run establishes one", plan["reassessAll"])
        self.assertEqual(len(plan["reassess"]), 2)
        self.assertEqual(plan["reuse"], [])
        self.assertIn("Baseline established", report)
        # A baseline run states no percentages: there is nothing to compare to.
        self.assertNotIn("%", report.split("#### Trend")[1])
        self.assertIn("1 of 3 child issues closed as completed", report)
        self.assertTrue(os.path.exists(result["snapshotPath"]))

    def test_unchanged_rerun_reuses_assessments_and_reports_no_change(self):
        self.run_once(
            REQUIREMENTS,
            [
                assessment("AC1", "Evidence found", [{"ref": PR_A, "kind": "pr", "state": "merged",
                                                      "at": "2026-09-18T09:00:00Z"}], "merged", "confirmed"),
                assessment("AC2", "No evidence found", [], "none"),
            ],
            generated_at="2026-10-01T00:00:00Z",
        )
        _, plan, result, report = self.run_once(
            REQUIREMENTS, [], generated_at="2026-10-08T00:00:00Z"
        )

        self.assertEqual(plan["reassess"], [], "an unchanged rerun must not ask for any reassessment")
        self.assertEqual(result["reused"], 2)
        self.assertEqual(result["assessed"], 0)
        # The report is still complete: both rows present, both verdicts intact.
        self.assertIn("AC1 (RHOAIENG-7001)", report)
        self.assertIn("AC2 (RHOAIENG-7001)", report)
        self.assertIn("Evidence found", report)
        self.assertIn("no change", report)
        self.assertNotIn("unchanged since", report)

    def test_a_pending_downstream_is_never_reused(self):
        """Nothing upstream can contradict it, so reuse would republish it forever.

        Downstream qualification is outside the traversal: no content hash this
        differ computes covers it. A `pending` carried forward unchanged is a
        months-old "qualification outstanding" reported as if it were current.
        """
        self.cite_pr()
        self.run_once(
            REQUIREMENTS,
            [
                assessment("AC1", "Evidence found", [{"ref": PR_A}], "merged", "pending"),
                assessment("AC2", "Evidence found", [{"ref": PR_B}], "merged", "confirmed"),
            ],
            generated_at="2026-10-01T00:00:00Z",
        )
        plan = self.plan(self.collect(), REQUIREMENTS)
        self.assertEqual([entry["id"] for entry in plan["reassess"]], ["AC1"])
        self.assertIn("downstream qualification was outstanding", plan["reassess"][0]["reason"])
        self.assertEqual([entry["id"] for entry in plan["reuse"]], ["AC2"])

    def test_an_unknown_downstream_is_still_reusable(self):
        """Nobody looked then and nobody looked now; repeating that is honest."""
        self.cite_pr()
        self.run_once(
            REQUIREMENTS,
            [
                assessment("AC1", "Evidence found", [{"ref": PR_A}], "merged", "unknown"),
                assessment("AC2", "Evidence found", [{"ref": PR_B}], "merged", "unknown"),
            ],
            generated_at="2026-10-01T00:00:00Z",
        )
        plan = self.plan(self.collect(), REQUIREMENTS)
        self.assertEqual(plan["reassess"], [])

    def test_new_work_in_a_repo_reassesses_what_drew_evidence_from_it(self):
        """`Evidence found` is the claim a later artifact is most able to undo.

        Nothing about a brand-new child changes any stored evidence ref, so
        without this rule a covered requirement would never be looked at again
        - and a new issue in the same repository narrowing or contradicting
        that coverage would be reused straight past. Scoped to the repository
        the evidence came from: one new child must not reassess everything.
        """
        new_child = "example-org/example-quota#303"
        self.run_once(
            REQUIREMENTS,
            [
                assessment("AC1", "Evidence found", [{"ref": PR_A}], "merged", "confirmed"),
                assessment("AC2", "Evidence found", [{"ref": CHILD_C}], "merged", "confirmed"),
            ],
            generated_at="2026-10-01T00:00:00Z",
        )
        self.world["issues"][new_child] = issue(new_child, "Tighten tier routing")
        self.world["subIssues"][EPIC] = [CHILD_A, CHILD_B, CHILD_C, new_child]
        self.world["timeline"][new_child] = []

        plan = self.plan(self.collect(), REQUIREMENTS)
        self.assertEqual(plan["inventoryChanges"]["artifactsAdded"], [new_child])
        self.assertEqual(plan["inventoryChanges"]["contentChanged"], [])
        # AC1's evidence is in example-quota, AC2's in example-meter. Only AC1,
        # so this is targeted at the repository rather than firing on any
        # addition anywhere in the traversal.
        self.assertEqual([entry["id"] for entry in plan["reassess"]], ["AC1"])
        self.assertIn("new upstream work appeared", plan["reassess"][0]["reason"])
        self.assertEqual([entry["id"] for entry in plan["reuse"]], ["AC2"])

    def test_a_dependency_closing_between_runs_invalidates_what_rests_on_it(self):
        """A declared dependency is inspected but not traversed, so it has no child hash."""
        dependency = "example-org/example-meter#900"
        self.world["issues"][CHILD_A]["body"] = f"Routing work. Depends on {dependency}"
        self.world["issues"][dependency] = {
            "title": "Meter API", "body": "", "state": "OPEN", "stateReason": "",
            "url": f"https://github.com/{dependency.replace('#', '/issues/')}",
            "createdAt": "2026-08-01T00:00:00Z",
            "updatedAt": "2026-09-01T00:00:00Z", "closedAt": None,
        }
        self.cite_pr()
        self.run_once(
            REQUIREMENTS,
            [
                assessment("AC1", "Evidence found", [{"ref": dependency}], "merged", "confirmed"),
                assessment("AC2", "Evidence found", [{"ref": PR_B}], "merged", "confirmed"),
            ],
            generated_at="2026-10-01T00:00:00Z",
        )
        self.world["issues"][dependency]["state"] = "CLOSED"
        self.world["issues"][dependency]["stateReason"] = "COMPLETED"

        plan = self.plan(self.collect(), REQUIREMENTS)
        self.assertIn(dependency, plan["inventoryChanges"]["dependenciesChanged"])
        # Only AC1: nothing else about the upstream tree moved, so this proves
        # the dependency state is what invalidated it.
        self.assertEqual([entry["id"] for entry in plan["reassess"]], ["AC1"])
        self.assertEqual(plan["inventoryChanges"]["contentChanged"], [])

    def test_changed_child_body_reassesses_the_requirement_resting_on_it(self):
        requirements = list(REQUIREMENTS) + [
            {"id": "AC3", "sourceKey": KEY, "type": "AC",
             "text": "Meter integration reports per-tier usage."}
        ]
        self.run_once(
            requirements,
            [
                assessment("AC1", "Evidence found", [{"ref": CHILD_A}], "merged", "confirmed"),
                assessment("AC2", "No evidence found", [], "none"),
                assessment("AC3", "Evidence found", [{"ref": CHILD_C}], "merged", "confirmed"),
            ],
            generated_at="2026-10-01T00:00:00Z",
        )
        self.world["issues"][CHILD_A]["body"] = "Now describes a different routing rule."

        manifest = self.collect()
        plan = self.plan(manifest, requirements)
        self.assertIn(CHILD_A, plan["inventoryChanges"]["contentChanged"])
        self.assertEqual(
            [entry["id"] for entry in plan["reassess"]],
            ["AC1", "AC2"],
            "AC1 rests on the changed issue; AC2 has no evidence yet, so a change "
            "anywhere upstream could be the evidence it was missing",
        )
        self.assertEqual([entry["id"] for entry in plan["reuse"]], ["AC3"])
        self.assertTrue(plan["reuse"][0]["reused"])
        self.assertEqual(plan["reuse"][0]["assessedAt"], "2026-10-01T00:00:00Z")

    def test_pr_state_change_is_detected_without_any_issue_change(self):
        """`updatedAt` on the issue does not move when its PR merges."""
        self.world["prs"][PR_B] = pull(PR_B, state="OPEN")
        self.world["timeline"][CHILD_B] = [crossref(PR_B)]
        self.world["prFiles"][PR_B] = {"changedFiles": 1, "files": [{"path": "a.go"}],
                                       "closingIssuesReferences": []}
        self.world["checks"][PR_B] = [{"name": "unit", "bucket": "pending"}]
        before = self.collect()

        self.world["prs"][PR_B] = pull(PR_B, merged="2026-10-20T09:00:00Z")
        self.world["checks"][PR_B] = [{"name": "unit", "bucket": "pass"}]
        after = self.collect()

        self.assertEqual(
            self.world["issues"][CHILD_B]["updatedAt"], "2026-09-01T00:00:00Z",
            "the fixture must leave the issue untouched for this test to mean anything",
        )
        before_hash = {child["ref"]: child["contentHash"] for child in before["children"]}
        after_hash = {child["ref"]: child["contentHash"] for child in after["children"]}
        self.assertNotEqual(before_hash[CHILD_B], after_hash[CHILD_B])
        self.assertEqual(before_hash[CHILD_A], after_hash[CHILD_A])

    def test_added_and_removed_scope_is_reported_with_a_like_for_like_comparison(self):
        self.run_once(
            REQUIREMENTS,
            [
                assessment("AC1", "Evidence found", [{"ref": PR_A, "kind": "pr", "state": "merged",
                                                      "at": "2026-09-18T09:00:00Z"}], "merged", "confirmed"),
                assessment("AC2", "No evidence found", [], "none"),
            ],
            generated_at="2026-10-01T00:00:00Z",
        )
        grown = list(REQUIREMENTS) + [
            {"id": "AC3", "sourceKey": KEY, "type": "AC", "text": "Quota breaches emit an audit event."},
            {"id": "DoD1", "sourceKey": KEY, "type": "DoD", "text": "Runbook updated."},
        ]
        _, plan, _, report = self.run_once(
            grown,
            [
                assessment("AC3", "No evidence found", [], "none"),
                assessment("DoD1", "No evidence found", [], "none"),
            ],
            generated_at="2026-10-08T00:00:00Z",
        )
        self.assertEqual(
            sorted(item["id"] for item in plan["requirementChanges"]["added"]), ["AC3", "DoD1"]
        )
        self.assertEqual(plan["requirementChanges"]["removed"], [])
        self.assertIn("**Scope added.**", report)
        self.assertIn("The denominator rose from 2 to 4", report)
        self.assertIn("present and unchanged in both", report)
        self.assertIn("Requirement mix:", report)
        self.assertIn("1/4 (25%)", report)

        # ... and shrinking it back is a removal, with the old verdict named.
        _, plan, _, report = self.run_once(
            REQUIREMENTS[:1],
            [],
            generated_at="2026-10-15T00:00:00Z",
        )
        removed = sorted(item["id"] for item in plan["requirementChanges"]["removed"])
        self.assertEqual(removed, ["AC2", "AC3", "DoD1"])
        self.assertIn("**Scope removed.**", report)
        self.assertIn("1/1 (100%)", report)

    def test_renumbering_is_matched_on_text_and_not_counted_as_a_change(self):
        previous = [dict(REQUIREMENTS[0], id="AC1"), dict(REQUIREMENTS[1], id="AC2")]
        current = [
            {"id": "AC1", "sourceKey": KEY, "type": "AC", "text": "A newly inserted first criterion."},
            dict(REQUIREMENTS[0], id="AC2"),
            dict(REQUIREMENTS[1], id="AC3"),
        ]
        match = diff_mod.match_requirements(previous, current)
        self.assertEqual(len(match["matched"]), 2)
        self.assertEqual(len(match["added"]), 1)
        self.assertEqual(match["removed"], [])
        self.assertEqual(
            sorted((item["previousId"], item["currentId"]) for item in match["renumbered"]),
            [("AC1", "AC2"), ("AC2", "AC3")],
        )

    def test_access_lost_then_restored(self):
        self.run_once(
            REQUIREMENTS,
            [
                assessment("AC1", "Evidence found", [{"ref": CHILD_C}], "merged", "confirmed"),
                assessment("AC2", "No evidence found", [], "none"),
            ],
            generated_at="2026-10-01T00:00:00Z",
        )
        self.world["missing"] = ["example-org/example-meter"]
        manifest = self.collect()
        plan = self.plan(manifest, REQUIREMENTS)
        self.assertIn("example-org/example-meter", plan["inventoryChanges"]["accessLost"])
        self.assertIn("AC1", [entry["id"] for entry in plan["reassess"]])

        _, _, _, report = self.run_once(
            REQUIREMENTS,
            [assessment("AC1", "Unable to assess", [], "not observed",
                        gap="Restore access to example-org/example-meter."),
             assessment("AC2", "No evidence found", [], "none")],
            generated_at="2026-10-08T00:00:00Z",
        )
        self.assertIn("**Access changed.**", report)
        self.assertIn("could not be read this run", report)
        self.assertIn("has not been withdrawn", report)

        del self.world["missing"]
        manifest = self.collect()
        plan = self.plan(manifest, REQUIREMENTS)
        self.assertIn("example-org/example-meter", plan["inventoryChanges"]["accessRestored"])

    def test_newly_discovered_evidence_is_not_reported_as_progress(self):
        pairs = [{"currentId": "AC1", "previousId": "AC1",
                  "previousAssessment": "No evidence found", "textChanged": False}]
        old = metrics_mod.classify_assessment_changes(
            pairs,
            [{"id": "AC1", "sourceKey": KEY, "assessment": "Evidence found",
              "evidence": [{"ref": PR_A, "at": "2026-05-01T00:00:00Z"}]}],
            "2026-10-01T00:00:00Z",
        )
        self.assertEqual(old[0]["cause"], "newly-discovered-evidence")

        new = metrics_mod.classify_assessment_changes(
            pairs,
            [{"id": "AC1", "sourceKey": KEY, "assessment": "Evidence found",
              "evidence": [{"ref": PR_A, "at": "2026-10-21T00:00:00Z"}]}],
            "2026-10-01T00:00:00Z",
        )
        self.assertEqual(new[0]["cause"], "implementation-progress")

        undated = metrics_mod.classify_assessment_changes(
            pairs,
            [{"id": "AC1", "sourceKey": KEY, "assessment": "Evidence found",
              "evidence": [{"ref": PR_A}]}],
            "2026-10-01T00:00:00Z",
        )
        self.assertEqual(undated[0]["cause"], "undetermined")

    def test_a_child_reachable_from_two_epics_is_counted_once(self):
        second = "example-org/example-quota#310"
        self.world["issues"][second] = issue(second, "Second epic", body=f"- [ ] {CHILD_C}")
        self.world["subIssues"][second] = [CHILD_B]
        self.world["timeline"][second] = []
        manifest = self.collect(epics=(EPIC, second))

        refs = [child["ref"] for child in manifest["children"]]
        self.assertEqual(len(refs), len(set(refs)))
        shared = next(child for child in manifest["children"] if child["ref"] == CHILD_B)
        self.assertEqual(sorted(shared["epics"]), sorted([EPIC, second]))
        cross = next(child for child in manifest["children"] if child["ref"] == CHILD_C)
        self.assertTrue(cross["crossRepo"], "a child in another repo keeps its attribution")

    def test_an_unreadable_epic_yields_unknown_not_zero(self):
        self.world["missing"] = [EPIC]
        manifest = self.collect()
        self.assertFalse(manifest["observed"])
        computed = metrics_mod.compute([], manifest["children"], observed=manifest["observed"],
                                       unobserved_reason=manifest["unobservedReason"])
        self.assertEqual(metrics_mod.render_ratio(computed["children"]), "unknown")
        self.assertEqual(metrics_mod.render_ratio(computed["coverage"]), "N/A")

    # --- nested epics ---------------------------------------------------

    def nested(self, manifest, ref):
        return next(child for child in manifest["children"] if child["ref"] == ref)

    def test_a_child_naming_its_parent_is_not_a_nested_epic(self):
        self.world["issues"][CHILD_B] = issue(
            CHILD_B, "Expose quota metrics", body=f"Parent {EPIC}. Related: {CHILD_A}."
        )
        manifest = self.collect()
        child = self.nested(manifest, CHILD_B)
        self.assertFalse(child["nested"], "two references in a body are not two children")
        self.assertIsNone(child["nestedVia"])
        self.assertEqual([n for n in manifest["traversalNotes"] if "nested epic" in n], [])

    def _grandchildren(self):
        """CHILD_B becomes a nested epic with two children of its own."""
        for ref, title in (
            ("example-org/example-quota#901", "Quota metrics exporter"),
            ("example-org/example-quota#902", "Quota metrics dashboard"),
        ):
            self.world["issues"][ref] = issue(ref, title)
            self.world["timeline"][ref] = []
        self.world["subIssues"][CHILD_B] = [
            "example-org/example-quota#901",
            "example-org/example-quota#902",
        ]

    def test_a_nested_epic_reached_by_a_declared_relation_is_traversed_one_level(self):
        """CHILD_B is one of the epic's own sub-issues, so its children are in scope."""
        self._grandchildren()
        manifest = self.collect()
        child = self.nested(manifest, CHILD_B)
        self.assertTrue(child["nested"])
        self.assertEqual(child["nestedVia"], "sub-issues")
        self.assertTrue(child["nestedTraversed"])

        refs = [c["ref"] for c in manifest["children"]]
        self.assertIn("example-org/example-quota#901", refs)
        self.assertIn("example-org/example-quota#902", refs)
        self.assertEqual(manifest["untraversed"], [])

        grandchild = self.nested(manifest, "example-org/example-quota#901")
        self.assertEqual(grandchild["depth"], 1)
        # Attributed to the nested epic that owns it, not to the top epic.
        self.assertEqual(grandchild["epics"], [CHILD_B])

    def test_a_nested_epic_found_only_by_a_mention_is_recorded_not_traversed(self):
        """A timeline cross-reference establishes a mention, not membership.

        This is the case that made the whole distinction necessary: descending
        through a mention attaches whatever happened to link to the epic - a
        duplicate, a bot, a "see also" - to this Jira issue's criteria.
        """
        self._grandchildren()
        mentioned = "example-org/example-quota#420"
        self.world["issues"][mentioned] = issue(mentioned, "Adjacent metering epic")
        self.world["timeline"][mentioned] = []
        self.world["subIssues"][mentioned] = [
            "example-org/example-quota#950",
            "example-org/example-quota#951",
        ]
        self.world["timeline"][EPIC] = [crossref(mentioned, kind="issue")]
        manifest = self.collect()

        child = self.nested(manifest, mentioned)
        self.assertEqual(child["discoveredVia"], "timeline-cross-reference")
        self.assertTrue(child["nested"])
        self.assertFalse(child["nestedTraversed"])
        self.assertNotIn(
            "example-org/example-quota#950", [c["ref"] for c in manifest["children"]]
        )

        recorded = manifest["untraversed"]
        self.assertEqual([entry["ref"] for entry in recorded], [mentioned])
        self.assertIn("mention rather than membership", recorded[0]["reason"])
        # The declared one next to it is still traversed: the rule is about the
        # relation, not about nesting.
        self.assertTrue(self.nested(manifest, CHILD_B)["nestedTraversed"])

    def test_traversal_stops_at_one_level_and_says_so(self):
        self._grandchildren()
        deep = "example-org/example-quota#901"
        self.world["subIssues"][deep] = [
            "example-org/example-quota#960",
            "example-org/example-quota#961",
        ]
        manifest = self.collect()

        self.assertNotIn(
            "example-org/example-quota#960", [c["ref"] for c in manifest["children"]]
        )
        recorded = manifest["untraversed"]
        self.assertEqual([entry["ref"] for entry in recorded], [deep])
        self.assertIn("1 level below", recorded[0]["reason"])

    def test_a_cycle_between_a_child_and_its_parent_terminates(self):
        """CHILD_B lists the epic and CHILD_A as sub-issues; both are already seen."""
        self.world["subIssues"][CHILD_B] = [EPIC, CHILD_A]
        manifest = self.collect()
        refs = [c["ref"] for c in manifest["children"]]
        self.assertEqual(len(refs), len(set(refs)))
        self.assertNotIn(EPIC, refs)

    def test_a_forbidden_sub_issue_list_is_a_limitation_not_an_empty_branch(self):
        """403 used to read as "no children", turning tracked work into a gap."""
        self.world["forbiddenSubIssues"] = [CHILD_B]
        manifest = self.collect()
        refused = [a for a in manifest["access"] if a["status"] == "forbidden"]
        self.assertTrue(refused, "a refused sub-issue list has to reach the access list")
        self.assertFalse(manifest["traversalComplete"])

    def test_the_scope_caveat_agrees_with_itself_on_one_nested_epic(self):
        self._grandchildren()
        mentioned = "example-org/example-quota#420"
        self.world["issues"][mentioned] = issue(mentioned, "Adjacent metering epic")
        self.world["timeline"][mentioned] = []
        self.world["subIssues"][mentioned] = [
            "example-org/example-quota#950",
            "example-org/example-quota#951",
        ]
        self.world["timeline"][EPIC] = [crossref(mentioned, kind="issue")]
        manifest = self.collect()
        caveat = summary_mod._scope_caveat(manifest)
        self.assertIn("1 nested epic was recorded but not traversed", caveat)
        # The traversed one must not be counted as a gap, however it is phrased
        # in the notes.
        self.assertNotIn("2 nested epics", caveat)

    def test_one_sub_issue_is_a_child_not_a_nested_epic(self):
        self.world["subIssues"][CHILD_B] = ["example-org/example-quota#901"]
        manifest = self.collect()
        self.assertFalse(self.nested(manifest, CHILD_B)["nested"])

    def test_an_epic_label_marks_a_nested_epic_without_asking_github(self):
        self.world["issues"][CHILD_B] = issue(
            CHILD_B, "Metering epic", labels=[{"name": "Epic"}]
        )
        manifest = self.collect()
        child = self.nested(manifest, CHILD_B)
        self.assertTrue(child["nested"])
        self.assertEqual(child["nestedVia"], "label")

    def test_body_references_decide_only_when_sub_issues_cannot_answer(self):
        """A repo without the sub-issues feature 404s, and the body is all there is.

        Even then an upward reference is not a child: the fallback has to drop
        the epic being traversed before it counts.
        """
        self.world["noSubIssues"] = ["example-org/example-quota"]
        self.world["issues"][EPIC] = issue(
            EPIC, "Tiered quota enforcement", body=f"- [ ] {CHILD_A}\n- [ ] {CHILD_B}\n"
        )
        self.world["issues"][CHILD_A] = issue(
            CHILD_A,
            "Route by tier",
            body="- [ ] example-org/example-quota#901\n- [ ] example-org/example-quota#902\n",
        )
        self.world["issues"][CHILD_B] = issue(
            CHILD_B, "Expose quota metrics", body=f"Parent {EPIC}. Tracks {CHILD_A}."
        )
        manifest = self.collect()
        self.assertEqual(self.nested(manifest, CHILD_A)["nestedVia"], "body-references")
        self.assertFalse(
            self.nested(manifest, CHILD_B)["nested"],
            "the epic being traversed is not one of its child's children",
        )

    # --- unobserved runs are not all the same -----------------------------

    def unobserved_report(self, mappings=(EPIC,)):
        manifest = self.collect()
        plan = self.plan(manifest, REQUIREMENTS)
        result = assemble_mod.build(
            {
                "jira": {"key": KEY, "summary": "Tiered quota", "status": "In Progress"},
                "mappings": [{"ref": ref} for ref in mappings],
                "manifest": manifest,
                "diff": plan,
                "requirements": REQUIREMENTS,
                "assessments": [],
                "summary": "Nothing upstream could be read.",
                "generatedAt": "2026-10-01T00:00:00Z",
            }
        )
        return manifest, plan, result

    def test_a_forbidden_epic_is_not_reported_as_a_missing_mapping(self):
        self.world["forbidden"] = ["example-org/example-quota"]
        manifest, plan, result = self.unobserved_report()

        self.assertEqual(manifest["unobservedKind"], scope_mod.ACCESS_DENIED)
        self.assertIn("access to it was denied", manifest["unobservedReason"])
        report = result["report"]
        self.assertIn("Unknown — upstream access denied", report)
        self.assertNotIn("upstream mapping missing", report)
        # The link is already correct; asking for it again is the wrong action.
        self.assertIn("Read access to example-org/example-quota#300", report)
        self.assertIn("read access to the linked", plan["autoFillGap"])

    def test_a_missing_epic_is_reported_as_a_bad_link_not_an_absent_one(self):
        self.world["missing"] = [EPIC]
        manifest, plan, result = self.unobserved_report()

        self.assertEqual(manifest["unobservedKind"], scope_mod.NOT_FOUND)
        report = result["report"]
        self.assertIn("Unknown — upstream epic not found", report)
        self.assertNotIn("upstream mapping missing", report)
        self.assertIn("could not be found", plan["autoFillGap"])

    def test_no_mapping_produces_a_partial_report_not_a_zero_one(self):
        manifest = collect_mod.empty_manifest(KEY)
        plan = diff_mod.plan({"snapshot": None}, manifest, REQUIREMENTS, [])
        self.assertEqual(plan["autoFill"], scope_mod.AUTO_FILL)
        self.assertEqual(manifest["unobservedKind"], scope_mod.NO_MAPPING)
        result = assemble_mod.build(
            {
                "jira": {"key": KEY, "summary": "Tiered quota", "status": "In Progress",
                         "fixVersions": ["2.26"]},
                "mappings": [],
                "manifest": manifest,
                "diff": plan,
                "requirements": REQUIREMENTS,
                "assessments": [],
                "summary": "No upstream link is recorded.",
                "generatedAt": "2026-10-01T00:00:00Z",
            }
        )
        report = result["report"]
        self.assertIn("Unknown — upstream mapping missing", report)
        self.assertIn("#### Jira scope", report)
        self.assertIn("What is needed to complete this assessment", report)
        self.assertNotIn("#### Progress", report)
        self.assertEqual(report.count("Unable to assess"), 2)
        self.assertIn("0% reflects absent assessment", report)
        self.assertIn("No upstream link was found on RHOAIENG-7001", report)

    def test_a_missing_assessment_is_an_error_not_a_verdict(self):
        manifest = self.collect()
        plan = self.plan(manifest, REQUIREMENTS)
        with self.assertRaises(ValueError) as caught:
            assemble_mod.build(
                {
                    "jira": {"key": KEY},
                    "mappings": [],
                    "manifest": manifest,
                    "diff": plan,
                    "requirements": REQUIREMENTS,
                    "assessments": [assessment("AC1", "Evidence found",
                                               [{"ref": PR_A, "kind": "pr"}], "merged")],
                    "summary": "x",
                    "generatedAt": "2026-10-01T00:00:00Z",
                },
                write_snapshot=False,
            )
        self.assertIn("AC2", str(caught.exception))

    def test_full_refresh_reassesses_everything(self):
        self.run_once(
            REQUIREMENTS,
            [assessment("AC1", "Evidence found", [{"ref": PR_A, "kind": "pr"}], "merged"),
             assessment("AC2", "No evidence found", [], "none")],
            generated_at="2026-10-01T00:00:00Z",
        )
        manifest = self.collect()
        plan = self.plan(manifest, REQUIREMENTS, full_refresh=True)
        self.assertIn("full refresh requested", plan["reassessAll"])
        self.assertEqual(len(plan["reassess"]), 2)
        self.assertEqual(plan["reuse"], [])

    def test_a_schema_v1_baseline_is_readable_but_forces_reassessment(self):
        directory = cache_mod.snapshot_dir(KEY)
        os.makedirs(directory, exist_ok=True)
        legacy = {
            "schemaVersion": 1,
            "jiraKey": KEY,
            "generatedAt": "2026-09-01T00:00:00Z",
            "publication": "published",
            "mappings": [{"epic": EPIC, "linkSource": "upstream-development-section"}],
            "scope": {"children": [{"ref": CHILD_A, "state": "CLOSED", "stateReason": "COMPLETED"}]},
            "requirements": [dict(REQUIREMENTS[0], assessment="Evidence found", evidence=[])],
        }
        with open(os.path.join(directory, "20260901T000000Z-published.json"), "w", encoding="utf-8") as handle:
            json.dump(legacy, handle)

        manifest = self.collect()
        plan = self.plan(manifest, REQUIREMENTS)
        self.assertIsNotNone(plan["baseline"])
        self.assertIn(
            "baseline predates content hashing, so reuse cannot be verified", plan["reassessAll"]
        )
        self.assertEqual(len(plan["reassess"]), 2)

    def test_snapshots_are_append_only(self):
        self.run_once(
            REQUIREMENTS,
            [assessment("AC1", "Evidence found", [{"ref": PR_A, "kind": "pr"}], "merged"),
             assessment("AC2", "No evidence found", [], "none")],
            generated_at="2026-10-01T00:00:00Z",
        )
        self.run_once(REQUIREMENTS, [], generated_at="2026-10-01T00:00:00Z")
        files = snapshots_mod.list_snapshots(KEY)
        self.assertEqual(len(files), 2, "a same-second rerun must not overwrite the baseline")

    def test_promote_renames_the_draft_and_records_the_comment(self):
        _, _, result, _ = self.run_once(
            REQUIREMENTS,
            [assessment("AC1", "Evidence found", [{"ref": PR_A, "kind": "pr"}], "merged"),
             assessment("AC2", "No evidence found", [], "none")],
            generated_at="2026-10-01T00:00:00Z",
        )
        promoted = snapshots_mod.promote(result["snapshotPath"], "10042")
        self.assertTrue(promoted.endswith("-published.json"))
        data, problem = snapshots_mod.load(promoted)
        self.assertIsNone(problem)
        self.assertEqual(data["jiraCommentId"], "10042")
        self.assertFalse(os.path.exists(result["snapshotPath"]))


class ReferenceTest(unittest.TestCase):
    def test_explicit_links_win_and_incidental_ones_are_flagged(self):
        found = refs_mod.collect(
            {
                "jiraKey": KEY,
                "descriptionSections": [
                    {"heading": "Upstream Development", "text": f"https://github.com/{EPIC.replace('#', '/issues/')}"}
                ],
                "comments": [{"id": "1", "created": "2026-09-01T00:00:00Z",
                              "body": "see https://github.com/example-org/other/issues/9"}],
            }
        )
        self.assertTrue(found["mappingFound"])
        self.assertEqual([epic["ref"] for epic in found["epics"]], [EPIC])
        # The explicit link is used without asking; the stray one in a comment
        # is offered as a question rather than silently rolled up or dropped.
        self.assertEqual(found["question"]["kind"], "incidental-extras")
        self.assertEqual(
            [option["ref"] for option in found["question"]["options"]], ["example-org/other#9"]
        )

    def test_two_incidental_links_and_no_explicit_one_ask_rather_than_guess(self):
        found = refs_mod.collect(
            {
                "jiraKey": KEY,
                "description": (
                    "see https://github.com/example-org/a/issues/1 and "
                    "https://github.com/example-org/b/issues/2"
                ),
            }
        )
        self.assertFalse(found["mappingFound"])
        self.assertIsNotNone(found["question"])

    def test_the_same_epic_written_three_ways_is_one_epic(self):
        found = refs_mod.collect(
            {
                "jiraKey": KEY,
                "descriptionSections": [
                    {
                        "heading": "Upstream Development",
                        "text": (
                            "https://github.com/example-org/example-quota/issues/300 "
                            "example-org/example-quota#300 "
                            "https://github.com/example-org/example-quota/issues/300#issuecomment-5"
                        ),
                    }
                ],
            }
        )
        self.assertEqual([epic["ref"] for epic in found["epics"]], [EPIC])


class ConversionTest(unittest.TestCase):
    DRAFT = (
        "### Upstream Development Rollup\n\n"
        "**Status:** In progress\n"
        "**Source epic:** [example-org/example-quota#300](https://github.com/example-org/example-quota/issues/300)\n\n"
        "#### Requirements coverage\n\n"
        "| Requirement | Outcome | Evidence | Evidence state | Coverage | Gap / next validation step |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| AC1 (RHOAIENG-7001) \"a \\| b\" | Outcomes met | PR example-org/example-quota#500 | merged | Evidence found | — |\n\n"
        "---\n\n"
        "_Generated by the jira-github-rollup skill from example-org/example-quota#300._\n"
    )

    def test_wiki_conversion_drops_the_separator_row_and_rewrites_links(self):
        wiki = convert_mod.to_wiki(self.DRAFT)
        self.assertIn("h3. Upstream Development Rollup", wiki)
        self.assertIn("h4. Requirements coverage", wiki)
        self.assertIn("|| Requirement || Outcome || Evidence ||", wiki)
        self.assertNotIn("| --- |", wiki)
        self.assertIn("[example-org/example-quota#300|https://github.com/", wiki)
        self.assertIn("*Status:*", wiki)
        self.assertIn("----", wiki)

    def test_plain_conversion_expands_the_coverage_table_into_blocks(self):
        plain = convert_mod.to_plain(self.DRAFT)
        self.assertIn("Upstream Development Rollup", plain)
        self.assertIn("  Evidence: PR example-org/example-quota#500", plain)
        self.assertIn("  State: merged", plain)
        self.assertIn("  Coverage: Evidence found", plain)
        self.assertNotIn("|", plain.replace('"a | b"', ""))

    def test_the_marker_sentence_survives_every_target(self):
        sentence = "Generated by the jira-github-rollup skill from example-org/example-quota#300."
        for target in ("gfm", "wiki", "plain"):
            self.assertIn(sentence, convert_mod.convert(self.DRAFT, target), target)

    def test_an_escaped_pipe_inside_a_cell_is_not_a_column_break(self):
        rows = convert_mod._cells(
            "| AC1 (RHOAIENG-7001) \"a \\| b\" | Outcomes met | PR #500 | merged | Evidence found | — |"
        )
        self.assertEqual(len(rows), 6)
        self.assertIn('"a | b"', rows[0])


class MetricTest(unittest.TestCase):
    def test_partial_evidence_earns_no_fractional_credit(self):
        computed = metrics_mod.requirement_metrics(
            [
                {"id": "AC1", "assessment": "Evidence found"},
                {"id": "AC2", "assessment": "Partial evidence"},
                {"id": "AC3", "assessment": "Unable to assess"},
                {"id": "AC4", "assessment": "No evidence found"},
            ]
        )
        self.assertEqual(metrics_mod.render_ratio(computed["coverage"]), "1/4 (25%)")

    def test_unknown_and_not_applicable_are_different_values(self):
        self.assertEqual(metrics_mod.render_ratio(metrics_mod.ratio(0, 0)), "N/A")
        self.assertEqual(metrics_mod.render_ratio(metrics_mod.ratio(0, 0, observed=False)), "unknown")

    def test_percentage_points_come_from_unrounded_percentages(self):
        before = metrics_mod.ratio(1, 3)   # 33.33%
        after = metrics_mod.ratio(2, 3)    # 66.67%
        moved = metrics_mod.delta(before, after)
        self.assertEqual(moved["pp"], 33)
        self.assertEqual(moved["count"], 1)

    def test_a_closed_issue_with_no_reason_is_its_own_bucket(self):
        buckets = metrics_mod.child_metrics(
            [
                {"ref": "a#1", "state": "CLOSED", "stateReason": "COMPLETED"},
                {"ref": "a#2", "state": "CLOSED", "stateReason": ""},
                {"ref": "a#3", "state": "CLOSED", "stateReason": "NOT_PLANNED"},
            ]
        )
        self.assertEqual(buckets["buckets"]["completed"], 1)
        self.assertEqual(buckets["buckets"]["noReasonRecorded"], 1)
        self.assertEqual(metrics_mod.render_ratio(buckets), "1/3 (33%)",
                         "not-planned and unrecorded reasons stay in the denominator")


class TwoOutputTest(PipelineTest):
    """The contract between the full assessment and the Jira summary draft.

    Each test here is a way the pair could quietly disagree, or a way the
    summary could say something it has no basis for. They matter more than
    most: the summary is the only one of the two that anybody posts, and it is
    read by people who will never open the evidence table it came from.
    """

    def both(self, assessments=None, requirements=None, **kwargs):
        _, _, result, report = self.run_once(
            requirements if requirements is not None else REQUIREMENTS,
            assessments
            if assessments is not None
            else [
                assessment("AC1", "Evidence found",
                           [{"ref": PR_A, "kind": "pr", "state": "merged",
                             "at": "2026-09-18T09:00:00Z"}], "merged"),
                assessment("AC2", "No evidence found", [], "none"),
            ],
            generated_at=kwargs.pop("generated_at", "2026-10-01T00:00:00Z"),
            **kwargs,
        )
        return result, report, result["summary"]

    def bullet(self, summary, label):
        """One named bullet of the summary, or "" if it is absent."""
        prefix = f"- **{label}:**"
        for line in summary.splitlines():
            if line.startswith(prefix):
                return line[len(prefix):].strip()
        return ""

    def test_the_counts_agree_across_both_outputs_and_sum_to_the_total(self):
        result, report, summary = self.both()
        counts = result["outcomes"]
        self.assertEqual(sum(counts.values()), len(REQUIREMENTS))
        row = "| " + " | ".join(str(counts[name]) for name in outcomes_mod.OUTCOMES) + " |"
        self.assertIn(row, report)
        self.assertIn(row, summary)
        self.assertIn("Upstream evidence assessment, not release completion.", summary)

    def test_missing_evidence_is_unverified_and_never_confirmed_unmet(self):
        result, report, summary = self.both()
        self.assertEqual(result["outcomes"]["unverified"], 1)
        self.assertEqual(result["outcomes"]["confirmed-unmet"], 0)
        self.assertNotIn("Confirmed unmet | ", summary.split("|")[0])
        self.assertIn("is not a finding that the work does not exist", report)

    def test_confirmed_unmet_is_refused_unless_something_refutes_the_criterion(self):
        declared = assessment("AC2", "No evidence found", [], "none")
        declared["outcome"] = "confirmed-unmet"
        with self.assertRaises(ValueError) as caught:
            self.both(
                assessments=[
                    assessment("AC1", "Evidence found",
                               [{"ref": PR_A, "kind": "pr", "state": "merged",
                                 "at": "2026-09-18T09:00:00Z"}], "merged"),
                    declared,
                ]
            )
        self.assertIn("absence of evidence is 'unverified'", str(caught.exception))

    def test_confirmed_unmet_is_honoured_when_something_is_cited(self):
        declared = assessment("AC2", "No evidence found", [{"ref": self.cite_pr()}], "merged")
        declared["outcome"] = "confirmed-unmet"
        result, _, summary = self.both(assessments=[self._merged(), declared])
        self.assertEqual(result["outcomes"]["confirmed-unmet"], 1)
        self.assertEqual(result["outcomes"]["unverified"], 0)
        self.assertEqual(sum(result["outcomes"].values()), 2)

    def _merged(self, requirement_id="AC1"):
        return assessment(
            requirement_id, "Evidence found",
            [{"ref": PR_A, "kind": "pr", "state": "merged", "at": "2026-09-18T09:00:00Z"}],
            "merged",
        )

    def test_evidence_found_is_refused_while_a_clause_is_undecided(self):
        """The rule requirements.md already states, now enforced rather than hoped for.

        A two-clause criterion whose second clause names a TBD is not met,
        however good the evidence for the first clause is.
        """
        claim = self._merged()
        claim["unresolvedClauses"] = ["the retention window is given as TBD"]
        with self.assertRaises(ValueError) as caught:
            self.both(assessments=[claim, assessment("AC2", "No evidence found", [], "none")])
        message = str(caught.exception)
        self.assertIn("claims every clause of the criterion holds", message)
        self.assertIn("undecided: the retention window is given as TBD", message)

    def test_evidence_found_is_refused_while_a_clause_is_unsupported(self):
        claim = self._merged()
        claim["uncoveredClauses"] = ["nothing establishes the per-tier rate limit"]
        with self.assertRaises(ValueError) as caught:
            self.both(assessments=[claim, assessment("AC2", "No evidence found", [], "none")])
        self.assertIn(
            "unsupported by evidence: nothing establishes the per-tier rate limit",
            str(caught.exception),
        )

    def test_the_same_criterion_assessed_partial_with_open_clauses_is_accepted(self):
        """The refusal has to leave a correct way through, or it just blocks the run."""
        claim = assessment(
            "AC1", "Partial evidence",
            [{"ref": PR_A, "kind": "pr", "state": "merged", "at": "2026-09-18T09:00:00Z"}],
            "merged",
        )
        claim["uncoveredClauses"] = [clause("nothing establishes the per-tier rate limit")]
        result, _, _ = self.both(
            assessments=[claim, assessment("AC2", "No evidence found", [], "none")]
        )
        self.assertEqual(result["outcomes"]["met"], 0)
        self.assertEqual(result["outcomes"]["partial"], 1)

    def test_a_clean_evidence_found_is_still_met(self):
        result, _, _ = self.both()
        self.assertEqual(result["outcomes"]["met"], 1)

    def test_an_uncovered_clause_is_named_in_the_full_assessment(self):
        """And kept apart from an undecided one: different ask, different person."""
        claim = assessment(
            "AC1", "Partial evidence",
            [{"ref": PR_A, "kind": "pr", "state": "merged", "at": "2026-09-18T09:00:00Z"}],
            "merged",
        )
        claim["uncoveredClauses"] = [clause("nothing establishes rejection above the tier quota")]
        _, report, _ = self.both(
            assessments=[claim, assessment("AC2", "No evidence found", [], "none")]
        )
        self.assertIn("Evidence gap", report)
        self.assertIn("nothing establishes rejection above the tier quota", report)
        self.assertNotIn("Decision needed", report)

    def test_open_clauses_survive_being_carried_forward(self):
        """A reused assessment must not launder a bad claim into a clean one."""
        claim = self._merged()
        claim["unresolvedClauses"] = ["the retention window is given as TBD"]
        merged, _, problems = assemble_mod.merge([REQUIREMENTS[0]], [claim], {}, "2026-10-01T00:00:00Z")
        self.assertEqual(merged[0]["unresolvedClauses"], ["the retention window is given as TBD"])
        self.assertTrue(outcomes_mod.problems(merged))

    def test_a_confirmed_unmet_criterion_is_a_finding_not_a_schedule_item(self):
        """It belongs under Decisions needed, with the artifact that refutes it.

        Describing it as "tracked and incomplete" alongside work still in
        flight is the failure: a reader skims Remaining work as a list of
        things that will arrive, and this is a thing that will not.
        """
        declared = assessment("AC2", "No evidence found", [{"ref": self.cite_pr()}], "merged")
        declared["outcome"] = "confirmed-unmet"
        _, _, summary = self.both(assessments=[self._merged(), declared])
        decisions = self.bullet(summary, "Decisions needed")
        self.assertIn("contradicted by something inspected", decisions)
        self.assertIn("confirm whether each still describes intended behaviour", decisions)
        self.assertNotIn("AC2", self.bullet(summary, "Remaining work"))

    def test_a_confirmed_unmet_criterion_does_not_prescribe_reopening_the_work(self):
        """Two answers, and the renderer is not entitled to pick one.

        "Reopen the work or revise the criterion" is a recommendation made
        before anyone has asked the question the finding actually raises -
        whether the criterion still describes what is intended to ship.
        """
        declared = assessment("AC2", "No evidence found", [{"ref": self.cite_pr()}], "merged")
        declared["outcome"] = "confirmed-unmet"
        _, _, summary = self.both(assessments=[self._merged(), declared])
        for prescription in ("reopen", "re-scope", "revise the criterion"):
            self.assertNotIn(prescription, summary.lower())
        self.assertIn(
            "record whether each stands as written", self.bullet(summary, "Next actions")
        )

    def test_an_open_decision_names_the_decision(self):
        claim = assessment(
            "AC1", "Partial evidence",
            [{"ref": PR_A, "kind": "pr", "state": "merged", "at": "2026-09-18T09:00:00Z"}],
            "merged",
        )
        claim["unresolvedClauses"] = ["the retention window is given as TBD"]
        _, _, summary = self.both(
            assessments=[claim, assessment("AC2", "No evidence found", [], "none")]
        )
        self.assertIn("the retention window is given as TBD", summary)

    def test_the_trend_says_which_baseline_it_compares_against(self):
        """"Draft snapshot" is this tool's word. The reader needs the question answered."""
        snapshot = {
            "requirements": [
                dict(REQUIREMENTS[0], assessment="No evidence found", evidence=[]),
                dict(REQUIREMENTS[1], assessment="No evidence found", evidence=[]),
            ]
        }
        for publication, expected in (
            ("published", "last update posted here on 2026-09-01"),
            ("draft", "last assessment on 2026-09-01, which was not posted here"),
        ):
            line = summary_mod.trend_line(
                {
                    "diff": {"baseline": {"generatedAt": "2026-09-01T00:00:00Z",
                                          "publication": publication}},
                    "baselineSnapshot": snapshot,
                },
                outcomes_mod.tally(snapshot["requirements"]),
            )
            self.assertIn(expected, line)
            self.assertNotIn("snapshot of", line)

    def test_a_partial_criterion_is_never_counted_as_met(self):
        result, report, _ = self.both(
            assessments=[
                assessment("AC1", "Partial evidence",
                           [{"ref": PR_A, "kind": "pr", "state": "merged",
                             "at": "2026-09-18T09:00:00Z"}], "merged"),
                assessment("AC2", "No evidence found", [], "none"),
            ]
        )
        self.assertEqual(result["outcomes"]["met"], 0)
        self.assertEqual(result["outcomes"]["partial"], 1)
        self.assertIn("| Partial |", report)

    def test_an_unmapped_criterion_becomes_a_tracking_clarification(self):
        _, report, summary = self.both()
        self.assertIn("Tracking clarification", report)
        self.assertIn(f"Identify and link the work covering {KEY} AC2", report)
        self.assertIn("identify and link the owning upstream work", summary)
        # The thing it must never say: that some other epic already has it.
        self.assertNotIn("is covered by", summary)

    def test_a_material_collection_limitation_reaches_the_summary(self):
        self.world["missing"] = ["example-org/example-meter"]
        _, report, summary = self.both(
            assessments=[
                assessment("AC1", "Evidence found",
                           [{"ref": PR_A, "kind": "pr", "state": "merged",
                             "at": "2026-09-18T09:00:00Z"}], "merged"),
                assessment("AC2", "Unable to assess", [], "not observed"),
            ]
        )
        self.assertIn("#### Collection scope and limitations", report)
        self.assertIn("Not readable", report)
        self.assertIn("Scope:", summary)
        self.assertIn("could not be read", summary)
        self.assertIn("an unverified row is not evidence that the work is missing", summary)

    def test_delivery_confidence_is_not_inferred_from_the_counts(self):
        self.cite_pr()
        result, _, summary = self.both(
            assessments=[
                assessment("AC1", "Evidence found", [{"ref": PR_A}], "merged",
                           downstream="confirmed"),
                assessment("AC2", "Evidence found", [{"ref": PR_B}], "merged",
                           downstream="confirmed"),
            ]
        )
        self.assertEqual(result["outcomes"]["met"], 2)
        self.assertEqual(result["deliveryConfidence"]["value"], "Not assessed")
        self.assertIn("no release target recorded", summary)

    def test_the_summary_carries_links_and_no_local_paths(self):
        _, _, summary = self.both()
        self.assertIn(f"https://github.com/{EPIC.split('#')[0]}/issues/300", summary)
        self.assertEqual(links_mod.unpublishable(summary), [])
        self.assertNotIn(self.home, summary)
        self.assertNotIn("file://", summary)

    def test_the_summary_stays_inside_its_word_budget(self):
        _, _, summary = self.both()
        self.assertLessEqual(summary_mod.word_count(summary), summary_mod.WORD_CEILING, summary)
        # The budget is prose a reader has to read: URLs and the outcome table
        # are scanned, not read, so neither inflates the count.
        self.assertEqual(summary_mod.word_count("[Streaming PR](https://x.test/a) landed"), 3)
        self.assertEqual(summary_mod.word_count("| 1 | 0 | 0 | 8 |"), 0)

    def test_links_survive_conversion_to_every_target_jira_accepts(self):
        _, _, summary = self.both()
        url = f"https://github.com/{EPIC.split('#')[0]}/issues/300"
        self.assertIn(url, convert_mod.convert(summary, "gfm"))
        html = convert_mod.convert(summary, "html")
        self.assertIn(f'<a href="{url}">', html)
        self.assertIn("<h3>", html)
        self.assertIn("<table><thead><tr><th>Outcomes met</th>", html)
        self.assertIn("<ul><li>", html)
        self.assertNotIn("data-type=\"layout", html)
        self.assertIn(url, convert_mod.convert(summary, "wiki"))
        self.assertIn(url, convert_mod.convert(summary, "plain"))

    def test_html_conversion_escapes_rather_than_trusting_cell_text(self):
        html = convert_mod.to_html("| A | B |\n| --- | --- |\n| <script>x</script> | b |\n")
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_a_snapshot_is_not_promoted_without_a_comment_id(self):
        result, _, summary = self.both()
        path = result["snapshotPath"]
        for bad in (None, "", "   "):
            with self.assertRaises(ValueError):
                snapshots_mod.promote(path, bad)
        self.assertTrue(path.endswith("-draft.json"), "the draft must still be a draft")
        data, _ = snapshots_mod.load(path)
        self.assertEqual(data["publication"], "draft")
        self.assertIsNone(data["publishedAt"])

    def test_promoting_records_that_the_summary_was_what_was_published(self):
        result, report, summary = self.both()
        promoted = snapshots_mod.promote(result["snapshotPath"], "10042", published_text=summary)
        data, _ = snapshots_mod.load(promoted)
        self.assertEqual(data["publication"], "published")
        self.assertEqual(data["jiraCommentId"], "10042")
        self.assertEqual(data["published"]["kind"], "summary")
        self.assertEqual(data["published"]["hash"], util.sha256(summary))
        self.assertNotEqual(data["published"]["hash"], util.sha256(report))

    def test_a_disagreement_between_the_outputs_is_an_error_not_a_report(self):
        problems = assemble_mod.cross_check(
            "| 1 | 0 | 0 | 1 |", "| 2 | 0 | 0 | 0 |",
            {"counts": {"met": 1, "partial": 0, "confirmed-unmet": 0, "unverified": 1}, "total": 2},
        )
        self.assertTrue(any("Jira summary" in problem for problem in problems))

    def test_a_local_path_in_the_summary_is_an_error_not_a_comment(self):
        problems = assemble_mod.cross_check(
            "| 1 | 0 | 0 | 1 |",
            "| 1 | 0 | 0 | 1 |\nFull assessment: /Users/someone/.jira-github-rollup/x.md",
            {"counts": {"met": 1, "partial": 0, "confirmed-unmet": 0, "unverified": 1}, "total": 2},
        )
        self.assertTrue(any("should not be published" in problem for problem in problems))

    def test_a_full_assessment_link_appears_only_when_it_is_a_real_url(self):
        tallied = outcomes_mod.tally(REQUIREMENTS)
        base = {
            "generatedAt": "2026-10-01T00:00:00Z",
            "jira": {"key": KEY, "summary": "Tiered quota"},
            "manifest": {"children": [], "epics": [], "observed": True},
            "requirements": REQUIREMENTS,
            "mappings": [],
        }
        confidence = outcomes_mod.confidence(base, REQUIREMENTS, tallied)
        local = summary_mod.render(
            base, tallied, confidence,
            full_assessment_url="/Users/someone/.jira-github-rollup/report.md",
        )
        self.assertNotIn("Full assessment", local)
        durable = summary_mod.render(
            base, tallied, confidence,
            full_assessment_url="https://example.invalid/rollups/report.md",
        )
        self.assertIn("[Full assessment](https://example.invalid/rollups/report.md)", durable)

    def test_a_changed_criteria_set_is_explained_rather_than_shown_as_progress(self):
        self.both()
        grown = REQUIREMENTS + [
            {"id": "AC3", "sourceKey": KEY, "type": "AC", "text": "Denials are metered."}
        ]
        _, _, summary = self.both(
            requirements=grown,
            assessments=[
                assessment("AC1", "Evidence found",
                           [{"ref": PR_A, "kind": "pr", "state": "merged",
                             "at": "2026-09-18T09:00:00Z"}], "merged"),
                assessment("AC2", "No evidence found", [], "none"),
                {"id": "AC3", "sourceKey": KEY, "type": "AC", "text": "Denials are metered.",
                 "assessment": "No evidence found", "evidence": [], "evidenceState": "none",
                 "downstream": {"state": "unknown", "detail": None}},
            ],
            generated_at="2026-10-08T00:00:00Z",
        )
        self.assertIn("1 criterion added (2→3)", summary)
        self.assertIn("The outcome counts are not comparable across a scope change", summary)
        # The failure this replaces: "unverified 1→2" beside "since the last
        # assessment" reads as a criterion going backwards, when what happened
        # is that somebody wrote down one more of the things they wanted.
        self.assertNotIn("unverified 1→2", summary)


class OverallAssessmentTest(PipelineTest):
    """The paragraph every rendering opens with.

    It is the one piece of prose a reader is guaranteed to read, and the only
    one that states a position rather than a row. So the checks here are not
    about whether it is well written - that is judgement, and stays with the
    model - but about the two ways a position can be wrong by construction:
    resting on rows that do not say what it claims they say, and reaching past
    what a read of issues and pull requests can establish at all.
    """

    MERGED = {"ref": PR_A}

    def met(self, requirement_id="AC1"):
        return assessment(requirement_id, "Evidence found", [self.MERGED], "merged")

    def unverified(self, requirement_id="AC2"):
        return assessment(requirement_id, "No evidence found", [], "none")

    def contradicted(self, requirement_id="AC2"):
        declared = assessment(requirement_id, "No evidence found", [{"ref": self.cite_pr()}],
                              "merged")
        declared["outcome"] = "confirmed-unmet"
        return declared

    PARAGRAPH = (
        "Tiered routing has a working implementation path in the traversed set, and the "
        "merged change behind it was inspected rather than inferred. Metering is the gap: "
        "nothing read upstream covers how consumption is exposed, which is absent evidence "
        "and not an established absence. Resolving it needs the owning upstream work linked "
        "to the criterion and the downstream qualification cited, so the next run can read a "
        "position instead of reconstructing one from the rows."
    )

    def run_with(self, overall, assessments=None):
        _, _, result, report = self.run_once(
            REQUIREMENTS,
            assessments if assessments is not None else [self.met(), self.unverified()],
            generated_at="2026-10-01T00:00:00Z",
            overall=overall,
        )
        return result, report

    def refuses(self, overall, expected, assessments=None):
        with self.assertRaises(ValueError) as caught:
            self.run_with(overall, assessments)
        self.assertIn(expected, str(caught.exception))
        return str(caught.exception)

    # --- the three shapes the brief names --------------------------------

    def test_mixed_outcomes_open_all_three_renderings_with_one_paragraph(self):
        result, report = self.run_with(
            {
                "text": self.PARAGRAPH,
                "establishes": [{"sourceKey": KEY, "id": "AC1"}],
                "unverified": [{"sourceKey": KEY, "id": "AC2"}],
                "links": [PR_A],
            }
        )
        self.assertEqual(result["overall"], self.PARAGRAPH)
        # Rendered once and carried, not regenerated per output: three
        # independent fallbacks would be three different positions.
        self.assertIn(self.PARAGRAPH, report)
        self.assertIn(self.PARAGRAPH, result["summary"])
        self.assertIn(self.PARAGRAPH, result["html"])
        self.assertIn("#### Overall assessment", report)
        self.assertIn("**Overall assessment:**", result["summary"])
        self.assertTrue(result["overallWordBudget"]["supplied"])
        self.assertTrue(result["overallWordBudget"]["within"], result["overallWords"])

    def test_an_entirely_unverified_run_falls_back_and_says_nobody_wrote_one(self):
        _, _, result, report = self.run_once(
            REQUIREMENTS,
            [self.unverified("AC1"), self.unverified("AC2")],
            generated_at="2026-10-01T00:00:00Z",
        )
        overall = result["overall"]
        self.assertIn("Nothing inspected upstream supports any of the 2 criteria", overall)
        self.assertIn("absent evidence, not established absence", overall)
        self.assertIn("No overall position was written for this run", overall)
        self.assertFalse(result["overallWordBudget"]["supplied"])
        # The fallback must not read as a finding that the work does not exist.
        self.assertEqual(assemble_mod.unscoped_claims(overall, "the fallback"), [])
        self.assertIn(overall, report)
        self.assertIn(overall, result["summary"])

    def test_a_contradicted_row_reads_as_a_finding_not_as_a_gap(self):
        _, _, result, _ = self.run_once(
            REQUIREMENTS,
            [self.met("AC1"), self.contradicted("AC2")],
            generated_at="2026-10-01T00:00:00Z",
        )
        overall = result["overall"]
        self.assertEqual(result["outcomes"]["confirmed-unmet"], 1)
        self.assertIn("contradicted by something inspected", overall)
        self.assertIn("a finding rather than a gap in the reading", overall)
        # And it is not also counted as something nobody looked at.
        self.assertNotIn("unverified in the traversed set", overall)

    def test_a_contradicted_row_may_be_cited_as_unmet(self):
        result, _ = self.run_with(
            {
                "text": self.PARAGRAPH,
                "establishes": [{"sourceKey": KEY, "id": "AC1"}],
                "unmet": [{"sourceKey": KEY, "id": "AC2"}],
            },
            assessments=[self.met("AC1"), self.contradicted("AC2")],
        )
        self.assertEqual(result["overall"], self.PARAGRAPH)

    # --- what the paragraph may not rest on ------------------------------

    def test_an_unverified_row_cannot_be_what_the_evidence_establishes(self):
        self.refuses(
            {"text": self.PARAGRAPH, "establishes": [{"sourceKey": KEY, "id": "AC2"}]},
            "is filed under 'establishes' but is unverified",
        )

    def test_missing_evidence_cannot_be_filed_as_a_confirmed_absence(self):
        self.refuses(
            {"text": self.PARAGRAPH, "unmet": [{"sourceKey": KEY, "id": "AC2"}]},
            "belongs under `unverified`",
        )

    def test_a_supported_row_cannot_be_filed_as_unverified(self):
        self.refuses(
            {"text": self.PARAGRAPH, "unverified": [{"sourceKey": KEY, "id": "AC1"}]},
            "the evidence supports it, so it is not unverified",
        )

    def test_a_row_that_was_never_assessed_is_refused(self):
        self.refuses(
            {"text": self.PARAGRAPH, "establishes": [{"sourceKey": KEY, "id": "AC9"}]},
            "which is not an assessed requirement in this run",
        )

    def test_a_paragraph_pinned_to_nothing_is_refused(self):
        self.refuses({"text": self.PARAGRAPH}, "names no assessment row")

    def test_a_link_no_cited_row_carries_is_refused(self):
        self.refuses(
            {
                "text": self.PARAGRAPH,
                "establishes": [{"sourceKey": KEY, "id": "AC1"}],
                "links": ["example-org/example-quota#999"],
            },
            "links example-org/example-quota#999, which is not evidence on any row it names",
        )

    # --- what the paragraph may not say ----------------------------------

    def pinned(self, text):
        return {"text": text, "establishes": [{"sourceKey": KEY, "id": "AC1"}]}

    def test_naming_criterion_ids_is_refused_so_the_paragraph_groups_them(self):
        self.refuses(
            self.pinned("AC1 is covered by a merged change; AC2 has nothing behind it."),
            "names AC1, AC2",
        )

    def test_a_percentage_is_refused(self):
        self.refuses(self.pinned("Routing is covered; the work is 50% complete."),
                     "carries a percentage")
        self.refuses(self.pinned("Routing is covered, which is half the criteria by percentage."),
                     "carries a percentage")

    def test_a_readiness_or_schedule_claim_is_refused(self):
        for text, fragment in (
            ("Routing is covered and the epic is on track.", "'on track'"),
            ("Routing is covered; metering will ship next.", "'will ship'"),
            ("Routing is covered and the remainder is expected by the next run.", "'expected by'"),
            ("Routing is covered and the gateway is release-ready.", "'release-ready'"),
        ):
            with self.subTest(text=text):
                self.refuses(self.pinned(text), f"{fragment} claims readiness or a date")

    def test_an_unscoped_existence_claim_is_refused(self):
        self.refuses(
            self.pinned("Routing is covered, but no upstream issue exists for metering."),
            "A traversal of one epic cannot establish that something does not exist",
        )

    def test_the_paragraph_is_refused_before_anything_is_rendered(self):
        """A rejected position must not reach a snapshot or a draft.

        The refusals above are only worth having if they stop the run. If the
        paragraph were checked after rendering, a reviewer would be looking at
        a draft that the pipeline had already decided it would not stand
        behind.
        """
        before = snapshots_mod.list_snapshots(KEY)
        self.refuses(self.pinned("The epic is on track."), "claims readiness or a date")
        self.assertEqual(snapshots_mod.list_snapshots(KEY), before)

    def test_an_overall_that_is_not_an_object_is_refused(self):
        self.refuses("Routing is covered.", "expected an object, got str")
        self.refuses({"text": "   "}, "has no text")


class FollowUpInvestigationTest(PipelineTest):
    """The investigation that stops one read short.

    The failure is always the same shape. A criterion leaves a question open,
    the file that answers it is named in evidence already collected and is
    readable, nobody opens it, and the leftover uncertainty is written up as
    though the product were missing something. These tests pin the three
    halves of the fix: the read is possible and bounded, the unresolved
    finding has to say which of the three things it is, and the two
    renderings have to say the same thing about it.
    """

    def read(self, path=ROUTER_FILE, revision=MERGE_A, repo=ROUTER_REPO, budget=None, key=KEY):
        """One follow-up read, through the same path the `source` command uses."""
        self.write_world()
        cache = cache_mod.Cache(key, reuse=True)
        kwargs = {} if budget is None else {"budget": budget}
        return followup_mod.read(Gh(), cache, repo, path, revision, **kwargs)

    def covering(self, clauses, verdict="Partial evidence"):
        """AC1 assessed with the given open clauses, AC2 left unverified."""
        claim = assessment(
            "AC1", verdict,
            [{"ref": PR_A, "kind": "pr", "state": "merged", "at": "2026-09-18T09:00:00Z"}],
            "merged",
        )
        claim["uncoveredClauses"] = clauses
        return [claim, assessment("AC2", "No evidence found", [], "none")]

    # --- the read itself ------------------------------------------------

    def test_a_named_file_from_collected_evidence_can_be_opened(self):
        """The concrete question the example turns on: what is in that list.

        The path comes from PR_A's changed files and the revision from its
        merge commit, so nothing here is a search - the follow-up follows a
        reference the collection already produced.
        """
        manifest = self.collect()
        pr = next(pr for child in manifest["children"] for pr in child["prs"])
        self.assertEqual(pr["mergeCommit"], MERGE_A)
        self.assertIn(ROUTER_FILE, pr["evidence"]["files"]["other"])
        self.assertIn(ROUTER_TEST, pr["evidence"]["files"]["tests"])

        result = self.read(revision=pr["mergeCommit"])
        self.assertTrue(result["inspected"])
        self.assertIn("TieredPools", result["body"])
        self.assertEqual(result["budget"]["spent"], 1)

    def test_the_revision_is_required_so_todays_main_cannot_stand_in(self):
        """A read of the default branch proves nothing about merged evidence.

        Spelled as two different documents at one path: the revision that
        answers the question, and one that does not exist. `gh` would serve
        the default branch happily, so the only defence is that the caller
        cannot omit the revision.
        """
        with self.assertRaises(TypeError):
            followup_mod.read(Gh(), cache_mod.Cache(KEY), ROUTER_REPO, ROUTER_FILE)
        missed = self.read(revision="0000000")
        self.assertFalse(missed["inspected"])
        self.assertIn("0000000", missed["limitation"])

    def test_the_same_source_is_not_fetched_twice(self):
        first = self.read()
        second = self.read()
        self.assertTrue(second["reused"])
        self.assertEqual(second["body"], first["body"])
        # Re-asking the same question is how a bounded follow-up becomes an
        # audit, so it costs nothing and does not ask GitHub again.
        self.assertEqual(second["budget"]["spent"], 1)

    def test_the_budget_stops_the_investigation_and_says_so(self):
        self.assertTrue(self.read(budget=1)["inspected"])
        blocked = self.read(path=ROUTER_TEST, budget=1)
        self.assertFalse(blocked["inspected"])
        self.assertEqual(blocked["reason"], "budget")
        self.assertIn("budget of 1 source reads", blocked["limitation"])
        self.assertIn("inspection limitation", blocked["limitation"])

    def test_an_unreadable_source_is_a_limitation_not_a_verdict(self):
        self.world["forbidden"] = ["example-org/closed-repo"]
        refused = self.read(repo="example-org/closed-repo")
        self.assertFalse(refused["inspected"])
        self.assertEqual(refused["reason"], "forbidden")
        self.assertIn("it is not evidence about the behaviour", refused["limitation"])

    def test_a_directory_and_an_oversized_file_are_not_read_as_empty(self):
        """Two contents responses that are not a file, and must not look like one."""
        self.world["sourceDirs"] = [f"{ROUTER_REPO}@{MERGE_A}:pkg/router"]
        self.world["sourcesTooLarge"] = [f"{ROUTER_REPO}@{MERGE_A}:pkg/router/big.bin"]
        directory = self.read(path="pkg/router")
        self.assertFalse(directory["inspected"])
        self.assertIn("is a directory", directory["limitation"])
        oversized = self.read(path="pkg/router/big.bin")
        self.assertFalse(oversized["inspected"])
        self.assertIn("will not inline", oversized["limitation"])

    # --- what an unresolved clause is allowed to claim --------------------

    def test_an_unresolved_clause_must_say_which_of_the_three_it_is(self):
        with self.assertRaises(ValueError) as caught:
            self.run_once(REQUIREMENTS, self.covering([
                {"text": "nothing establishes runtime routing", "kind": "unclear",
                 "nextAction": "read the router"}
            ]))
        self.assertIn("is classified 'unclear'", str(caught.exception))

    def test_an_absence_claim_that_names_no_read_is_a_limitation_not_a_gap(self):
        """The one mechanical lever that forces the follow-up read.

        "What I read does not establish this" is a claim about a read. With
        nothing named, the honest finding is that nothing was looked at - and
        being made to write that down is what makes opening the file the
        cheaper option.
        """
        with self.assertRaises(ValueError) as caught:
            self.run_once(REQUIREMENTS, self.covering([
                {"text": "nothing establishes runtime routing", "kind": "evidence-gap",
                 "nextAction": "read the router"}
            ]))
        message = str(caught.exception)
        self.assertIn("naming nothing inspected", message)
        self.assertIn("'inspection-limitation' instead", message)

    def test_an_unread_file_is_not_proof_that_the_behaviour_is_missing(self):
        """Missing evidence must not be presented as a confirmed implementation gap."""
        with self.assertRaises(ValueError) as caught:
            self.run_once(REQUIREMENTS, self.covering([
                {"text": "the router does not fall back to the tier pool",
                 "kind": "implementation-gap",
                 "nextAction": "implement the fallback"}
            ]))
        message = str(caught.exception)
        self.assertIn("an unread file is not proof of missing functionality", message)
        self.assertIn("an absent test is not proof of an absent implementation", message)

    def test_an_absent_test_alone_does_not_make_an_implementation_gap(self):
        """Same rule, the way it actually shows up: a test nobody can find.

        Citing the test file that exists and does not cover the clause is an
        implementation gap about the tests. Citing nothing, because the search
        came up empty, is not an implementation gap about anything.
        """
        with self.assertRaises(ValueError):
            self.run_once(REQUIREMENTS, self.covering([
                {"text": "no test asserts overflow is rejected at runtime",
                 "kind": "implementation-gap", "evidence": [],
                 "nextAction": "add the test"}
            ]))
        _, _, result, _ = self.run_once(REQUIREMENTS, self.covering([
            {"text": "no test asserts overflow is rejected at runtime",
             "kind": "evidence-gap", "inspected": [f"{ROUTER_REPO}@{MERGE_A}:{ROUTER_TEST}"],
             "revision": MERGE_A, "nextAction": "point at the test, or add one"}
        ]))
        self.assertEqual(result["clauseKinds"]["evidence-gap"], 1)
        self.assertEqual(result["clauseKinds"]["implementation-gap"], 0)

    def test_every_open_clause_has_to_name_a_next_action(self):
        with self.assertRaises(ValueError) as caught:
            self.run_once(REQUIREMENTS, self.covering([
                {"text": "nothing establishes runtime routing", "kind": "inspection-limitation",
                 "limitation": "the repository is not readable with this token"}
            ]))
        self.assertIn("states no next action", str(caught.exception))

    def test_an_inspection_limitation_must_state_the_constraint(self):
        with self.assertRaises(ValueError) as caught:
            self.run_once(REQUIREMENTS, self.covering([
                {"text": "nothing establishes runtime routing", "kind": "inspection-limitation",
                 "nextAction": "ask for read access"}
            ]))
        self.assertIn("with no constraint stated", str(caught.exception))

    # --- what the follow-up changes about the conclusion -------------------

    def test_follow_up_evidence_that_supports_the_clause_closes_it(self):
        """The read answers the question, the clause goes away, the row is met.

        This is the case the whole change is for: before, the same criterion
        was reported Partial for want of a read nobody did.
        """
        read = self.read()
        self.assertIn("TieredPools", read["body"])
        claim = assessment(
            "AC1", "Evidence found",
            [{"ref": PR_A, "kind": "pr", "state": "merged", "at": "2026-09-18T09:00:00Z"}],
            "merged", "confirmed",
        )
        _, _, result, report = self.run_once(
            REQUIREMENTS, [claim, assessment("AC2", "No evidence found", [], "none")],
            generated_at="2026-10-01T00:00:00Z",
        )
        self.assertEqual(result["outcomes"]["met"], 1)
        self.assertEqual(result["outcomes"]["partial"], 0)
        # The read is named in the report, so the conclusion is traceable to
        # the document it rests on rather than to a claim that one was read.
        self.assertIn(f"{ROUTER_REPO}@{MERGE_A}:{ROUTER_FILE}", report)

    def test_follow_up_evidence_that_contradicts_the_requirement_is_a_real_gap(self):
        """The other direction: the file was read and shows the behaviour absent.

        Cited, so it survives the refusal that an uncited implementation gap
        does not, and reported as engineering's problem rather than as
        something nobody checked.
        """
        _, _, result, report = self.run_once(REQUIREMENTS, self.covering([
            {"text": "Validate permits overflow for an unlisted pool",
             "kind": "implementation-gap",
             "evidence": [f"{ROUTER_REPO}@{MERGE_A}:{ROUTER_FILE}"],
             "revision": MERGE_A,
             "nextAction": "extend the check to pools outside TieredPools"}
        ]), generated_at="2026-10-01T00:00:00Z")
        self.assertEqual(result["clauseKinds"]["implementation-gap"], 1)
        self.assertIn("**Implementation gap**", report)
        self.assertIn("Something inspected shows this behaviour missing or contradicted", report)
        self.assertIn(f"(at {MERGE_A})", report)
        self.assertIn("extend the check to pools outside TieredPools", report)

    def test_a_configuration_restriction_is_not_proof_of_runtime_behaviour(self):
        """The example's actual trap, in this fixture's terms.

        `TieredPools` membership establishes which configurations are
        rejected. It does not establish what the router does with a live
        request, so the runtime clause stays open - but as an evidence gap
        scoped to the file that was read, not as a gap in the product and not
        as something nobody looked at.
        """
        read = self.read()
        self.assertIn("Validate rejects a configuration", read["body"])
        self.assertNotIn("Route(", read["body"])

        # Claiming the criterion met on the strength of the restriction alone
        # is refused, because the clause it leaves open is still open.
        with self.assertRaises(ValueError) as caught:
            self.run_once(REQUIREMENTS, self.covering([
                {"text": "membership in TieredPools does not establish that a live request is "
                         "routed to its tier's pool",
                 "kind": "evidence-gap", "inspected": [f"{ROUTER_REPO}@{MERGE_A}:{ROUTER_FILE}"],
                 "revision": MERGE_A, "nextAction": "read the request handler at this revision"}
            ], verdict="Evidence found"))
        self.assertIn("claims every clause of the criterion holds", str(caught.exception))

        _, _, result, report = self.run_once(REQUIREMENTS, self.covering([
            {"text": "membership in TieredPools does not establish that a live request is "
                     "routed to its tier's pool",
             "kind": "evidence-gap", "inspected": [f"{ROUTER_REPO}@{MERGE_A}:{ROUTER_FILE}"],
             "revision": MERGE_A, "nextAction": "read the request handler at this revision"}
        ]), generated_at="2026-10-01T00:00:00Z")
        self.assertEqual(result["outcomes"]["partial"], 1)
        self.assertIn("**Evidence gap**", report)
        self.assertIn("What was inspected does not establish this either way", report)
        self.assertIn(f"having inspected {ROUTER_REPO}@{MERGE_A}:{ROUTER_FILE}", report)

    def test_partial_stays_conservative_when_some_clauses_hold(self):
        """Supported clauses do not promote the row, and one open clause does not sink it."""
        _, _, result, report = self.run_once(REQUIREMENTS, self.covering([
            {"text": "runtime routing is unestablished", "kind": "evidence-gap",
             "inspected": [f"{ROUTER_REPO}@{MERGE_A}:{ROUTER_FILE}"], "revision": MERGE_A,
             "nextAction": "read the request handler"}
        ]), generated_at="2026-10-01T00:00:00Z")
        self.assertEqual(result["outcomes"]["partial"], 1)
        self.assertEqual(result["outcomes"]["met"], 0)
        self.assertEqual(result["outcomes"]["confirmed-unmet"], 0)
        # Merged and supported is still not "implemented": the row says what
        # holds and what does not, separately.
        self.assertIn("Partial", report)

    # --- the two renderings ------------------------------------------------

    def test_an_incomplete_investigation_is_stated_in_both_renderings(self):
        _, _, result, report = self.run_once(REQUIREMENTS, self.covering([
            {"text": "the request handler could not be read", "kind": "inspection-limitation",
             "limitation": "the handler lives in a repository this token cannot read",
             "nextAction": "ask for read access to example-org/example-gateway"}
        ]), generated_at="2026-10-01T00:00:00Z")
        self.assertIn("This investigation is incomplete.", report)
        self.assertIn("**Inspection limitation**", report)
        self.assertIn("could not be read", result["summary"])
        self.assertIn("unresolved rather than negative", result["summary"])
        # The summary's action is one action. It is joined to its neighbours
        # with "; ", so a semicolon inside it would read as a second one.
        action = [
            line for line in result["summary"].splitlines()
            if line.startswith("- **Next actions:**")
        ][0]
        self.assertIn("finish the inspection on 1 criterion", action)
        self.assertEqual(1, action.count("unresolved rather than negative"))
        self.assertNotIn("read; the position", action)

    def test_the_summary_counts_the_kinds_the_full_assessment_names(self):
        _, _, result, report = self.run_once(REQUIREMENTS, self.covering([
            {"text": "the handler is unestablished", "kind": "evidence-gap",
             "inspected": [f"{ROUTER_REPO}@{MERGE_A}:{ROUTER_FILE}"],
             "nextAction": "read the request handler"},
            {"text": "Validate skips unlisted pools", "kind": "implementation-gap",
             "evidence": [f"{ROUTER_REPO}@{MERGE_A}:{ROUTER_FILE}"],
             "nextAction": "extend the check"},
        ]), generated_at="2026-10-01T00:00:00Z")
        self.assertEqual(result["clauseKinds"],
                         {"implementation-gap": 1, "evidence-gap": 1, "inspection-limitation": 0})
        self.assertIn("1 implementation gap", result["summary"])
        self.assertIn("1 evidence gap", result["summary"])
        # And the labels the summary counts are the ones the reader finds.
        self.assertIn("**Implementation gap**", report)
        self.assertIn("**Evidence gap**", report)
        # Nothing was inspectable-but-unread, so neither rendering says the
        # investigation stopped early.
        self.assertNotIn("This investigation is incomplete.", report)
        self.assertNotIn("could not be read", result["summary"])

    def test_the_summary_says_the_counts_it_means(self):
        """Grammar, on the one bullet whose whole job is the distinction.

        A count that reads "2 evidence gap" or "1 criterion - 1 on
        RHOAIENG-7001" is not a typo in a log line; it is in the sentence a
        program manager forwards, and it costs the bullet the authority it
        needs to be acted on.
        """
        _, _, result, _ = self.run_once(REQUIREMENTS, self.covering([
            {"text": "overflow is unestablished", "kind": "evidence-gap",
             "inspected": [f"{ROUTER_REPO}@{MERGE_A}:{ROUTER_FILE}"],
             "nextAction": "read the clamp"},
            {"text": "the tier pool is unestablished", "kind": "evidence-gap",
             "inspected": [f"{ROUTER_REPO}@{MERGE_A}:{ROUTER_TEST}"],
             "nextAction": "read the test"},
        ]), generated_at="2026-10-01T00:00:00Z")
        self.assertIn("2 evidence gaps", result["summary"])
        self.assertNotIn("2 evidence gap,", result["summary"])
        # AC1 was already named under "Evidence established", so this bullet
        # collapses it to a count. One source means that count is the
        # breakdown, and printing both says it twice.
        self.assertIn("still open: 1 on RHOAIENG-7001", result["summary"])
        self.assertNotIn("1 criteria", result["summary"])
        self.assertNotIn("1 criterion — 1 on", result["summary"])

    def test_one_follow_up_read_is_reported_in_the_singular(self):
        self.read()
        _, _, _, report = self.run_once(REQUIREMENTS, self.covering([
            {"text": "overflow is unestablished", "kind": "evidence-gap",
             "inspected": [f"{ROUTER_REPO}@{MERGE_A}:{ROUTER_FILE}"],
             "nextAction": "read the clamp"},
        ]), generated_at="2026-10-01T00:00:00Z")
        self.assertIn("1 source file read as a bounded follow-up, at the revision named",
                      report)
        self.assertNotIn("at the 1 revision", report)

    def test_the_renderings_cannot_disagree_about_an_inspection_limitation(self):
        """The cross-check, exercised by breaking the agreement it protects."""
        requirements = [dict(r) for r in REQUIREMENTS]
        assessments = self.covering([
            {"text": "the handler could not be read", "kind": "inspection-limitation",
             "limitation": "no read access", "nextAction": "ask for access"}
        ])
        merged, _, _ = assemble_mod.merge(
            requirements, assessments, {}, "2026-10-01T00:00:00Z"
        )
        def clause_problems(report, summary):
            # Scoped to this check: `cross_check` also refuses a missing
            # outcome row in these hand-built strings, and asserting on the
            # whole list would pass whether or not this check ran at all.
            return [
                p for p in assemble_mod.cross_check(
                    report, summary, outcomes_mod.tally(merged), None, merged, None)
                if "clause(s)" in p or "investigation is incomplete" in p
            ]

        self.assertEqual(
            clause_problems("… **Inspection limitation** …", "… could not be read …"), []
        )
        # The label missing from the full assessment the summary points at.
        self.assertIn(
            "never uses the label 'Inspection limitation'",
            " ".join(clause_problems("… nothing to see …", "… could not be read …")),
        )
        # And the draft that reads as a finished reading which found nothing.
        self.assertIn(
            "does not say the investigation is incomplete",
            " ".join(clause_problems("… **Inspection limitation** …", "… all clear …")),
        )

    # --- the record of what was read ---------------------------------------

    def test_the_reads_are_recorded_and_survive_a_re_render(self):
        """A re-render must not describe a shallower investigation than the one reviewed."""
        self.read()
        _, _, result, report = self.run_once(
            REQUIREMENTS,
            [assessment("AC1", "Evidence found", [{"ref": PR_A}], "merged", "confirmed"),
             assessment("AC2", "No evidence found", [], "none")],
            generated_at="2026-10-01T00:00:00Z",
        )
        ref = f"{ROUTER_REPO}@{MERGE_A}:{ROUTER_FILE}"
        self.assertEqual(result["sourceReads"], [ref])
        self.assertIn(ref, report)

        stored, problem = snapshots_mod.load(result["snapshotPath"])
        self.assertIsNone(problem)
        self.assertEqual(stored["sourceReads"], [ref])

        # The ledger lives in the cache, which is disposable. The snapshot is
        # the record, so clearing the cache must not shorten the account of
        # what was inspected.
        shutil.rmtree(cache_mod.cache_dir(KEY), ignore_errors=True)
        again = assemble_mod.build(
            {"jira": {"key": KEY, "summary": "Tiered quota", "status": "In Progress"},
             "mappings": [], "manifest": {"jiraKey": KEY, "epics": [], "children": [],
                                          "dependencies": [], "access": []},
             "requirements": stored["requirements"], "assessments": stored["requirements"],
             "summary": stored["summaryNarrative"] or "Upstream work is partly complete.",
             "sourceReads": stored["sourceReads"], "generatedAt": "2026-10-02T00:00:00Z"},
            write_snapshot=False,
            # What `rerender` does: the stored evidence was joined when the
            # assessment was made, against a manifest this call does not have.
            resolve_evidence=False,
        )
        self.assertEqual(again["sourceReads"], [ref])


class EvidenceJoinTest(PipelineTest):
    """What a citation says, and what the pipeline says on its behalf.

    Which artifact is evidence for a criterion is the model's judgement and
    stays with it. What that artifact *is* - merged or open, and when - the
    collector already fetched, and the failure here is the one that happens
    when it is written down a second time: a merge time rounded to the minute
    is a different instant, and `at` is what decides whether the trend
    section calls a changed row work that landed or work nobody had found.
    """

    def stored(self, assessments):
        """The requirement rows as they were snapshotted, by id."""
        _, _, result, _ = self.run_once(
            REQUIREMENTS, assessments, generated_at="2026-10-01T00:00:00Z"
        )
        snapshot, problem = snapshots_mod.load(result["snapshotPath"])
        self.assertIsNone(problem)
        return {row["id"]: row for row in snapshot["requirements"]}

    def refused(self, evidence, verdict="Evidence found", state="merged"):
        """The message `assemble` refuses one cited list with."""
        with self.assertRaises(ValueError) as caught:
            self.run_once(
                REQUIREMENTS,
                [assessment("AC1", verdict, evidence, state),
                 assessment("AC2", "No evidence found", [], "none")],
                generated_at="2026-10-01T00:00:00Z",
            )
        return str(caught.exception)

    def unverified(self):
        return assessment("AC2", "No evidence found", [], "none")

    # --- what the join fills in -----------------------------------------

    def test_a_bare_ref_is_all_a_citation_needs(self):
        rows = self.stored(
            [assessment("AC1", "Evidence found", [{"ref": PR_A}], "merged"), self.unverified()]
        )
        self.assertEqual(
            rows["AC1"]["evidence"],
            [{"ref": PR_A, "kind": "pr", "state": "merged", "at": "2026-09-18T09:00:00Z"}],
            "kind, state and at come from the manifest, not from the assessment",
        )

    def test_an_issue_is_dated_by_its_close_and_an_open_one_by_its_creation(self):
        """`updatedAt` is not a date for evidence: a comment would move it."""
        rows = self.stored(
            [assessment("AC1", "Evidence found", [{"ref": CHILD_A}], "merged"),
             assessment("AC2", "Partial evidence", [{"ref": CHILD_B}], "in review")]
        )
        self.assertEqual(
            rows["AC1"]["evidence"][0],
            {"ref": CHILD_A, "kind": "issue", "state": "closed", "at": "2026-09-18T10:00:00Z"},
        )
        self.assertEqual(
            rows["AC2"]["evidence"][0],
            {"ref": CHILD_B, "kind": "issue", "state": "open", "at": "2026-08-01T00:00:00Z"},
        )

    def test_refuting_evidence_is_joined_the_same_way(self):
        """The list behind the report's least forgiving claim gets no exemption."""
        declared = assessment("AC2", "No evidence found", [], "none")
        declared["outcome"] = "confirmed-unmet"
        declared["refutingEvidence"] = [{"ref": self.cite_pr()}]
        rows = self.stored(
            [assessment("AC1", "Evidence found", [{"ref": PR_A}], "merged"), declared]
        )
        self.assertEqual(
            rows["AC2"]["refutingEvidence"],
            [{"ref": PR_B, "kind": "pr", "state": "merged", "at": "2026-09-20T09:00:00Z"}],
        )

    # --- what it refuses -------------------------------------------------

    def test_a_ref_the_traversal_never_saw_is_refused_by_name(self):
        message = self.refused([{"ref": "example-org/example-quota#999"}])
        self.assertIn("example-org/example-quota#999", message)
        self.assertIn("is not an artifact this run traversed", message)

    def test_declaring_a_kind_does_not_smuggle_an_untraversed_ref_in(self):
        """Otherwise the way to cite a CI check is also the way around the check."""
        message = self.refused([{"ref": "example-org/example-quota#999", "kind": "pr"}])
        self.assertIn("is not an artifact this run traversed", message)

    def test_a_timestamp_rounded_to_the_minute_is_refused_rather_than_merged(self):
        """The bug this exists for: 09:00:00Z transcribed from a merge at 09:00:34Z."""
        self.world["prs"][PR_A] = pull(PR_A, merged="2026-09-18T09:00:34Z", commit=MERGE_A)
        message = self.refused([{"ref": PR_A, "at": "2026-09-18T09:00:00Z"}])
        self.assertIn("2026-09-18T09:00:00Z", message)
        self.assertIn("2026-09-18T09:00:34Z", message)

    def test_a_conflicting_state_is_refused_in_both_directions(self):
        message = self.refused([{"ref": PR_A, "state": "open"}])
        self.assertIn("states state='open' but what was collected says 'merged'", message)

    def test_the_same_instant_written_another_way_is_not_a_conflict(self):
        """Nobody acted on the notation; the stored value is the collected one."""
        rows = self.stored(
            [assessment("AC1", "Evidence found",
                        [{"ref": PR_A, "at": "2026-09-18T09:00:00+00:00"}], "merged"),
             self.unverified()]
        )
        self.assertEqual(rows["AC1"]["evidence"][0]["at"], "2026-09-18T09:00:00Z")

    def test_a_field_nothing_collected_records_is_refused_too(self):
        """A declared dependency is inspected shallowly, so it may have no date.

        Accepting a supplied one here would leave the single field the trend
        reads as the one field nobody checked.
        """
        dependency = "example-org/example-meter#900"
        self.world["issues"][CHILD_A]["body"] = f"Routing work. Depends on {dependency}"
        self.world["issues"][dependency] = {
            "title": "Meter API", "body": "", "state": "OPEN", "stateReason": "",
            "url": "https://github.com/example-org/example-meter/issues/900",
        }
        message = self.refused([{"ref": dependency, "at": "2026-09-18T09:00:00Z"}])
        self.assertIn("nothing collected for it records a value for at", message)

    # --- evidence that is not a traversed artifact ------------------------

    def test_a_ci_check_states_its_own_kind_and_is_left_as_written(self):
        rows = self.stored(
            [assessment("AC1", "Evidence found",
                        [{"ref": PR_A}, {"ref": "e2e-routing", "kind": "check", "state": "pass"}],
                        "tested"),
             self.unverified()]
        )
        self.assertEqual(
            rows["AC1"]["evidence"][1], {"ref": "e2e-routing", "kind": "check", "state": "pass"}
        )

    def test_a_check_name_with_no_kind_is_refused_rather_than_guessed_at(self):
        message = self.refused([{"ref": "e2e-routing"}], state="tested")
        self.assertIn("nothing collected this run describes it", message)

    def test_a_source_read_is_joined_from_the_ledger_and_carries_no_date(self):
        """The ledger dates the read, which is now, not the code it read."""
        self.write_world()
        followup_mod.read(
            Gh(), cache_mod.Cache(KEY, reuse=True), ROUTER_REPO, ROUTER_FILE, MERGE_A
        )
        ref = followup_mod.source_ref(ROUTER_REPO, ROUTER_FILE, MERGE_A)
        rows = self.stored(
            [assessment("AC1", "Evidence found", [{"ref": ref}], "merged"), self.unverified()]
        )
        self.assertEqual(rows["AC1"]["evidence"][0], {"ref": ref, "kind": "source"})

    def test_a_source_read_that_never_happened_is_refused(self):
        ref = followup_mod.source_ref(ROUTER_REPO, ROUTER_TEST, MERGE_A)
        message = self.refused([{"ref": ref}])
        self.assertIn("names a source read this run did not make", message)


def multi_source(count_per_key=4, keys=("RHOAIENG-2201", "RHOAIENG-2202", "RHOAIENG-2203")):
    """Criteria spread over several Jira issues, with ids that collide.

    `AC1` exists once per key here, which is the normal shape of a rollup over
    an epic's worth of Jira issues and the shape every id-keyed lookup got
    wrong.
    """
    requirements = []
    for key in keys:
        for index in range(1, count_per_key + 1):
            requirements.append(
                {
                    "id": f"AC{index}",
                    "sourceKey": key,
                    "type": "AC" if index % 2 else "SC",
                    "text": f"{key} criterion {index}.",
                    "assessment": "No evidence found",
                    "evidence": [],
                    "evidenceState": "none",
                    "downstream": {"state": "unknown", "detail": None},
                }
            )
    return requirements


class SummaryBudgetTest(unittest.TestCase):
    """The one artifact that gets posted, and what happens when it is too long.

    The failure this pins down was silent: a 49-criterion run produced a draft
    at 89% over the ceiling, the renderer's compression loop shrank the one
    thing that was not the problem, and the overrun reached the approval step
    as a boolean in a file nobody reads. Nothing here truncates anything -
    what changed is that the condition is named, says which half is long, and
    is printed where the draft is read.
    """

    def world(self, criteria=49, bullet_words=120, overall_words=85, keys=6):
        """A rollup the size the issue was filed about, with prose of a set length."""
        sources = [f"RHOAIENG-22{n:02d}" for n in range(1, keys + 1)]
        plan = ["met", "partial", "confirmed-unmet", "unverified"]
        requirements = []
        for index in range(criteria):
            outcome = plan[index % len(plan)]
            verdict = {"met": "Evidence found", "partial": "Partial evidence"}.get(
                outcome, "No evidence found"
            )
            row = {
                "id": f"AC{index + 1}", "sourceKey": sources[index % keys], "type": "AC",
                "text": f"Criterion {index + 1}.", "assessment": verdict,
                "evidence": [], "downstream": {"state": "unknown"},
            }
            if outcome in ("met", "partial"):
                row["evidence"] = [{"ref": PR_A, "kind": "pr", "state": "merged"}]
            if outcome == "confirmed-unmet":
                row["outcome"] = "confirmed-unmet"
                row["refutingEvidence"] = [{"ref": PR_A, "kind": "pr", "state": "merged"}]
            requirements.append(row)

        by_bullet = {"evidence-established": "met", "remaining-work": "unverified",
                     "decisions-needed": "confirmed-unmet", "next-actions": "unverified"}
        narrative = []
        for slug, outcome in by_bullet.items():
            rows = [r for r in requirements if outcomes_mod.classify(r) == outcome][:8]
            narrative.append({
                "bullet": slug, "text": " ".join(["word"] * bullet_words), "links": [],
                "refs": [{"sourceKey": r["sourceKey"], "id": r["id"]} for r in rows],
            })
        picked = {
            field: [{"sourceKey": r["sourceKey"], "id": r["id"]}
                    for r in requirements if outcomes_mod.classify(r) in wanted][:3]
            for field, wanted in (("establishes", ("met", "partial")),
                                  ("unmet", ("confirmed-unmet",)),
                                  ("unverified", ("unverified",)))
        }
        assembly = {
            "generatedAt": "2026-10-11T00:00:00Z",
            "jira": {"key": sources[0], "summary": "Tiered quota",
                     "site": "https://jira.example.com"},
            "manifest": {"children": [], "epics": [], "observed": True},
            "requirements": requirements, "mappings": [], "narrative": narrative,
            "overall": dict(picked, text=" ".join(["word"] * overall_words)),
        }
        return assembly, requirements

    def draft(self, **kwargs):
        assembly, requirements = self.world(**kwargs)
        tallied = outcomes_mod.tally(requirements)
        confidence = outcomes_mod.confidence(assembly, requirements, tallied)
        return summary_mod.draft(assembly, tallied, confidence, trend="Baseline established.")

    def test_a_draft_inside_the_budget_is_named_within_budget(self):
        state = self.draft(criteria=8, bullet_words=38, keys=2)
        self.assertEqual(state["condition"], summary_mod.WITHIN_BUDGET)
        self.assertTrue(state["within"])
        self.assertIsNone(summary_mod.budget_notice(state))

    def test_an_overrun_is_a_named_condition_not_only_a_false(self):
        state = self.draft()
        self.assertGreater(state["words"], summary_mod.WORD_CEILING)
        self.assertEqual(state["condition"], summary_mod.OVER_CEILING)
        self.assertFalse(state["within"])

    def test_the_overrun_says_which_half_of_the_draft_is_long(self):
        """"The draft is long" and "what you wrote is long" lead to different moves."""
        state = self.draft(bullet_words=120, overall_words=85)
        self.assertEqual(state["authored"]["narrative"], 480)
        self.assertEqual(state["authored"]["overall"], 85)

    def test_the_notice_names_the_room_the_bullets_actually_have_left(self):
        state = self.draft()
        notice = summary_mod.budget_notice(state)
        fixed = state["words"] - state["authored"]["narrative"] - state["authored"]["overall"]
        room = summary_mod.WORD_CEILING - state["authored"]["overall"] - fixed
        self.assertIn(f"{state['words']} words against a 350-word ceiling", notice)
        self.assertIn(f"they have {room} to work with", notice)
        self.assertIn("assemble again before showing the draft for approval", notice)

    def test_nothing_the_model_wrote_is_shortened_to_fit(self):
        """The whole point of reporting rather than enforcing."""
        assembly, requirements = self.world()
        tallied = outcomes_mod.tally(requirements)
        confidence = outcomes_mod.confidence(assembly, requirements, tallied)
        state = summary_mod.draft(assembly, tallied, confidence, trend="Baseline established.")
        for entry in assembly["narrative"]:
            self.assertIn(entry["text"], state["text"])
        self.assertIn(assembly["overall"]["text"], state["text"])
        for _, label in summary_mod.BULLETS:
            self.assertIn(f"- **{label}:**", state["text"])

    def test_the_reference_cap_is_applied_once_rather_than_retried(self):
        """Retrying at two and one references bought four words and cost two renders.

        Measured on this fixture the one-reference draft is the *longest* of
        the three, because "and 9 more - 4 on RHOAIENG-2204, 3 on
        RHOAIENG-2205" costs more than the two names it replaces. So an
        over-ceiling draft still names three criteria per bullet: the cap is a
        readability rule, and it was never a compression lever.
        """
        state = self.draft()
        self.assertEqual(state["condition"], summary_mod.OVER_CEILING)
        self.assertEqual(state["refsPerBullet"], summary_mod.MAX_REFS_PER_BULLET)
        remaining = next(
            line for line in state["text"].splitlines()
            if line.startswith("- **Remaining work:**")
        )
        named = len(re.findall(r"RHOAIENG-\d+ AC\d+\]", remaining))
        self.assertEqual(named, summary_mod.MAX_REFS_PER_BULLET)

    def test_a_short_draft_is_named_under_floor_and_gets_no_notice(self):
        """A thin summary is visible in the draft itself; an overrun is not."""
        state = self.draft(criteria=4, bullet_words=4, overall_words=20, keys=1)
        self.assertEqual(state["condition"], summary_mod.UNDER_FLOOR)
        self.assertIsNone(summary_mod.budget_notice(state))


class SummaryRenderTest(unittest.TestCase):
    """The rules that keep the Jira summary readable at 49 criteria.

    Rendered directly rather than through the pipeline: these are properties
    of the renderer given an assessment, and nothing here depends on how the
    assessment was reached.
    """

    def render(self, requirements, narrative=None, **assembly):
        base = {
            "generatedAt": "2026-10-01T00:00:00Z",
            "jira": {"key": "RHOAIENG-2200", "summary": "Quota policy"},
            "manifest": {"children": [], "epics": [], "observed": True},
            "requirements": requirements,
            "mappings": [],
            "narrative": narrative or [],
        }
        base.update(assembly)
        tallied = outcomes_mod.tally(requirements)
        confidence = outcomes_mod.confidence(base, requirements, tallied)
        return summary_mod.render(base, tallied, confidence)

    def test_every_criterion_reference_names_its_source_jira(self):
        """`AC1` belongs to three issues here. Unqualified, it points at none."""
        summary = self.render(multi_source(count_per_key=1))
        bullets = [line for line in summary.splitlines() if line.startswith("- **")]
        self.assertTrue(any("RHOAIENG-2201 AC1" in line for line in bullets))
        # Every `AC1` in a bullet is preceded by the key that owns it. Three
        # issues have one, so a bare id points at none of them.
        for line in bullets:
            for match in re.finditer("AC1", line):
                # Matched against the whole prefix rather than a fixed-width
                # slice of it, so the check does not depend on how long the
                # fixture's Jira keys happen to be.
                self.assertRegex(line[:match.start()], r"RHOAIENG-\d+ $", line)

    def test_a_long_enumeration_collapses_to_counts_grouped_by_jira_issue(self):
        summary = self.render(multi_source(count_per_key=6))
        remaining = next(
            line for line in summary.splitlines() if line.startswith("- **Remaining work:**")
        )
        explicit = remaining.count("RHOAIENG-2201 AC") + remaining.count("RHOAIENG-2202 AC") \
            + remaining.count("RHOAIENG-2203 AC")
        self.assertLessEqual(explicit, summary_mod.MAX_REFS_PER_BULLET)
        self.assertIn("more — ", remaining)
        self.assertIn("on RHOAIENG-2203", remaining)
        # The suffix is already inside one pair of brackets; a second pair
        # inside it is what the collapse was meant to spare the reader.
        self.assertNotIn("more (", remaining)

    def test_a_criterion_is_named_in_one_bullet_and_counted_in_the_rest(self):
        """The same eight ids under three headings reads as 24 problems."""
        requirements = multi_source(count_per_key=2)
        requirements[0]["unresolvedClauses"] = ["the retention window is TBD"]
        summary = self.render(requirements)
        named = [
            line for line in summary.splitlines()
            if line.startswith("- **") and "RHOAIENG-2201 AC1" in line
        ]
        self.assertEqual(len(named), 1, "a criterion is named explicitly in exactly one bullet")

    def test_the_four_bullets_are_present_and_in_order(self):
        summary = self.render(multi_source(count_per_key=2))
        order = [
            index
            for label in ("Evidence established", "Remaining work", "Decisions needed",
                          "Next actions")
            for index, line in enumerate(summary.splitlines())
            if line.startswith(f"- **{label}:**")
        ]
        self.assertEqual(len(order), 4, summary)
        self.assertEqual(order, sorted(order))

    def test_types_are_counted_separately_and_never_summed(self):
        summary = self.render(multi_source(count_per_key=4))
        self.assertIn("acceptance criteria", summary)
        self.assertIn("success criteria", summary)
        self.assertIn("counted separately", summary)
        self.assertNotIn("% complete", summary)

    def test_narrative_carries_the_bullet_and_traces_to_its_rows(self):
        requirements = multi_source(count_per_key=2)
        requirements[0].update(
            assessment="Evidence found",
            evidence=[{"ref": PR_A, "kind": "pr", "state": "merged",
                       "at": "2026-09-18T09:00:00Z"}],
            evidenceState="merged",
        )
        summary = self.render(
            requirements,
            narrative=[
                {
                    "bullet": "evidence-established",
                    "text": "Prohibited-topic rails fire on buffered responses",
                    "refs": [{"sourceKey": "RHOAIENG-2201", "id": "AC1"}],
                    "links": [PR_A],
                }
            ],
        )
        established = next(
            line for line in summary.splitlines()
            if line.startswith("- **Evidence established:**")
        )
        self.assertIn("Prohibited-topic rails fire on buffered responses", established)
        self.assertIn("RHOAIENG-2201 AC1", established)
        self.assertIn(f"https://github.com/{PR_A.split('#')[0]}/pull/500", established)


class NarrativeTraceabilityTest(unittest.TestCase):
    """Structural checks on model prose, and the line they stop at.

    These prove a claim can be traced to rows that exist. None of them proves
    the claim is true; that reading of the evidence is the model's and stays
    the model's.
    """

    def rows(self):
        return multi_source(count_per_key=2)

    def test_a_claim_citing_a_row_that_does_not_exist_is_refused(self):
        problems = summary_mod.narrative_problems(
            [{"bullet": "remaining-work", "text": "Observability is untracked",
              "refs": [{"sourceKey": "RHOAIENG-2201", "id": "SC99"}]}],
            self.rows(),
        )
        self.assertTrue(any("not an assessed requirement" in p for p in problems))

    def test_the_same_id_on_the_wrong_jira_issue_is_refused(self):
        """Traceability keyed on `(sourceKey, id)`, because ids repeat."""
        problems = summary_mod.narrative_problems(
            [{"bullet": "remaining-work", "text": "x",
              "refs": [{"sourceKey": "RHOAIENG-2204", "id": "AC1"}]}],
            self.rows(),
        )
        self.assertTrue(any("RHOAIENG-2204" in p for p in problems))

    def test_a_claim_with_no_rows_at_all_is_refused(self):
        problems = summary_mod.narrative_problems(
            [{"bullet": "next-actions", "text": "Ship it", "refs": []}], self.rows()
        )
        self.assertTrue(any("cites no assessment row" in p for p in problems))

    def test_an_established_claim_cannot_rest_on_an_unverified_row(self):
        problems = summary_mod.narrative_problems(
            [{"bullet": "evidence-established", "text": "Streaming is enforced",
              "refs": [{"sourceKey": "RHOAIENG-2201", "id": "AC1"}]}],
            self.rows(),
        )
        self.assertTrue(any("cannot establish a capability" in p for p in problems))

    def test_a_link_not_carried_by_a_cited_row_is_refused(self):
        rows = self.rows()
        rows[0].update(
            assessment="Evidence found", evidenceState="merged",
            evidence=[{"ref": PR_A, "kind": "pr", "state": "merged"}],
        )
        problems = summary_mod.narrative_problems(
            [{"bullet": "evidence-established", "text": "Rails fire",
              "refs": [{"sourceKey": "RHOAIENG-2201", "id": "AC1"}], "links": [PR_B]}],
            rows,
        )
        self.assertTrue(any("not evidence on any row it cites" in p for p in problems))

    def test_a_well_formed_claim_passes(self):
        rows = self.rows()
        rows[0].update(
            assessment="Evidence found", evidenceState="merged",
            evidence=[{"ref": PR_A, "kind": "pr", "state": "merged"}],
        )
        self.assertEqual(
            summary_mod.narrative_problems(
                [{"bullet": "evidence-established", "text": "Rails fire",
                  "refs": [{"sourceKey": "RHOAIENG-2201", "id": "AC1"}], "links": [PR_A]}],
                rows,
            ),
            [],
        )

    def test_structural_checks_do_not_claim_the_prose_is_correct(self):
        """A traceable claim that misreads its evidence still passes. By design.

        Recorded as a test so nobody later reads the validator as a fact
        checker and stops reviewing the summary.
        """
        rows = self.rows()
        rows[0].update(
            assessment="Evidence found", evidenceState="merged",
            evidence=[{"ref": PR_A, "kind": "pr", "state": "merged"}],
        )
        self.assertEqual(
            summary_mod.narrative_problems(
                [{"bullet": "evidence-established",
                  "text": "This criterion is fully verified in production",
                  "refs": [{"sourceKey": "RHOAIENG-2201", "id": "AC1"}]}],
                rows,
            ),
            [],
        )


class UnscopedClaimTest(unittest.TestCase):
    """A traversal of one epic cannot establish that something does not exist."""

    def test_an_absolute_absence_claim_is_refused(self):
        for text in (
            "No upstream issue covers this.",
            "There is no upstream work for observability.",
            "No PR exists for streaming enforcement.",
        ):
            self.assertTrue(
                assemble_mod.unscoped_claims(text, "AC1 gap"), text
            )

    def test_a_claim_scoped_to_what_was_read_is_accepted(self):
        for text in (
            "No work in the traversed set covers this.",
            "Nothing inspected supports the streaming clause.",
            "No upstream issue in the epics traversed is linked to this criterion.",
        ):
            self.assertEqual(assemble_mod.unscoped_claims(text, "AC1 gap"), [], text)

    def test_the_gap_field_is_checked_at_merge_time(self):
        record = {"assessment": "No evidence found", "evidence": [],
                  "gap": "No upstream issue covers this."}
        self.assertTrue(
            any("claims more than a traversal can show" in p
                for p in assemble_mod._validate(record, "AC1"))
        )


class MatchedPairTest(unittest.TestCase):
    """Movement computed over the right rows when ids repeat across issues."""

    def pairs(self):
        return [
            {"sourceKey": "RHOAIENG-2201", "currentId": "AC1", "previousId": "AC1",
             "previousAssessment": "No evidence found", "textChanged": False},
            {"sourceKey": "RHOAIENG-2202", "currentId": "AC1", "previousId": "AC1",
             "previousAssessment": "No evidence found", "textChanged": False},
        ]

    def current(self):
        rows = multi_source(count_per_key=1, keys=("RHOAIENG-2201", "RHOAIENG-2202"))
        rows[0]["assessment"] = "Evidence found"
        rows[0]["evidence"] = [{"ref": PR_A, "at": "2026-10-21T00:00:00Z"}]
        return rows

    def test_like_for_like_counts_both_issues_not_one(self):
        like = metrics_mod.like_for_like(self.pairs(), self.current())
        self.assertEqual(like["total"], 2, "id-keyed lookup used to collapse these to one")
        self.assertEqual(like["current"]["numerator"], 1)

    def test_a_change_is_attributed_to_the_issue_that_owns_it(self):
        changes = metrics_mod.classify_assessment_changes(
            self.pairs(), self.current(), "2026-10-01T00:00:00Z"
        )
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["sourceKey"], "RHOAIENG-2201")
        self.assertEqual(changes[0]["cause"], "implementation-progress")

    def test_a_pair_without_a_source_key_is_skipped_when_the_id_is_ambiguous(self):
        """Older snapshots have no `sourceKey`. An arbitrary match is worse than none."""
        legacy = [{"currentId": "AC1", "previousId": "AC1",
                   "previousAssessment": "No evidence found", "textChanged": False}]
        self.assertIsNone(metrics_mod.like_for_like(legacy, self.current()))


class HtmlReportTest(unittest.TestCase):
    """The third rendering, held to the same standard as the other two.

    An HTML file gets forwarded, opened on a phone and printed, which the
    Markdown does not, so the things that matter here are: the counts agree
    with the tally the Jira comment carries, nothing it says is invented to
    fill a gap, and nothing a stranger wrote in an issue body can execute when
    somebody opens it.
    """

    def render(self, requirements, **assembly):
        base = {
            "generatedAt": "2026-10-01T00:00:00Z",
            "jira": {"key": "RHOAIENG-2200", "summary": "Quota policy",
                     "site": "https://jira.example.com"},
            "manifest": {"children": [], "epics": [EPIC], "observed": True},
            "requirements": requirements,
            "mappings": [{"ref": EPIC, "url": f"https://github.com/{EPIC}"}],
            "narrative": [],
        }
        base.update(assembly)
        return htmlreport_mod.render(base, outcomes_mod.tally(requirements))

    def rows(self, document):
        return re.findall(r"<details class=\"row\"(.*?)</details>", document, re.S)

    # --- counts ----------------------------------------------------------

    def test_each_requirement_type_is_counted_on_its_own_row(self):
        """Eight met acceptance criteria and zero met success criteria is not "8 of 16"."""
        requirements = []
        for kind, outcome in (("AC", "Evidence found"), ("SC", "No evidence found"),
                              ("DoD", "Partial evidence")):
            for index in range(1, 3):
                requirements.append({
                    "id": f"{kind}{index}", "sourceKey": "RHOAIENG-2201", "type": kind,
                    "text": f"{kind} {index}.", "assessment": outcome,
                    "evidence": [{"ref": PR_A, "kind": "pr"}] if outcome != "No evidence found" else [],
                    "downstream": {"state": "unknown"},
                })
        document = self.render(requirements)
        table = document.split("Assessment context")[0]
        for label, cells in (
            ("Acceptance criteria", ["2", "0", "0", "0"]),
            ("Success criteria", ["0", "0", "0", "2"]),
            ("Definition-of-done items", ["0", "2", "0", "0"]),
        ):
            row = re.search(
                rf'<th scope="row">{label}</th>(.*?)</tr>', table, re.S
            )
            self.assertIsNotNone(row, label)
            self.assertEqual(re.findall(r">(\d+)</td>", row.group(1)), cells, label)
        # No combined score anywhere: the three types are not interchangeable
        # units of delivery and a percentage over them would say they are.
        self.assertNotIn("% complete", document)
        self.assertNotIn("Completion", document)

    def test_the_totals_row_is_the_tally_the_jira_summary_carries(self):
        requirements = multi_source(count_per_key=2)
        tallied = outcomes_mod.tally(requirements)
        document = self.render(requirements)
        problems = assemble_mod._html_problems(document, tallied, requirements)
        self.assertEqual(problems, [])
        # And a document rendered from a different tally is caught, which is
        # the only reason the check is worth having.
        other = outcomes_mod.tally(multi_source(count_per_key=1))
        self.assertTrue(assemble_mod._html_problems(document, other, requirements))

    def test_the_third_outcome_column_says_confirmed_unmet_not_unmet(self):
        """"Unmet" invites a reader to file "we did not look" under it."""
        document = self.render(multi_source(count_per_key=1))
        self.assertIn("Confirmed unmet", document)

    def test_the_live_count_starts_at_every_criterion(self):
        document = self.render(multi_source(count_per_key=3))
        self.assertIn("Showing all 9 criteria", document)
        self.assertEqual(len(self.rows(document)), 9)

    # --- identity --------------------------------------------------------

    def test_every_criterion_id_is_qualified_with_its_source_jira(self):
        """`AC1` belongs to three issues here. A bare one points at none."""
        document = self.render(multi_source(count_per_key=2))
        for row in self.rows(document):
            label = re.search(r'<span class="cid">([^<]+)</span>', row)
            self.assertIsNotNone(label, row[:200])
            self.assertRegex(label.group(1), r"^RHOAIENG-\d+ AC\d+$")

    def test_each_group_is_headed_by_its_linked_jira_issue(self):
        document = self.render(
            multi_source(count_per_key=1),
            jira={"key": "RHOAIENG-2200", "summary": "Quota policy",
                  "site": "https://jira.example.com",
                  "children": [{"key": "RHOAIENG-2201", "summary": "Rate policy"}]},
        )
        self.assertIn(
            '<a href="https://jira.example.com/browse/RHOAIENG-2201" rel="noreferrer noopener">'
            "RHOAIENG-2201 — Rate policy</a>",
            document,
        )
        # No title recorded for this one, so the key stands alone rather than
        # borrowing the parent's.
        self.assertIn(">RHOAIENG-2202</a>", document)

    # --- missing data ----------------------------------------------------

    def test_an_uninspected_downstream_step_is_not_reported_as_a_negative_result(self):
        requirements = multi_source(count_per_key=1, keys=("RHOAIENG-2201",))
        document = self.render(requirements)
        self.assertIn("Not inspected", document)
        self.assertIn("that is not confirmation that none is required", document)
        self.assertNotIn("No downstream step is required", document)

    def test_an_absent_release_target_and_baseline_say_so(self):
        document = self.render(multi_source(count_per_key=1))
        self.assertIn("Not recorded on the Jira issue", document)
        self.assertIn("baseline established by this run", document)
        self.assertIn("No baseline to compare against.", document)
        self.assertIn("nothing to compare against", document)

    def test_movement_is_withheld_rather_than_computed_across_a_changed_scope(self):
        """A ratio whose denominator moved is not movement in the work."""
        document = self.render(
            multi_source(count_per_key=2),
            diff={
                "baseline": {"generatedAt": "2026-09-01T00:00:00Z", "publication": "published"},
                "requirementChanges": {"added": [{"id": "AC9", "sourceKey": "RHOAIENG-2201"}]},
                "matchedPairs": [],
            },
        )
        self.assertIn("Numerical movement is unavailable", document)
        self.assertIn("different denominators", document)
        self.assertIn("1 added", document)
        # Scope growth is reported as scope, never as delivery.
        self.assertIn("A larger assessed inventory is not delivery progress", document)

    def test_newly_visible_evidence_is_not_reported_as_new_implementation(self):
        requirements = multi_source(count_per_key=1, keys=("RHOAIENG-2201",))
        requirements[0].update(
            assessment="Evidence found",
            evidence=[{"ref": PR_A, "kind": "pr", "at": "2026-08-01T00:00:00Z"}],
        )
        document = self.render(
            requirements,
            diff={
                "baseline": {"generatedAt": "2026-09-01T00:00:00Z"},
                "matchedPairs": [{"sourceKey": "RHOAIENG-2201", "currentId": "AC1",
                                  "previousId": "AC1",
                                  "previousAssessment": "No evidence found",
                                  "textChanged": False}],
            },
        )
        self.assertIn("Newly discovered evidence, not newly done work", document)
        self.assertNotIn("New implementation", document)

    # --- limitations -----------------------------------------------------

    def test_an_incomplete_traversal_raises_the_banner_and_names_the_branch(self):
        document = self.render(
            multi_source(count_per_key=1),
            manifest={
                "children": [], "epics": [EPIC], "observed": True,
                "traversalComplete": False,
                "untraversed": [{"ref": "example-org/example-quota#900",
                                 "reason": "already 1 level below the mapped epic",
                                 "nestedVia": "sub-issue"}],
                "access": [{"ref": "example-org/private#1", "status": "forbidden",
                            "detail": "not visible to this account"}],
            },
        )
        self.assertIn("Material collection limitations apply", document)
        self.assertIn("example-org/example-quota#900", document)
        self.assertIn("Traversal did not complete", document)
        self.assertIn("not visible to this account", document)
        self.assertIn("a floor, not a total", document)

    def test_a_clean_run_gets_no_banner_rather_than_a_manufactured_warning(self):
        document = self.render(multi_source(count_per_key=1))
        self.assertNotIn('class="banner"', document)
        self.assertNotIn("Material collection limitations", document)

    def test_an_unmapped_epic_is_unassessable_not_unstarted(self):
        document = self.render(
            multi_source(count_per_key=1),
            mappings=[],
            manifest={"children": [], "epics": [], "observed": False,
                      "unobservedReason": "no upstream link on the Jira issue"},
        )
        self.assertIn("Upstream coverage is unassessable here, not absent", document)
        self.assertNotIn("Not started", document)

    # --- evidence and narrative ------------------------------------------

    def test_evidence_links_carry_their_state_date_and_commit_pinned_files(self):
        requirements = multi_source(count_per_key=1, keys=("RHOAIENG-2201",))
        requirements[0].update(
            assessment="Evidence found",
            evidenceState="tested",
            evidence=[{
                "ref": PR_A, "kind": "pr", "state": "merged", "at": "2026-09-18T09:00:00Z",
                "files": [{"repo": "example-org/example-quota", "commit": "9f3c2abdeadbeef",
                           "path": "src/quota/tier.rs"}],
            }],
        )
        document = self.render(requirements)
        self.assertIn(f"https://github.com/{PR_A.split('#')[0]}/pull/500", document)
        self.assertIn("merged · 2026-09-18", document)
        self.assertIn(
            "https://github.com/example-org/example-quota/blob/9f3c2abdeadbeef/src/quota/tier.rs",
            document,
        )
        self.assertIn("@ 9f3c2ab", document)
        self.assertIn("Test execution verified in CI", document)

    def test_a_file_without_a_recorded_commit_is_dropped_rather_than_floated(self):
        """An unpinned path points at whatever that file says today."""
        requirements = multi_source(count_per_key=1, keys=("RHOAIENG-2201",))
        requirements[0].update(
            assessment="Evidence found",
            evidence=[{"ref": PR_A, "kind": "pr",
                       "files": [{"repo": "example-org/example-quota",
                                  "path": "src/quota/tier.rs"}]}],
        )
        self.assertNotIn("src/quota/tier.rs", self.render(requirements))

    def test_narrative_entries_carry_their_rows_and_their_links(self):
        requirements = multi_source(count_per_key=1, keys=("RHOAIENG-2201",))
        requirements[0].update(
            assessment="Evidence found",
            evidence=[{"ref": PR_A, "kind": "pr", "state": "merged"}],
        )
        document = self.render(
            requirements,
            narrative=[{"bullet": "decisions-needed",
                        "text": "Whether metering counts denials is unrecorded",
                        "refs": [{"sourceKey": "RHOAIENG-2201", "id": "AC1"}],
                        "links": [PR_A]}],
        )
        self.assertIn("Decisions needed", document)
        self.assertIn("Whether metering counts denials is unrecorded", document)
        self.assertIn(">RHOAIENG-2201 AC1</a>", document)
        self.assertIn(f"https://github.com/{PR_A.split('#')[0]}/pull/500", document)

    def test_a_dependency_gets_no_owner_or_date_unless_a_source_recorded_one(self):
        document = self.render(
            multi_source(count_per_key=1, keys=("RHOAIENG-2201",)),
            dependencies=[{"ref": "example-org/example-quota#901", "criteria": ["AC1"],
                           "note": "Named on an issue that was read."}],
        )
        self.assertIn("Named on an issue that was read.", document)
        self.assertNotIn("Owner", document)
        self.assertNotIn("Unassigned", document)

    # --- escaping and unsafe links ---------------------------------------

    def test_markup_in_issue_text_is_escaped_rather_than_rendered(self):
        hostile = "<img src=x onerror=alert(1)>&\"'</details><script>alert(2)</script>"
        requirements = multi_source(count_per_key=1, keys=("RHOAIENG-2201",))
        requirements[0].update(
            text=hostile,
            coverageDetail=hostile,
            gap=hostile,
            uncoveredClauses=[hostile],
            downstream={"state": "pending", "detail": hostile},
        )
        document = self.render(
            requirements,
            jira={"key": "RHOAIENG-2200", "summary": hostile, "site": "https://jira.example.com"},
        )
        self.assertNotIn("<img", document)
        self.assertNotIn("<script>alert(2)", document)
        self.assertNotIn("</details><script>", document)
        # The string survives in full; what it does not do is open a tag.
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", document)
        self.assertIn("&amp;&quot;&#x27;&lt;/details&gt;", document)
        # Exactly one script element: the embedded filter logic, nothing else.
        self.assertEqual(document.count("<script"), 1)
        # And the row survived: escaping must not break out of the disclosure.
        self.assertEqual(len(self.rows(document)), 1)

    def test_a_search_attribute_cannot_be_broken_out_of(self):
        requirements = multi_source(count_per_key=1, keys=("RHOAIENG-2201",))
        requirements[0]["text"] = '" data-attention="0" x="'
        document = self.render(requirements)
        self.assertIn("&quot;", document)
        self.assertEqual(document.count('data-attention="1"'), 1)
        self.assertNotIn('data-attention="0"', document)

    def test_a_non_http_url_renders_as_text_and_never_as_an_href(self):
        for hostile in ("javascript:alert(1)", "data:text/html;base64,PHNjcmlwdD4=",
                        "file:///etc/passwd", "full-assessment.html"):
            self.assertIsNone(links_mod.safe_url(hostile), hostile)
            document = self.render(
                multi_source(count_per_key=1, keys=("RHOAIENG-2201",)),
                mappings=[{"ref": EPIC, "url": hostile, "title": "Epic"}],
            )
            self.assertNotIn(f'href="{hostile}"', document)
            self.assertNotIn("javascript:", document)

    def test_a_relative_path_is_not_published_as_a_jira_full_assessment_link(self):
        """A local HTML file is not a durable link; it 404s against the Jira host."""
        requirements = multi_source(count_per_key=1, keys=("RHOAIENG-2201",))
        tallied = outcomes_mod.tally(requirements)
        base = {"generatedAt": "2026-10-01T00:00:00Z",
                "jira": {"key": "RHOAIENG-2200", "summary": "Quota policy"},
                "manifest": {"children": [], "epics": [], "observed": True},
                "requirements": requirements, "mappings": [], "narrative": []}
        confidence = outcomes_mod.confidence(base, requirements, tallied)
        for bad in ("full-assessment.html", "/tmp/out.html", "file:///tmp/out.html"):
            rendered = summary_mod.render(base, tallied, confidence, full_assessment_url=bad)
            self.assertNotIn("Full assessment", rendered, bad)
        good = summary_mod.render(
            base, tallied, confidence,
            full_assessment_url="https://reports.example.com/RHOAIENG-2200.html",
        )
        self.assertIn("[Full assessment](https://reports.example.com/RHOAIENG-2200.html)", good)

    def test_no_local_path_or_external_resource_reaches_the_document(self):
        document = self.render(multi_source(count_per_key=2))
        self.assertEqual(links_mod.unpublishable(document), [])
        self.assertNotIn("@import", document)
        self.assertNotIn("fetch(", document)
        for url in re.findall(r'(?:href|src)="([^"#][^"]*)"', document):
            self.assertRegex(url, r"^https://(github\.com|jira\.example\.com)/", url)

    # --- structure --------------------------------------------------------

    def test_the_document_is_balanced_and_self_contained(self):
        document = self.render(multi_source(count_per_key=2))
        self.assertTrue(document.startswith("<!DOCTYPE html>"))
        parser = _TagBalance()
        parser.feed(document)
        self.assertEqual(parser.errors, [])
        self.assertEqual([tag for tag, _ in parser.stack], [])
        for element in ("toggle-all", "f-outcome", "f-type", "f-attention", "visible-count", "q"):
            self.assertIn(f'id="{element}"', document)

    def test_the_print_rules_both_open_the_rows_and_give_them_room(self):
        """Forcing the panel to display is half a fix, and the half that prints wrong.

        A closed `<details>` applies size containment to its content, so the
        panel paints at full height while the row is sized as if empty - every
        evidence panel lands on top of the rows beneath it. Nothing about that
        is visible on screen, which is why it is asserted here.
        """
        document = self.render(multi_source(count_per_key=1))
        print_rules = document.split("@media print {")[1]
        self.assertIn("details.row > .detail { display: grid !important; }", print_rules)
        self.assertIn("details.row::details-content", print_rules)
        self.assertIn("content-visibility: visible", print_rules)
        # And the fallback for a browser without `::details-content`.
        self.assertIn("'beforeprint'", document)
        self.assertIn("'afterprint'", document)
        # Controls are the one thing paper must not carry.
        self.assertIn(".no-print { display: none !important; }", print_rules)
        self.assertIn('class="controls no-print"', document)
        self.assertIn('class="toggle no-print"', document)

    def test_the_sections_appear_in_the_contracted_order(self):
        document = self.render(
            multi_source(count_per_key=1),
            narrative=[{"bullet": "next-actions", "text": "Link the telemetry work",
                        "refs": [{"sourceKey": "RHOAIENG-2201", "id": "AC1"}]}],
            manifest={"children": [], "epics": [EPIC], "observed": True,
                      "traversalComplete": False},
        )
        order = [
            document.index(marker)
            for marker in ('class="head"', 'class="banner"', ">Overview<",
                           ">Decisions and follow-up<", ">Requirement review<",
                           ">Changes since baseline<", ">Collection scope and limitations<")
        ]
        self.assertEqual(order, sorted(order))


class _TagBalance(html_parser.HTMLParser):
    """Enough of a parser to prove no element is left open or crossed.

    A browser will silently repair unbalanced markup, which is exactly why an
    unclosed `<details>` would not show up by looking at the thing.
    """

    VOID = {"meta", "br", "hr", "img", "input", "link", "source", "col", "area", "base"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append((tag, self.getpos()))

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack:
            self.errors.append(f"stray </{tag}> at {self.getpos()}")
            return
        open_tag, where = self.stack.pop()
        if open_tag != tag:
            self.errors.append(f"</{tag}> at {self.getpos()} closes <{open_tag}> from {where}")


class CliTest(unittest.TestCase):
    """One end-to-end pass through the actual command line."""

    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="jgr-cli-")
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.env = dict(
            os.environ,
            JGR_HOME=self.home,
            GH_BIN=os.path.join(ROOT, "tests", "fakegh.py"),
            GH_WORLD=os.path.join(self.home, "world.json"),
        )
        with open(self.env["GH_WORLD"], "w", encoding="utf-8") as handle:
            json.dump(base_world(), handle)

    def run_cli(self, *args, stdin=None):
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "rollup.py"), *args],
            capture_output=True, text=True, env=self.env, input=stdin,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # Kept for the tests that care what the command said as well as what
        # it wrote: the word-budget notice goes to stderr, not into the draft.
        self.stderr = proc.stderr
        return proc.stdout

    def path(self, name):
        return os.path.join(self.home, name)

    def test_collect_diff_assemble_measure(self):
        self.run_cli(
            "collect", "--key", KEY, "--epics", json.dumps([EPIC]),
            "--out", self.path("manifest.json"),
        )
        with open(self.path("manifest.json")) as handle:
            manifest = json.load(handle)
        self.assertEqual(len(manifest["children"]), 3)
        self.assertTrue(manifest["observed"])

        with open(self.path("requirements.json"), "w") as handle:
            json.dump(REQUIREMENTS, handle)
        self.run_cli(
            "diff", "--manifest", self.path("manifest.json"),
            "--requirements", self.path("requirements.json"),
            "--out", self.path("diff.json"),
        )
        with open(self.path("diff.json")) as handle:
            plan = json.load(handle)
        self.assertEqual(len(plan["reassess"]), 2)

        with open(self.path("assessments.json"), "w") as handle:
            json.dump(
                [assessment("AC1", "Evidence found", [{"ref": PR_A, "kind": "pr", "state": "merged",
                                                       "at": "2026-09-18T09:00:00Z"}], "merged"),
                 assessment("AC2", "No evidence found", [], "none")],
                handle,
            )
        with open(self.path("assembly.json"), "w") as handle:
            json.dump(
                {"jira": {"key": KEY, "summary": "Tiered quota", "status": "In Progress"},
                 "mappings": [{"ref": EPIC, "url": f"https://github.com/{EPIC}"}],
                 "summary": "Upstream work is underway."},
                handle,
            )
        out = self.run_cli(
            "assemble", "--in", self.path("assembly.json"),
            "--manifest", self.path("manifest.json"),
            "--diff", self.path("diff.json"),
            "--requirements", self.path("requirements.json"),
            "--assessments", self.path("assessments.json"),
            "--report", self.path("report.md"),
            "--out", self.path("result.json"),
        )
        self.assertIn("result.json", out)
        with open(self.path("report.md")) as handle:
            report = handle.read()
        self.assertIn("### Upstream Development Rollup", report)
        self.assertIn("AC1 (RHOAIENG-7001)", report)
        self.assertIn("AC2 (RHOAIENG-7001)", report)

        excerpt = json.loads(
            self.run_cli("excerpt", "--key", KEY, "--ref", EPIC, "--field", "body")
        )
        self.assertEqual(excerpt["text"], "Epic body.")
        self.assertFalse(excerpt["truncated"])

        measured = json.loads(self.run_cli("measure", self.path("manifest.json")))
        self.assertGreater(measured["total"]["bytes"], 0)

    def test_an_over_budget_draft_says_so_where_the_draft_is_read(self):
        """`summaryWordBudget.within: false` reached the approval step silently.

        The run still finishes and still writes the draft - refusing to render
        was never the fix. What is new is that the command says the draft is
        over the ceiling, on stderr, beside the summary somebody is about to
        be asked to approve.
        """
        self.run_cli("collect", "--key", KEY, "--epics", json.dumps([EPIC]),
                     "--out", self.path("manifest.json"))
        with open(self.path("requirements.json"), "w") as handle:
            json.dump(REQUIREMENTS, handle)
        self.run_cli("diff", "--manifest", self.path("manifest.json"),
                     "--requirements", self.path("requirements.json"),
                     "--out", self.path("diff.json"))
        with open(self.path("assessments.json"), "w") as handle:
            json.dump([assessment("AC1", "Evidence found", [{"ref": PR_A}], "merged"),
                       assessment("AC2", "No evidence found", [], "none")], handle)
        prose = " ".join(["word"] * 200)
        with open(self.path("narrative.json"), "w") as handle:
            json.dump(
                [{"bullet": slug, "text": prose, "links": [],
                  "refs": [{"sourceKey": KEY, "id": "AC1" if slug == "evidence-established"
                            else "AC2"}]}
                 for slug in ("evidence-established", "remaining-work")],
                handle,
            )
        with open(self.path("assembly.json"), "w") as handle:
            json.dump({"jira": {"key": KEY, "summary": "Tiered quota", "status": "In Progress"},
                       "mappings": [{"ref": EPIC, "url": f"https://github.com/{EPIC}"}],
                       "summary": "Upstream work is underway."}, handle)

        self.run_cli(
            "assemble", "--in", self.path("assembly.json"),
            "--manifest", self.path("manifest.json"), "--diff", self.path("diff.json"),
            "--requirements", self.path("requirements.json"),
            "--assessments", self.path("assessments.json"),
            "--narrative", self.path("narrative.json"),
            "--report", self.path("report.md"), "--summary", self.path("summary.md"),
            "--out", self.path("result.json"),
        )
        self.assertIn("notice: the Jira summary draft is", self.stderr)
        self.assertIn("words against a 350-word ceiling", self.stderr)

        with open(self.path("result.json")) as handle:
            result = json.load(handle)
        self.assertEqual(result["summaryWordBudget"]["condition"], "over-ceiling")
        self.assertFalse(result["summaryWordBudget"]["within"])
        self.assertGreaterEqual(result["summaryWordBudget"]["authored"]["narrative"], 400)
        self.assertIn("rewrite", result["summaryBudgetNotice"].lower())

        # The notice is for the person approving, never for the Jira reader:
        # it must not reach the thing that gets posted.
        with open(self.path("summary.md")) as handle:
            summary = handle.read()
        self.assertNotIn("ceiling", summary)
        self.assertIn(prose, summary)

        # Re-rendering the stored draft reports the condition and says nothing.
        # The prose is the stored prose; "rewrite before approval" is advice
        # about an approval that already happened.
        self.run_cli("rerender", "--snapshot", result["snapshotPath"],
                     "--summary", self.path("again.md"), "--out", self.path("again.json"))
        self.assertNotIn("notice:", self.stderr)
        with open(self.path("again.json")) as handle:
            self.assertEqual(
                json.load(handle)["summaryWordBudget"]["condition"], "over-ceiling"
            )

    def test_a_pr_description_is_collected_and_excerptable(self):
        """`excerpt --kind pr --field body` is the documented read of a PR.

        `PR_FIELDS` did not ask `gh` for `body`, so that read failed for every
        pull request ever collected - with "no field 'body'", which reads like
        an empty description rather than a field nobody requested.
        """
        self.assertIn("body", collect_mod.PR_FIELDS)
        with open(self.env["GH_WORLD"], encoding="utf-8") as handle:
            world = json.load(handle)
        world["prs"][PR_A]["body"] = "Routes by tier at the proxy edge."
        with open(self.env["GH_WORLD"], "w", encoding="utf-8") as handle:
            json.dump(world, handle)

        self.run_cli(
            "collect", "--key", KEY, "--epics", json.dumps([EPIC]),
            "--out", self.path("manifest.json"),
        )
        excerpt = json.loads(
            self.run_cli("excerpt", "--key", KEY, "--ref", PR_A, "--kind", "pr", "--field", "body")
        )
        self.assertEqual(excerpt["text"], "Routes by tier at the proxy edge.")

    def test_a_missing_field_says_which_fields_the_payload_has(self):
        self.run_cli(
            "collect", "--key", KEY, "--epics", json.dumps([EPIC]),
            "--out", self.path("manifest.json"),
        )
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "rollup.py"), "excerpt",
             "--key", KEY, "--ref", PR_A, "--kind", "pr", "--field", "bdoy"],
            capture_output=True, text=True, env=self.env,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no field 'bdoy'", proc.stderr)
        self.assertIn("it carries", proc.stderr)
        self.assertIn("mergedAt", proc.stderr)

    def test_the_no_mapping_path_assembles_once_and_reports_the_jira_side(self):
        """The partial run, exactly as SKILL.md spells it.

        `assembly.json` has to exist before `assemble`: `--in` reads it, and
        `--manifest`/`--diff` only override two of its keys. The procedure
        used to run `assemble` against a file nobody had written and then send
        the reader to a step that assembles again.
        """
        self.run_cli(
            "collect", "--key", KEY, "--epics", "[]", "--out", self.path("manifest.json")
        )
        with open(self.path("manifest.json")) as handle:
            manifest = json.load(handle)
        self.assertFalse(manifest["observed"])

        with open(self.path("requirements.json"), "w") as handle:
            json.dump(REQUIREMENTS, handle)
        self.run_cli(
            "diff", "--manifest", self.path("manifest.json"),
            "--requirements", self.path("requirements.json"),
            "--out", self.path("diff.json"),
        )
        with open(self.path("assembly.json"), "w") as handle:
            json.dump(
                {"jira": {"key": KEY, "summary": "Tiered quota", "status": "In Progress"},
                 "mappings": [],
                 "summary": "No upstream source was inspected: no epic is linked."},
                handle,
            )
        self.run_cli(
            "assemble", "--in", self.path("assembly.json"),
            "--manifest", self.path("manifest.json"),
            "--diff", self.path("diff.json"),
            "--requirements", self.path("requirements.json"),
            "--assessments", "[]",
            "--report", self.path("report.md"),
            "--summary", self.path("summary.md"),
            "--out", self.path("result.json"),
        )
        with open(self.path("result.json")) as handle:
            result = json.load(handle)
        with open(self.path("report.md")) as handle:
            report = handle.read()
        with open(self.path("summary.md")) as handle:
            summary = handle.read()

        # Both criteria are reported, neither is judged, and the child count
        # is unknown rather than a zero nobody measured.
        self.assertEqual(result["outcomes"]["unverified"], 2)
        self.assertEqual(result["metrics"]["children"], "unknown")
        self.assertIn("AC1 (RHOAIENG-7001)", report)
        self.assertIn("Upstream coverage is unassessable, not absent.", report)
        self.assertIn("No upstream epic is linked on this issue.", summary)
        self.assertEqual(links_mod.unpublishable(summary), [])

    def test_rerender_reproduces_the_saved_summary_without_reassessing(self):
        narrative = [
            {"bullet": "evidence-established",
             "text": "Tier routing lands for the paid pool",
             "refs": [{"sourceKey": KEY, "id": "AC1"}],
             "links": [PR_A]},
            {"bullet": "decisions-needed",
             "text": "Whether metering counts denials is unrecorded",
             "refs": [{"sourceKey": KEY, "id": "AC2"}]},
        ]
        self.run_cli(
            "collect", "--key", KEY, "--epics", json.dumps([EPIC]),
            "--out", self.path("manifest.json"),
        )
        with open(self.path("requirements.json"), "w") as handle:
            json.dump(REQUIREMENTS, handle)
        self.run_cli(
            "diff", "--manifest", self.path("manifest.json"),
            "--requirements", self.path("requirements.json"),
            "--out", self.path("diff.json"),
        )
        with open(self.path("assessments.json"), "w") as handle:
            json.dump(
                [assessment("AC1", "Evidence found",
                            [{"ref": PR_A, "kind": "pr", "state": "merged",
                              "at": "2026-09-18T09:00:00Z"}], "merged"),
                 assessment("AC2", "No evidence found", [], "none")],
                handle,
            )
        with open(self.path("assembly.json"), "w") as handle:
            json.dump(
                {"jira": {"key": KEY, "summary": "Tiered quota", "status": "In Progress"},
                 "mappings": [{"ref": EPIC, "url": f"https://github.com/{EPIC}"}],
                 "summary": "Routing landed; metering is undecided."},
                handle,
            )
        with open(self.path("narrative.json"), "w") as handle:
            json.dump(narrative, handle)

        self.run_cli(
            "assemble", "--in", self.path("assembly.json"),
            "--manifest", self.path("manifest.json"),
            "--diff", self.path("diff.json"),
            "--requirements", self.path("requirements.json"),
            "--assessments", self.path("assessments.json"),
            "--narrative", self.path("narrative.json"),
            "--summary", self.path("summary.md"),
            "--report", self.path("report.md"),
            "--out", self.path("result.json"),
        )
        with open(self.path("result.json")) as handle:
            result = json.load(handle)
        with open(self.path("summary.md")) as handle:
            original = handle.read()
        self.assertEqual(result["narrativeClaims"], 2)
        self.assertIn("Tier routing lands for the paid pool", original)

        snapshot, _ = snapshots_mod.load(result["snapshotPath"])
        self.assertEqual(snapshot["narrative"], narrative)
        self.assertEqual(snapshot["summaryNarrative"], "Routing landed; metering is undecided.")

        # No --title and no --site: everything the summary is rendered with
        # has to come out of the snapshot, or "re-render" means "render a
        # different document from the same rows".
        self.assertEqual(snapshot["jiraSummary"], "Tiered quota")
        self.run_cli(
            "rerender", "--snapshot", result["snapshotPath"],
            "--summary", self.path("again.md"),
            "--report", self.path("again-report.md"),
            "--out", self.path("again.json"),
        )
        with open(self.path("again.md")) as handle:
            again = handle.read()
        self.assertEqual(again, original, "re-rendering must reproduce what was reviewed")
        with open(self.path("again-report.md")) as handle:
            self.assertIn("Routing landed; metering is undecided.", handle.read())

    def test_the_html_report_rerenders_from_a_snapshot_with_gh_removed(self):
        """A snapshot is the whole input. Re-rendering must not reach anything.

        `gh` is pointed at a binary that always fails and the cache directory
        is deleted, so any attempt to collect - or to quietly fall back to a
        cached payload - fails the run rather than producing a document that
        looks the same but was assembled from something else.
        """
        self.run_cli(
            "collect", "--key", KEY, "--epics", json.dumps([EPIC]),
            "--out", self.path("manifest.json"),
        )
        with open(self.path("requirements.json"), "w") as handle:
            json.dump(REQUIREMENTS, handle)
        self.run_cli(
            "diff", "--manifest", self.path("manifest.json"),
            "--requirements", self.path("requirements.json"),
            "--out", self.path("diff.json"),
        )
        with open(self.path("assessments.json"), "w") as handle:
            json.dump(
                [assessment("AC1", "Evidence found",
                            [{"ref": PR_A, "kind": "pr", "state": "merged",
                              "at": "2026-09-18T09:00:00Z"}], "merged"),
                 assessment("AC2", "No evidence found", [], "none")],
                handle,
            )
        with open(self.path("assembly.json"), "w") as handle:
            json.dump(
                {"jira": {"key": KEY, "summary": "Tiered quota",
                          "site": "https://jira.example.com",
                          "fixVersions": ["2026.3"]},
                 "mappings": [{"ref": EPIC, "url": f"https://github.com/{EPIC}"}],
                 "summary": "Routing landed; metering is undecided."},
                handle,
            )
        self.run_cli(
            "assemble", "--in", self.path("assembly.json"),
            "--manifest", self.path("manifest.json"),
            "--diff", self.path("diff.json"),
            "--requirements", self.path("requirements.json"),
            "--assessments", self.path("assessments.json"),
            "--summary", self.path("summary.md"),
            "--report", self.path("report.md"),
            "--html", self.path("full.html"),
            "--out", self.path("result.json"),
        )
        with open(self.path("result.json")) as handle:
            result = json.load(handle)
        self.assertEqual(result["htmlPath"], self.path("full.html"))
        with open(self.path("full.html")) as handle:
            first = handle.read()
        # The document is written, not printed: stdout carries a byte count so
        # a quarter of a megabyte of markup never lands in the conversation.
        self.assertEqual(result["htmlBytes"], len(first.encode("utf-8")))

        shutil.rmtree(os.path.join(self.home, "cache"), ignore_errors=True)
        offline = dict(self.env, GH_BIN="/usr/bin/false")
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "rollup.py"), "rerender",
             "--snapshot", result["snapshotPath"],
             "--summary", self.path("off.md"), "--report", self.path("off-report.md"),
             "--html", self.path("off.html"), "--out", self.path("off.json")],
            capture_output=True, text=True, env=offline,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(self.path("off.html")) as handle:
            again = handle.read()
        self.assertEqual(again, first, "re-rendering must reproduce the reviewed document")

        # The recorded release target survives the round trip. Without it on
        # the snapshot the re-render would say "Not recorded on the Jira
        # issue", which is a different and false statement.
        self.assertIn("2026.3", again)
        self.assertNotIn(self.home, again)
        self.assertEqual(links_mod.unpublishable(again), [])

    def _cache_checks(self):
        """`pr-checks` is cached as a bare list, unlike every other kind."""
        cache = cache_mod.Cache(KEY, root=os.path.join(self.home, "cache", KEY))
        cache.put("pr-checks", EPIC, [
            {"name": "unit", "state": "SUCCESS", "bucket": "pass"},
            {"name": "signoff-check", "state": "FAILURE", "bucket": "fail"},
        ])
        return cache

    def test_a_list_payload_is_read_whole_and_matched_by_line(self):
        cache = self._cache_checks()
        excerpt = json.loads(self.run_cli(
            "excerpt", "--key", KEY, "--ref", EPIC, "--kind", "pr-checks",
            "--field", "", "--match", "FAILURE", "--context", "1",
            "--cache-dir", cache.root,
        ))
        # One line, not one blob: a compact dump would make every match return
        # the whole payload, which is what excerpt exists to avoid.
        self.assertEqual(excerpt["matchedLines"], 1)
        self.assertIn("signoff-check", excerpt["text"])
        self.assertNotIn("unit", excerpt["text"])

    def test_a_field_path_into_a_list_payload_says_how_to_read_it(self):
        cache = self._cache_checks()
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "rollup.py"), "excerpt",
             "--key", KEY, "--ref", EPIC, "--kind", "pr-checks",
             "--field", "bucket", "--cache-dir", cache.root],
            capture_output=True, text=True, env=self.env,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("--field ''", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
