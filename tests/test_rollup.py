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
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, ".claude", "skills", "jira-github-rollup", "scripts")
sys.path.insert(0, SCRIPTS)

from jgr import assemble as assemble_mod  # noqa: E402
from jgr import cache as cache_mod  # noqa: E402
from jgr import collect as collect_mod  # noqa: E402
from jgr import convert as convert_mod  # noqa: E402
from jgr import diff as diff_mod  # noqa: E402
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


def issue(ref, title, state="OPEN", reason=None, body="", closed=None, updated="2026-09-01T00:00:00Z", labels=None):
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
        "closedAt": closed,
        "updatedAt": updated,
    }


def pull(ref, state="OPEN", merged=None, updated="2026-09-01T00:00:00Z"):
    repo, number = ref.split("#")
    return {
        "number": int(number),
        "title": f"PR {number}",
        "state": "MERGED" if merged else state,
        "isDraft": False,
        "mergedAt": merged,
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
        "prs": {PR_A: pull(PR_A, merged="2026-09-18T09:00:00Z")},
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

    def run_once(self, requirements, assessments, epics=(EPIC,), generated_at=None, full_refresh=False, key=KEY):
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
        self.run_once(
            REQUIREMENTS,
            [
                assessment("AC1", "Evidence found",
                           [{"ref": PR_A, "kind": "pr", "state": "merged",
                             "at": "2026-09-18T09:00:00Z"}], "merged", "pending"),
                assessment("AC2", "Evidence found",
                           [{"ref": PR_B, "kind": "pr", "state": "merged",
                             "at": "2026-09-18T09:00:00Z"}], "merged", "confirmed"),
            ],
            generated_at="2026-10-01T00:00:00Z",
        )
        plan = self.plan(self.collect(), REQUIREMENTS)
        self.assertEqual([entry["id"] for entry in plan["reassess"]], ["AC1"])
        self.assertIn("downstream qualification was outstanding", plan["reassess"][0]["reason"])
        self.assertEqual([entry["id"] for entry in plan["reuse"]], ["AC2"])

    def test_an_unknown_downstream_is_still_reusable(self):
        """Nobody looked then and nobody looked now; repeating that is honest."""
        self.run_once(
            REQUIREMENTS,
            [
                assessment("AC1", "Evidence found",
                           [{"ref": PR_A, "kind": "pr", "state": "merged",
                             "at": "2026-09-18T09:00:00Z"}], "merged", "unknown"),
                assessment("AC2", "Evidence found",
                           [{"ref": PR_B, "kind": "pr", "state": "merged",
                             "at": "2026-09-18T09:00:00Z"}], "merged", "unknown"),
            ],
            generated_at="2026-10-01T00:00:00Z",
        )
        plan = self.plan(self.collect(), REQUIREMENTS)
        self.assertEqual(plan["reassess"], [])

    def test_a_dependency_closing_between_runs_invalidates_what_rests_on_it(self):
        """A declared dependency is inspected but not traversed, so it has no child hash."""
        dependency = "example-org/example-meter#900"
        self.world["issues"][CHILD_A]["body"] = f"Routing work. Depends on {dependency}"
        self.world["issues"][dependency] = {
            "title": "Meter API", "body": "", "state": "OPEN", "stateReason": "",
            "url": f"https://github.com/{dependency.replace('#', '/issues/')}",
            "updatedAt": "2026-09-01T00:00:00Z", "closedAt": None,
        }
        self.run_once(
            REQUIREMENTS,
            [
                assessment("AC1", "Evidence found",
                           [{"ref": dependency, "kind": "issue", "at": "2026-09-18T09:00:00Z"}],
                           "merged", "confirmed"),
                assessment("AC2", "Evidence found",
                           [{"ref": PR_B, "kind": "pr", "state": "merged",
                             "at": "2026-09-18T09:00:00Z"}], "merged", "confirmed"),
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
                assessment("AC1", "Evidence found", [{"ref": CHILD_A, "kind": "issue",
                                                      "at": "2026-09-18T10:00:00Z"}], "merged", "confirmed"),
                assessment("AC2", "No evidence found", [], "none"),
                assessment("AC3", "Evidence found", [{"ref": CHILD_C, "kind": "issue",
                                                      "at": "2026-09-10T00:00:00Z"}], "merged", "confirmed"),
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
                assessment("AC1", "Evidence found", [{"ref": CHILD_C, "kind": "issue",
                                                      "at": "2026-09-10T00:00:00Z"}], "merged", "confirmed"),
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

    def test_a_child_with_its_own_sub_issues_is_a_nested_epic(self):
        self.world["subIssues"][CHILD_B] = [
            "example-org/example-quota#901",
            "example-org/example-quota#902",
        ]
        manifest = self.collect()
        child = self.nested(manifest, CHILD_B)
        self.assertTrue(child["nested"])
        self.assertEqual(child["nestedVia"], "sub-issues")
        self.assertIn(
            f"{CHILD_B} looks like a nested epic; it was recorded but not traversed.",
            manifest["traversalNotes"],
        )
        # Recorded, not traversed: its own sub-issues stay out of the manifest.
        self.assertNotIn(
            "example-org/example-quota#901", [c["ref"] for c in manifest["children"]]
        )

    def test_the_scope_caveat_agrees_with_itself_on_one_nested_epic(self):
        self.world["subIssues"][CHILD_B] = [
            "example-org/example-quota#901",
            "example-org/example-quota#902",
        ]
        manifest = self.collect()
        caveat = summary_mod._scope_caveat(manifest)
        self.assertIn("1 nested epic was recorded", caveat)
        # Both stages ran on one collector; the note must appear once.
        self.assertEqual(len(manifest["traversalNotes"]), 1)

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
        declared = assessment(
            "AC2", "No evidence found",
            [{"ref": PR_B, "kind": "pr", "state": "merged", "at": "2026-09-20T09:00:00Z"}],
            "merged",
        )
        declared["outcome"] = "confirmed-unmet"
        result, _, summary = self.both(
            assessments=[
                assessment("AC1", "Evidence found",
                           [{"ref": PR_A, "kind": "pr", "state": "merged",
                             "at": "2026-09-18T09:00:00Z"}], "merged"),
                declared,
            ]
        )
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
        claim["uncoveredClauses"] = ["nothing establishes the per-tier rate limit"]
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
        claim["uncoveredClauses"] = ["nothing establishes rejection above the tier quota"]
        _, report, _ = self.both(
            assessments=[claim, assessment("AC2", "No evidence found", [], "none")]
        )
        self.assertIn("Clause not covered", report)
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
        """It belongs in Attention needed, with the artifact that refutes it.

        Describing it as "tracked and incomplete" alongside work still in
        flight is the failure: a reader skims Remaining as a list of things
        that will arrive, and this is a thing that will not.
        """
        declared = assessment(
            "AC2", "No evidence found",
            [{"ref": PR_B, "kind": "pr", "state": "merged", "at": "2026-09-20T09:00:00Z"}],
            "merged",
        )
        declared["outcome"] = "confirmed-unmet"
        _, _, summary = self.both(assessments=[self._merged(), declared])
        attention = next(
            line for line in summary.splitlines() if line.startswith("- Attention needed:")
        )
        self.assertIn("is not satisfied", attention)
        self.assertIn("decide whether to reopen the work or revise the criterion", attention)
        remaining = next(line for line in summary.splitlines() if line.startswith("- Remaining:"))
        self.assertNotIn("AC2", remaining)
        self.assertIn("reopen or re-scope AC2", summary)

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
        self.assertIn("Identify and link the work covering AC2", report)
        self.assertIn("identify and link the work covering AC2", summary)
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
        result, _, summary = self.both(
            assessments=[
                assessment("AC1", "Evidence found",
                           [{"ref": PR_A, "kind": "pr", "state": "merged",
                             "at": "2026-09-18T09:00:00Z"}], "merged", downstream="confirmed"),
                assessment("AC2", "Evidence found",
                           [{"ref": PR_B, "kind": "pr", "state": "merged",
                             "at": "2026-09-19T09:00:00Z"}], "merged", downstream="confirmed"),
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
        self.assertIn("The criteria set changed (2→3), so these are not like-for-like", summary)
        self.assertIn("unverified 1→2", summary)


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
