#!/usr/bin/env python3
"""Focused contract checks for shared workflow routing and native review."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = PLUGIN_ROOT / "references/workflows/routes.json"
PROTOCOL_PATH = PLUGIN_ROOT / "references/workflows/protocol.md"
COMMAND_ADAPTER_PATH = PLUGIN_ROOT / "references/workflows/command-adapter.md"
WORK_LADDER_PATH = PLUGIN_ROOT / "references/work-ladder.md"
CURATED = {
    "dev",
    "plan",
    "harden",
    "execute",
    "review",
    "dashboard",
    "runbook",
    "diagnose",
    "ops",
}


class WorkflowRoutingContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(ROUTES_PATH.read_text(encoding="utf-8"))

    def test_all_67_commands_have_one_valid_route(self) -> None:
        command_files = {
            path.stem for path in (PLUGIN_ROOT / "commands").glob("*.md")
        }
        routes = self.catalog["commands"]
        # command files and routes must stay 1:1 (no orphan routes / no unrouted cmds)
        self.assertEqual(command_files, set(routes))
        self.assertEqual(len(command_files), len(routes))

        workflows = self.catalog["workflows"]
        self.assertEqual(CURATED, set(workflows))
        for name, spec in workflows.items():
            self.assertTrue((PLUGIN_ROOT / spec["skill"]).is_file(), name)
            self.assertTrue(spec["subcommands"], name)
            for procedure in spec["subcommands"].values():
                self.assertTrue((PLUGIN_ROOT / procedure).is_file(), procedure)

        for command, target in routes.items():
            self.assertEqual(1, target.count("."), command)
            workflow, subcommand = target.split(".")
            self.assertIn(workflow, workflows, command)
            self.assertIn(subcommand, workflows[workflow]["subcommands"], command)

    def test_meta_twins_are_true_route_aliases(self) -> None:
        routes = self.catalog["commands"]
        for command in routes:
            if command.startswith("meta-"):
                bare = command.removeprefix("meta-")
                if bare in routes:
                    self.assertEqual(routes[bare], routes[command], command)

    def test_protocol_declares_shared_contract_axes(self) -> None:
        text = PROTOCOL_PATH.read_text(encoding="utf-8")
        for marker in (
            "## Authority", "## Six stages", "## Execution and state",
            "## Host adapters and explicit commands", "## Review and closeout",
            "FOCUSED_PASS", "TASK_RED", "BASELINE_RED", "INFRA_RED",
            "BROAD_VERIFY_OMITTED", "planctl", "native host",
            "stages, workers and compaction", "repairs, verification, commits",
            "existing authority counts", "new scope or authority",
            "protected human actions", "credentials",
        ):
            self.assertIn(marker, text)
        self.assertNotIn("require an explicit confirmation even when nearby work", text)


class NativeReviewContract(unittest.TestCase):
    def test_codex_stage_completion_is_native_and_non_recursive(self) -> None:
        protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
        adapter = COMMAND_ADAPTER_PATH.read_text(encoding="utf-8")
        ladder = WORK_LADDER_PATH.read_text(encoding="utf-8")
        execute = (PLUGIN_ROOT / "commands/meta-execute.md").read_text(
            encoding="utf-8"
        )
        evaluation = (PLUGIN_ROOT / "commands/meta-eval.md").read_text(
            encoding="utf-8"
        )
        audit = (PLUGIN_ROOT / "commands/meta-audit.md").read_text(
            encoding="utf-8"
        )
        housekeeping = (PLUGIN_ROOT / "commands/housekeeping.md").read_text(
            encoding="utf-8"
        )

        for marker in (
            "## Codex efficiency boundary",
            "A stage name, section heading, example,",
            "Stage 6 uses one native Codex review",
            "Do not infer `meta-eval`, `meta-audit`, or standalone `housekeeping`",
            "Before dispatching two or more external workers",
            "existing authorization already covers that dispatch",
            "Carry scoped authorization across stages, workers, repairs",
        ):
            self.assertIn(marker, adapter)
        self.assertIn("External or\ncross-family reviewers are opt-in", protocol)
        self.assertIn("host-native configured route", ladder)
        self.assertIn("configured native", execute)
        self.assertIn("One native closing review suffices", execute)
        self.assertIn("Stage 6 does not invoke", execute)
        self.assertIn("user explicitly selects `meta-eval`", evaluation)
        self.assertIn("explicitly selects `meta-audit`", audit)
        self.assertIn("explicitly selects `housekeeping`", housekeeping)

    def test_codex_defaults_and_claude_adapter_stay_distinct(self) -> None:
        settings = json.loads(
            (PLUGIN_ROOT / "templates/settings.json").read_text(encoding="utf-8")
        )
        models = settings["meta_dev"]["codex"]["models"]
        for workflow in ("plan", "harden", "review"):
            self.assertEqual({"tier": "sol", "effort": "high"}, models[workflow])
        self.assertEqual("native", settings["meta_dev"]["codex"]["reviewer"])

        agent = (PLUGIN_ROOT / "agents/review-agent.md").read_text(encoding="utf-8")
        self.assertIn("model: opus", agent)
        self.assertIn("preserves Claude's configured reviewer behavior", agent)
        self.assertIn("Codex uses its native configured review route", agent)

    def test_review_is_report_only_without_explicit_fix_permission(self) -> None:
        skill = (
            PLUGIN_ROOT / "workflow-skills/code-review-protocol/SKILL.md"
        ).read_text(encoding="utf-8")
        routing = (
            PLUGIN_ROOT
            / "workflow-skills/code-review-protocol/references/verdict-routing.md"
        ).read_text(encoding="utf-8")
        evaluation = (PLUGIN_ROOT / "commands/meta-eval.md").read_text(
            encoding="utf-8"
        )

        for text in (skill, routing, evaluation):
            self.assertIn("report-only", text)
            self.assertIn("--fix", text)
        self.assertIn("does not authorize edits or a commit", skill)
        self.assertIn("Do not commit merely", routing)
        self.assertIn("Do not dispatch a", evaluation)
        self.assertNotIn("Auto-fix trivials", evaluation)
        self.assertNotIn("Auto-fix and commit", routing)

    def test_structured_verdict_and_native_phase_review_remain(self) -> None:
        skill = (
            PLUGIN_ROOT / "workflow-skills/code-review-protocol/SKILL.md"
        ).read_text(encoding="utf-8")
        loop = (
            PLUGIN_ROOT
            / "workflow-skills/agentic-exec-loop/references/loop-protocol.md"
        ).read_text(encoding="utf-8")
        for verdict in ("PASS", "CONDITIONAL_PASS", "FAIL"):
            self.assertIn(verdict, skill)
        self.assertIn("commands/meta-execute.md", loop)
        self.assertIn("final planctl PASS", loop)
        self.assertNotIn("Reviewer is ALWAYS the Opus", loop)
        self.assertNotIn("single Opus code-review checkpoint", loop)

    def test_curated_codex_skills_load_shared_protocol(self) -> None:
        workflows = json.loads(ROUTES_PATH.read_text())["workflows"]
        for name in CURATED - {"plan", "ops"}:
            text = (PLUGIN_ROOT / workflows[name]["skill"]).read_text()
            # Generated command adapters load the protocol transitively;
            # helper skills may reference it directly. Test real route paths.
            if "../../commands/meta-execute.md" in text:
                text += (PLUGIN_ROOT / "commands/meta-execute.md").read_text()
            if "references/workflows/protocol.md" not in text:
                self.assertIn("../../references/workflows/command-adapter.md", text, name)
        self.assertIn("references/workflows/protocol.md", COMMAND_ADAPTER_PATH.read_text())


class ReviewBatchEvidence(unittest.TestCase):
    script = PLUGIN_ROOT / "scripts/review-batch-render.py"

    def run_renderer(self, payload, *args):
        return subprocess.run(
            [sys.executable, str(self.script), *args], input=json.dumps(payload),
            text=True, capture_output=True, check=False,
        )

    def test_complete_batch_renders_every_finding_and_exact_critical_count(self) -> None:
        issues = [
            {"severity": "high" if n == 1 else "medium", "file": "src/flow.py",
             "line": n, "title": f"Issue {n}", "description": "Observed impact",
             "failure_path": "request → transport → consumer failure",
             "violated_requirement": "Contract C1", "missing_evidence": "Focused refusal check",
             "suggested_fix": "Repair consumer"}
            for n in range(1, 5)
        ]
        result = self.run_renderer({"reviews": [
            {"target": "slice A", "verdict": "FAIL", "summary": "Four defects",
             "confidence": 0.9, "blast_radius": "module",
             "dimensions": {name: "NEEDS_FIX" for name in
                            ("correctness", "safety", "patterns", "coverage", "scope")},
             "issues": issues},
        ]})
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Critical issues: 1", result.stdout)
        for n in range(1, 5):
            self.assertIn(f"Issue {n} — src/flow.py:{n}", result.stdout)
        self.assertIn("Failure path: request → transport → consumer failure", result.stdout)

    def test_single_valid_pass_and_incomplete_pass_or_finding_refused(self) -> None:
        verdict = {"verdict": "PASS", "summary": "All declared scope inspected",
                   "confidence": 0.9, "blast_radius": "file",
                   "dimensions": {name: "PASS" for name in
                                  ("correctness", "safety", "patterns", "coverage", "scope")},
                   "issues": []}
        self.assertEqual(0, self.run_renderer(verdict, "--validate-only").returncode)
        verdict["dimensions"]["coverage"] = "NEEDS_REVIEW"
        rejected = self.run_renderer(verdict, "--validate-only")
        self.assertEqual(2, rejected.returncode)
        self.assertIn("PASS requires", rejected.stderr)
        verdict["verdict"] = "FAIL"
        verdict["issues"] = [{"severity": "high", "file": "src/flow.py", "line": 5,
                              "title": "Missing consumer guard", "description": "Reachable bad state",
                              "suggested_fix": "Guard consumer"}]
        rejected = self.run_renderer(verdict, "--validate-only")
        self.assertEqual(2, rejected.returncode)
        self.assertIn("failure_path is required", rejected.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
