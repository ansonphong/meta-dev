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

PRODUCTION_CODEX_BASH = {
    "hook_event_name": "PreToolUse",
    "tool_name": "Bash",
    "tool_input": {
        "cmd": "git -C /work/repo add -A",
        "yield_time_ms": 10000,
        "max_output_tokens": 2000,
    },
}


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
        self.assert_denied("g=git; $g -C /work/repo add -- src/a.py")

    def test_allows_only_proven_read_only_branch_config_and_remote_forms(self) -> None:
        for command in (
            "git -C /work/repo status --short",
            "git -C /work/repo diff --stat",
            "git -C /work/repo log -1 --oneline",
            "git -C /work/repo branch --show-current",
            "git -C /work/repo config --get remote.origin.url",
            "git -C /work/repo remote get-url origin",
        ):
            with self.subTest(command=command):
                self.assert_allowed(command)
        for command in (
            "git -C /work/repo branch -D old-topic",
            "git -C /work/repo config user.name changed",
            "git -C /work/repo remote set-url origin https://invalid.example/repo.git",
        ):
            with self.subTest(command=command):
                self.assert_denied(command)

    def test_newlines_and_path_qualified_git_are_governed(self) -> None:
        self.assert_allowed("/usr/bin/git -C /work/repo status\ngit -C /work/repo status")
        self.assert_denied("echo safe\n/usr/bin/git -C /work/repo add -A")
        self.assert_denied("/opt/git/bin/git -C /work/repo commit -m unsafe")

    def test_codex_adapter_is_gated_without_plugin_root(self) -> None:
        payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git add -A"}})
        env = os.environ.copy()
        env.pop("PLUGIN_ROOT", None)
        result = subprocess.run([sys.executable, str(ADAPTER_PATH)], input=payload, text=True, capture_output=True, env=env, check=True)
        self.assertEqual(result.stdout, "")

    def test_codex_adapter_emits_native_deny_shape(self) -> None:
        payload = json.dumps(PRODUCTION_CODEX_BASH)
        env = os.environ.copy()
        env["PLUGIN_ROOT"] = str(ROOT)
        result = subprocess.run([sys.executable, str(ADAPTER_PATH)], input=payload, text=True, capture_output=True, env=env, check=True)
        output = json.loads(result.stdout)
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_codex_adapter_supports_legacy_command_and_denies_missing_or_non_string_input(self) -> None:
        env = os.environ.copy()
        env["PLUGIN_ROOT"] = str(ROOT)
        payloads = (
            {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git -C /work/repo add -A"}},
            {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {}},
            {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"cmd": ["git", "status"]}},
            {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": 7}},
            {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": None},
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                result = subprocess.run(
                    [sys.executable, str(ADAPTER_PATH)], input=json.dumps(payload), text=True,
                    capture_output=True, env=env, check=True,
                )
                output = json.loads(result.stdout)
                self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "PreToolUse")
                self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
