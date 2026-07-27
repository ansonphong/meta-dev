#!/usr/bin/env python3
"""Focused contract checks for shared workflow routing and native review."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = PLUGIN_ROOT / "references/workflows/routes.json"
PROTOCOL_PATH = PLUGIN_ROOT / "references/workflows/protocol.md"
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
            "## Permission boundary",
            "## Six stages",
            "## Artifacts",
            "## Result states",
            "## Host capability adapters",
            "FOCUSED_PASS",
            "TASK_RED",
            "BASELINE_RED",
            "INFRA_RED",
            "BROAD_VERIFY_OMITTED",
            "PASS",
            "CONDITIONAL_PASS",
            "FAIL",
            "gpt-5.6-sol",
            "External/headless reviewers run only",
        ):
            self.assertIn(marker, text)


class NativeReviewContract(unittest.TestCase):
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
            self.assertIn(verdict, loop)
        self.assertIn("Reviewer**: native to the host by default", loop)
        self.assertNotIn("Reviewer is ALWAYS the Opus", loop)
        self.assertNotIn("single Opus code-review checkpoint", loop)

    def test_curated_codex_skills_load_shared_protocol(self) -> None:
        for name in CURATED - {"plan", "ops"}:
            text = (
                PLUGIN_ROOT / f"skills/{name}/SKILL.md"
            ).read_text(encoding="utf-8")
            self.assertIn("../../references/workflows/protocol.md", text, name)
            self.assertIn("host-neutral", text, name)
            self.assertIn("slash-command", text, name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
