"""Focused contracts for the shared git parser and Codex hook adapter."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "scripts" / "lib" / "git_policy.py"
ADAPTER_PATH = ROOT / "hooks" / "scripts" / "codex-adapter.py"
SPEC = importlib.util.spec_from_file_location("git_policy", POLICY_PATH)
assert SPEC and SPEC.loader
git_policy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = git_policy
SPEC.loader.exec_module(git_policy)


class GitPolicyTests(unittest.TestCase):
    def assert_allowed(self, command: str) -> None:
        decision = git_policy.validate_shell(command)
        self.assertTrue(decision.allowed, decision.reason)

    def assert_denied(self, command: str) -> None:
        decision = git_policy.validate_shell(command)
        self.assertFalse(decision.allowed, "expected shared-worktree policy denial")

    def test_allows_explicit_add_then_index_isolated_commit(self) -> None:
        self.assert_allowed(
            "git -C /work/repo add -- 'src/a file.py' tests/test_a.py && "
            "git -C /work/repo commit --only -m 'fix: safe commit' -- "
            "'src/a file.py' tests/test_a.py"
        )

    def test_rejects_broad_add_forms_even_when_chained(self) -> None:
        for command in (
            "git -C /work/repo add -A && git -C /work/repo status",
            "git -C /work/repo add -- .",
            "git -C /work/repo add -- plans/",
            "git -C /work/repo add -- '*.py'",
            f"git -C {ROOT} add -- hooks",
        ):
            with self.subTest(command=command):
                self.assert_denied(command)

    def test_rejects_destructive_and_history_rewriting_commands(self) -> None:
        for subcommand in ("stash", "reset", "restore", "checkout", "clean", "rebase", "revert"):
            with self.subTest(subcommand=subcommand):
                self.assert_denied(f"git -C /work/repo {subcommand}")
        self.assert_denied("git -C /work/repo commit --amend --no-edit")

    def test_rejects_unsafe_sync_and_bare_commits(self) -> None:
        self.assert_allowed("git -C /work/repo merge --ff-only")
        self.assert_allowed("git -C /work/repo pull --ff-only")
        for command in (
            "git -C /work/repo merge origin/main",
            "git -C /work/repo pull origin main",
            "git -C /work/repo commit -m 'bare commit'",
            "git commit --only -m x -- src/file.py",
            "git -C /work/repo commit --only -m x -- .",
        ):
            with self.subTest(command=command):
                self.assert_denied(command)

    def test_rejects_indirect_or_uninspectable_git(self) -> None:
        self.assert_denied("sh -c 'git -C /work/repo add -A'")
        self.assert_denied("git -C /work/repo add -- src/a.py | cat")

    def test_codex_adapter_is_gated_without_plugin_root(self) -> None:
        payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git add -A"}})
        env = os.environ.copy()
        env.pop("PLUGIN_ROOT", None)
        result = subprocess.run([sys.executable, str(ADAPTER_PATH)], input=payload, text=True, capture_output=True, env=env, check=True)
        self.assertEqual(result.stdout, "")

    def test_codex_adapter_emits_native_deny_shape(self) -> None:
        payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git -C /work/repo add -A"}})
        env = os.environ.copy()
        env["PLUGIN_ROOT"] = str(ROOT)
        result = subprocess.run([sys.executable, str(ADAPTER_PATH)], input=payload, text=True, capture_output=True, env=env, check=True)
        output = json.loads(result.stdout)
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
