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
ADAPTER_SPEC = importlib.util.spec_from_file_location("codex_adapter", ADAPTER_PATH)
assert ADAPTER_SPEC and ADAPTER_SPEC.loader
codex_adapter = importlib.util.module_from_spec(ADAPTER_SPEC)
ADAPTER_SPEC.loader.exec_module(codex_adapter)

PRODUCTION_CODEX_BASH = {
    "hook_event_name": "PreToolUse",
    "tool_name": "Bash",
    "tool_input": {
        "cmd": "git -C /work/repo add -A",
        "yield_time_ms": 10000,
        "max_output_tokens": 2000,
    },
}


def codex_env(*, plugin_root: bool = True) -> dict[str, str]:
    """Build the environment a real Codex hook runs in.

    ``codex-adapter`` deliberately no-ops whenever Claude Code's markers are
    present, so a suite run from inside a Claude session would otherwise get
    empty stdout from every adapter test and fail decoding it as JSON — while
    the one gating test passed for the wrong reason.  Drop the markers so
    these cases assert Codex behavior no matter which host runs the suite.
    """
    env = os.environ.copy()
    for marker in codex_adapter.CLAUDE_MARKERS:
        env.pop(marker, None)
    env.pop("META_DEV_GIT_POLICY_IN_CLAUDE", None)
    if plugin_root:
        env["PLUGIN_ROOT"] = str(ROOT)
    else:
        env.pop("PLUGIN_ROOT", None)
    return env


class GitPolicyTests(unittest.TestCase):
    def assert_allowed(self, command: str) -> None:
        decision = git_policy.validate_shell(command)
        self.assertTrue(decision.allowed, decision.reason)

    def assert_denied(self, command: str) -> None:
        decision = git_policy.validate_shell(command)
        self.assertFalse(decision.allowed, "expected shared-worktree policy denial")

    def test_allows_ordinary_git_work_with_no_required_flag_shape(self) -> None:
        """The whole point of the inversion: normal work is not policed.

        Every one of these was denied by the old allowlist — several of them
        (``merge --ff-only <ref>``, ``config --list``) are the exact commands
        CLAUDE.md tells an agent to run.
        """
        for command in (
            "git -C /work/repo merge --ff-only origin/main",
            "git -C /work/repo pull --ff-only origin main",
            "git fetch origin master",
            "git -C /work/repo push origin main",
            "git push --force-with-lease origin topic",
            "git -C /work/repo config --list",
            "git cat-file -p HEAD",
            "git grep -n TODO",
            "git worktree list",
            "git for-each-ref --format='%(refname)'",
            "git branch -a",
            "git branch -d merged-topic",
            "git switch -c feature/x",
            "git checkout main",
            "git checkout -- src/one_file.py",
            "git restore --staged src/a.py",
            "git commit -m 'an ordinary commit'",
            "git commit -m 'msg' -- src/a.py",
            "git add src/a.py src/b.py",
            "git apply /tmp/patch.diff",
            "git cherry-pick abc123",
            "git revert abc123",
            "git tag -a v1 -m v1",
            "git stash list",
            "git rebase --abort",
            "git merge --abort",
            "git clean -n",
            "git reset HEAD~1",
            "git reset --soft HEAD~1",
            "git bisect start",
            "git submodule update --init",
            "git remote set-url origin git@example.com:x/y.git",
            "git gc --prune=never",
            "git worktree remove wt-1",
        ):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_allows_the_charter_add_then_isolated_commit_form(self) -> None:
        """Still the preferred shape — now encouraged by doctrine, not enforced here."""
        self.assert_allowed(
            "git -C /work/repo add -- 'src/a file.py' tests/test_a.py && "
            "git -C /work/repo commit --only -m 'fix: safe commit' -- "
            "'src/a file.py' tests/test_a.py"
        )

    def test_rejects_tree_wide_staging_even_when_chained(self) -> None:
        """The 2026-07-05 commit-sweep: staging that reaches unnamed files."""
        for command in (
            "git -C /work/repo add -A && git -C /work/repo status",
            "git -C /work/repo add -u",
            "git -C /work/repo add .",
            "git -C /work/repo add -- .",
            "git -C /work/repo add -- plans/",
            "git -C /work/repo commit -a -m sweep",
            "git -C /work/repo commit -am sweep",
        ):
            with self.subTest(command=command):
                self.assert_denied(command)

    def test_rejects_worktree_and_history_destroyers(self) -> None:
        for command in (
            "git -C /work/repo reset --hard",
            "git -C /work/repo reset --hard HEAD~3",
            "git -C /work/repo reset --merge",
            "git -C /work/repo stash",
            "git -C /work/repo stash pop",
            "git -C /work/repo stash drop",
            "git -C /work/repo checkout .",
            "git -C /work/repo checkout -- .",
            "git -C /work/repo checkout -- src/",
            "git -C /work/repo restore .",
            "git -C /work/repo restore",
            "git -C /work/repo clean -fd",
            "git -C /work/repo commit --amend --no-edit",
            "git -C /work/repo branch -D old-topic",
            "git -C /work/repo filter-branch --tree-filter true",
            "git -C /work/repo reflog expire --expire=now --all",
            "git -C /work/repo update-ref -d refs/heads/x",
            "git -C /work/repo gc --prune=now",
            "git -C /work/repo worktree remove --force wt-1",
        ):
            with self.subTest(command=command):
                self.assert_denied(command)

    def test_rejects_unsafe_sync_and_force_push(self) -> None:
        self.assert_allowed("git -C /work/repo merge --ff-only")
        self.assert_allowed("git -C /work/repo pull --ff-only")
        for command in (
            "git -C /work/repo merge origin/main",
            "git -C /work/repo pull origin main",
            "git -C /work/repo pull --rebase",
            "git -C /work/repo rebase origin/main",
            "git -C /work/repo push --force origin main",
            "git -C /work/repo push -f",
            "git -C /work/repo push --delete origin topic",
            "git -C /work/repo push --mirror",
        ):
            with self.subTest(command=command):
                self.assert_denied(command)

    def test_uninspectable_commands_are_scanned_not_refused(self) -> None:
        """Refusing what it could not parse is what made the old guard sabotage.

        A wrapper the splitter cannot open is text-scanned for the destructive
        forms instead: the sweep still dies, ordinary work still runs.
        """
        for command in (
            "sh -c 'git -C /work/repo add -- src/a.py'",
            "bash -c 'git status && git log --oneline -3'",
            "g=git; $g status",
            'bash -c "$possibly_git_command"',
            'eval "$possibly_git_command"',
            "bash -c 'echo $(date +%s)'",
        ):
            with self.subTest(command=command):
                self.assert_allowed(command)
        for command in (
            "sh -c 'git -C /work/repo add -A'",
            'g=git; maybe="$g -C /work/repo add -A"; export maybe; bash -c \'$maybe\'',
            "env MODE=safe $g -C /work/repo add -A",
            'printf "%s" "$(git -C /work/repo add -A)"',
            "bash -c 'git clean -fd'",
        ):
            with self.subTest(command=command):
                self.assert_denied(command)

    def test_pipelines_are_split_not_refused(self) -> None:
        """A pipeline hides nothing — split it and inspect every segment."""
        for command in (
            "ls foo | head -5",
            "curl -s https://example.com -o out.json || true",
            "python3 tool.py 2>&1 | tail -20",
            "echo one & echo two",
            "git -C /work/repo add -- src/a.py | cat",
            "git -C /work/repo status | grep -c modified &",
            "git -C /work/repo log --oneline | head -5",
        ):
            with self.subTest(command=command):
                self.assert_allowed(command)
        for command in (
            "ls foo | git -C /work/repo stash",
            "echo hi || git -C /work/repo add -A",
            "git -C /work/repo rebase origin/main | cat",
            "true & git -C /work/repo reset --hard",
        ):
            with self.subTest(command=command):
                self.assert_denied(command)

    def test_git_free_commands_are_not_this_policys_business(self) -> None:
        self.assert_allowed("diff <(ls dir_a) <(ls dir_b)")
        self.assert_allowed("diff <(git -C /work/repo stash list) other.txt")
        self.assert_denied("diff <(ls a) <(git -C /work/repo clean -fd)")

    def test_allows_safe_expansions_outside_executable_position(self) -> None:
        for command in (
            'echo "$HOME"',
            "printf '%s' \"$value\"",
            "printf '%s' \"$(date +%s)\"",
            """echo "it's $HOME" """,
            "echo '${literal}'",
            "env LABEL=\"$HOME\" printf '%s' \"$value\"",
        ):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_read_only_and_mutating_metadata_commands_all_run(self) -> None:
        """Read-only forms were never the risk; neither is changing your own config."""
        for command in (
            "git -C /work/repo status --short",
            "git -C /work/repo diff --stat",
            "git -C /work/repo log -1 --oneline",
            "git -C /work/repo branch --show-current",
            "git -C /work/repo config --get remote.origin.url",
            "git -C /work/repo config user.name changed",
            "git -C /work/repo remote get-url origin",
            "git -C /work/repo remote set-url origin https://example.com/repo.git",
        ):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_newlines_and_path_qualified_git_are_governed(self) -> None:
        self.assert_allowed("/usr/bin/git -C /work/repo status\ngit -C /work/repo status")
        self.assert_allowed("/opt/git/bin/git -C /work/repo commit -m ordinary")
        self.assert_denied("echo safe\n/usr/bin/git -C /work/repo add -A")

    def test_non_git_destroyers_are_checked_by_executable_not_by_text(self) -> None:
        """Prose describing a destructive command is prose.

        The hook used to grep the raw string, so a commit message explaining
        why ``rm -rf`` is blocked was itself blocked. The rules now read the
        executable of each simple command.
        """
        for command in (
            "git commit -m 'docs: explain why rm -rf and DROP TABLE are blocked'",
            "grep -rn 'DROP TABLE' migrations/",
            "echo 'DROP TABLE users;' > migration_notes.txt",
            "rm -rf node_modules",
            "rm -rf /tmp/scratch/dir",
            "rm -rf ./build",
            "rm src/old_file.py",
        ):
            with self.subTest(command=command):
                self.assertTrue(git_policy.validate_destructive(command)[0].allowed, command)
        for command, category in (
            ("rm -rf /srv/production-data", "rm_rf_non_temp"),
            ("rm -r /srv/data", "rm_rf_non_temp"),
            ("rm -f .git/index", "rm_git_index"),
            ("psql -c 'DROP TABLE users'", "drop_table"),
            ("echo 'TRUNCATE TABLE orders;' | psql mydb", "drop_table"),
            ("DROP TABLE users;", "drop_table"),
        ):
            with self.subTest(command=command):
                decision, seen = git_policy.validate_destructive(command)
                self.assertFalse(decision.allowed, command)
                self.assertEqual(seen, category)

    def test_codex_adapter_is_gated_without_plugin_root(self) -> None:
        payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git add -A"}})
        result = subprocess.run([sys.executable, str(ADAPTER_PATH)], input=payload, text=True, capture_output=True, env=codex_env(plugin_root=False), check=True)
        self.assertEqual(result.stdout, "")

    def test_codex_adapter_is_gated_inside_a_claude_session(self) -> None:
        """Claude runs its own guard chain — the Codex policy must not layer on it."""
        payload = json.dumps(PRODUCTION_CODEX_BASH)
        for marker in codex_adapter.CLAUDE_MARKERS:
            with self.subTest(marker=marker):
                env = codex_env()
                env[marker] = "1"
                result = subprocess.run(
                    [sys.executable, str(ADAPTER_PATH)], input=payload, text=True,
                    capture_output=True, env=env, check=True,
                )
                self.assertEqual(result.stdout, "")

        # The opt-in override re-enables it deliberately.
        env = codex_env()
        env["CLAUDECODE"] = "1"
        env["META_DEV_GIT_POLICY_IN_CLAUDE"] = "1"
        result = subprocess.run(
            [sys.executable, str(ADAPTER_PATH)], input=payload, text=True,
            capture_output=True, env=env, check=True,
        )
        self.assertEqual(
            json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny",
        )

    def test_codex_adapter_emits_native_deny_shape(self) -> None:
        payload = json.dumps(PRODUCTION_CODEX_BASH)
        result = subprocess.run([sys.executable, str(ADAPTER_PATH)], input=payload, text=True, capture_output=True, env=codex_env(), check=True)
        output = json.loads(result.stdout)
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_codex_adapter_approves_safe_command_without_stdout(self) -> None:
        payload = json.loads(json.dumps(PRODUCTION_CODEX_BASH))
        payload["tool_input"]["cmd"] = "git -C /work/repo status --short"

        result = subprocess.run(
            [sys.executable, str(ADAPTER_PATH)], input=json.dumps(payload),
            text=True, capture_output=True, env=codex_env(), check=True,
        )

        self.assertEqual(result.stdout, "")

    def test_codex_adapter_preserves_warning_without_bare_allow(self) -> None:
        output = codex_adapter.normalize_legacy_pretool_output(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            },
            "systemMessage": "meta-guard WARN: inspect this command",
        }))

        self.assertEqual(output, {
            "systemMessage": "meta-guard WARN: inspect this command",
        })

    def test_codex_adapter_production_cmd_denies_dynamic_git_bypasses(self) -> None:
        env = codex_env()
        # A dynamic *pathspec* (`add -- "$path"`) is no longer denied: staging is
        # additive and recoverable, and refusing every variable path broke
        # ordinary scripted commits. What still dies is a hidden tree-wide sweep.
        commands = (
            'g=git; maybe="$g -C /work/repo add -A"; export maybe; bash -c \'$maybe\'',
            'flags="-A"; bash -c "git -C /work/repo add -A"',
            "bash -c 'git -C /work/repo reset --hard'",
        )
        for command in commands:
            with self.subTest(command=command):
                payload = json.loads(json.dumps(PRODUCTION_CODEX_BASH))
                payload["tool_input"]["cmd"] = command
                result = subprocess.run(
                    [sys.executable, str(ADAPTER_PATH)], input=json.dumps(payload),
                    text=True, capture_output=True, env=env, check=True,
                )
                output = json.loads(result.stdout)
                self.assertEqual(
                    output["hookSpecificOutput"]["permissionDecision"], "deny",
                )

    def test_codex_adapter_normalizes_production_cmd_for_legacy_destructive_guard(self) -> None:
        payload = json.loads(json.dumps(PRODUCTION_CODEX_BASH))
        payload["tool_input"]["cmd"] = "rm -rf /srv/production-data"
        payload["tool_input"]["custom_field"] = {"preserved": True}
        normalized = json.loads(codex_adapter.normalized_bash_payload(
            payload, payload["tool_input"]["cmd"],
        ))
        self.assertEqual(normalized["tool_input"]["command"], payload["tool_input"]["cmd"])
        self.assertEqual(normalized["tool_input"]["custom_field"], {"preserved": True})
        self.assertEqual(normalized["tool_input"]["yield_time_ms"], 10000)
        self.assertNotIn("command", payload["tool_input"])

        result = subprocess.run(
            [sys.executable, str(ADAPTER_PATH)], input=json.dumps(payload), text=True,
            capture_output=True, env=codex_env(), check=True,
        )

        output = json.loads(result.stdout)
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("Recursive delete", output["hookSpecificOutput"]["permissionDecisionReason"])

    def test_codex_adapter_supports_legacy_command_and_denies_missing_or_non_string_input(self) -> None:
        env = codex_env()
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
