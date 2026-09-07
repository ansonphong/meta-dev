#!/usr/bin/env python3
"""Classify a verification command without executing it.

The execution harness uses this as a mechanical scope gate.  Classification is
intentionally conservative: commands are focused only when a known test runner
names a test file, and checks are scoped only when they name an allowed path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


_SHELL_OPERATORS = {";", "&&", "||", "|", "&"}
_PYTEST_NAMES = {"pytest", "py.test", "pytest.exe", "py.test.exe"}
_JS_TEST_RUNNERS = {"vitest", "vitest.exe", "jest", "jest.exe"}
_PACKAGE_MANAGERS = {"npm", "npm.cmd", "pnpm", "pnpm.cmd", "yarn", "yarn.cmd", "bun"}
_PACKAGE_EXECUTORS = {"npx", "npx.cmd", "bunx"}
_BROAD_PACKAGE_ACTIONS = {"build", "check", "test"}
_JS_TEST_FILE_RE = re.compile(
    r"(?:^|/)(?:[^/]+\.(?:test|spec)\.[cm]?[jt]sx?|__tests__/[^/]+\.[cm]?[jt]sx?)$",
    re.IGNORECASE,
)
_MANUAL_RE = re.compile(
    r"\bmanual(?:ly)?\b|\bby[ -](?:eye|hand)\b|\bgpu\b|\bvisible[ -]app\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Classification:
    category: str
    reason: str

    def as_json(self) -> dict[str, str]:
        return {"class": self.category, "reason": self.reason}


def _basename(token: str) -> str:
    return Path(token).name.lower()


def _tokenize(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def _segments(tokens: Sequence[str]) -> list[list[str]]:
    result: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in _SHELL_OPERATORS or (token and set(token) <= set(";&|")):
            if not current:
                raise ValueError("empty command segment")
            result.append(current)
            current = []
        else:
            current.append(token)
    if not current:
        raise ValueError("command ends with a shell operator")
    result.append(current)
    return result


def _strip_wrappers(tokens: Sequence[str]) -> list[str]:
    """Remove common non-semantic launch wrappers from one command segment."""
    remaining = list(tokens)
    while remaining:
        name = _basename(remaining[0])
        if name == "env":
            remaining = remaining[1:]
            while remaining and "=" in remaining[0] and not remaining[0].startswith("-"):
                remaining = remaining[1:]
            continue
        if name in {"uv", "uvx"} and len(remaining) > 1 and remaining[1] == "run":
            remaining = remaining[2:]
            continue
        break
    return remaining


def _runner(tokens: Sequence[str]) -> tuple[str | None, list[str]]:
    """Return a recognized test runner and its arguments."""
    tokens = _strip_wrappers(tokens)
    if not tokens:
        return None, []

    first = _basename(tokens[0])
    if first in _PYTEST_NAMES | _JS_TEST_RUNNERS:
        return first, list(tokens[1:])

    if first in {"python", "python3", "python.exe", "python3.exe"}:
        if len(tokens) >= 3 and tokens[1] == "-m" and _basename(tokens[2]) in _PYTEST_NAMES:
            return _basename(tokens[2]), list(tokens[3:])

    if first in _PACKAGE_EXECUTORS and len(tokens) >= 2:
        candidate = _basename(tokens[1])
        if candidate in _JS_TEST_RUNNERS:
            return candidate, list(tokens[2:])

    if first in _PACKAGE_MANAGERS and len(tokens) >= 3 and tokens[1] in {"exec", "x", "dlx"}:
        candidate = _basename(tokens[2])
        if candidate in _JS_TEST_RUNNERS:
            return candidate, list(tokens[3:])

    return None, []


def _path_candidate(token: str) -> str:
    # Pytest node IDs decorate the path; punctuation here is shell syntax or a
    # common delimiter rather than part of an allowed verification path.
    return token.split("::", 1)[0].rstrip(",:")


def _normalized_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.normpath(path)))


def _references_allowed_path(tokens: Iterable[str], allowed_paths: Sequence[str]) -> bool:
    allowed = [_normalized_path(path) for path in allowed_paths]
    for token in tokens:
        if token.startswith("-"):
            continue
        candidate_text = _path_candidate(token)
        if not candidate_text:
            continue
        candidate = _normalized_path(candidate_text)
        for permitted in allowed:
            if candidate == permitted or candidate.startswith(permitted + os.sep):
                return True
    return False


def _all_paths_allowed(paths: Sequence[str], allowed_paths: Sequence[str]) -> bool:
    return bool(paths) and all(_references_allowed_path([path], allowed_paths) for path in paths)


def _positionals(args: Sequence[str], value_options: set[str]) -> list[str]:
    """Extract operands for known command families, not their launcher paths."""
    result = []
    skip = False
    literal = False
    for arg in args:
        if skip:
            skip = False
        elif arg == "--" and not literal:
            literal = True
        elif not literal and arg in value_options:
            skip = True
        elif literal or not arg.startswith("-"):
            result.append(arg)
    return result


def _test_targets(runner: str, args: Sequence[str]) -> list[str]:
    options = {
        "-c", "-o", "-p", "-m", "--override-ini", "--confcutdir", "--rootdir",
        "--basetemp", "--junitxml", "--tb", "--maxfail", "--color", "--capture",
        "--durations", "--import-mode", "--config", "--reporter", "--pool",
        "--maxWorkers", "--minWorkers", "--testTimeout", "--testNamePattern", "-t",
    }
    targets = _positionals(args, options)
    if runner in _JS_TEST_RUNNERS and targets and targets[0] in {"run", "watch"}:
        targets = targets[1:]
    return targets


def _package_action(tokens: Sequence[str]) -> str | None:
    tokens = _strip_wrappers(tokens)
    if not tokens or _basename(tokens[0]) not in _PACKAGE_MANAGERS:
        return None
    args = list(tokens[1:])
    if args and args[0] == "run":
        args = args[1:]
    for arg in args:
        if arg == "--":
            continue
        if not arg.startswith("-"):
            return arg.lower()
    return None


def _is_project_tsc(tokens: Sequence[str]) -> bool:
    tokens = _strip_wrappers(tokens)
    if not tokens:
        return False
    first = _basename(tokens[0])
    if first in {"tsc", "tsc.cmd", "svelte-check", "svelte-check.cmd"}:
        return True
    if first in _PACKAGE_EXECUTORS and len(tokens) >= 2:
        return _basename(tokens[1]) in {"tsc", "tsc.cmd", "svelte-check", "svelte-check.cmd"}
    if first in _PACKAGE_MANAGERS and len(tokens) >= 3 and tokens[1] in {"exec", "x", "dlx"}:
        return _basename(tokens[2]) in {"tsc", "tsc.cmd", "svelte-check", "svelte-check.cmd"}
    return False


def _is_scoped_check(tokens: Sequence[str], allowed_paths: Sequence[str]) -> bool:
    tokens = _strip_wrappers(tokens)
    if not tokens:
        return False
    first = _basename(tokens[0])
    if first in {"bash", "sh"} and "-n" in tokens[1:]:
        return _all_paths_allowed(_positionals(tokens[1:], set()), allowed_paths)
    if first in {"grep", "egrep", "fgrep", "rg", "ripgrep"}:
        # Pattern arguments are not inspected files; every file operand is.
        operands = _positionals(tokens[1:], {"-e", "--regexp", "-g", "--glob", "-t", "--type", "-m", "--max-count"})
        explicit_pattern = any(token in {"-e", "--regexp", "-f", "--file"} or token.startswith(("--regexp=", "--file=")) for token in tokens[1:])
        paths = operands if explicit_pattern else operands[1:]
        paths += [token.split("=", 1)[1] for token in tokens[1:] if token.startswith("--file=")]
        return _all_paths_allowed(paths, allowed_paths)
    if first == "shellcheck":
        return _all_paths_allowed(_positionals(tokens[1:], {"-s", "--shell", "-e", "--exclude", "-f", "--format", "-S", "--severity"}), allowed_paths)
    if first in {"python", "python3", "node", "ruby", "perl"} and len(tokens) > 3 and tokens[2] == "check" and not tokens[1].startswith("-"):
        # python scripts/tool.py check <targets>: tool.py is an executable,
        # not a verification target that needs to be owned by this task.
        operands = tokens[3:]
        return _all_paths_allowed(_positionals(operands, set()), allowed_paths)
    return first.endswith("check") and _all_paths_allowed(_positionals(tokens[1:], set()), allowed_paths)


def _classify_segment(tokens: Sequence[str]) -> Classification:
    runner, args = _runner(tokens)
    if runner in _PYTEST_NAMES:
        targets = _test_targets(runner, args)
        if "-k" in args or any(arg.startswith("-k=") for arg in args):
            return Classification("broad", "pytest -k is forbidden; name exact test files/nodes")
        if targets and all(_path_candidate(arg).lower().endswith(".py") for arg in targets):
            return Classification("focused", "pytest names an explicit Python test file")
        return Classification("broad", "pytest must name only explicit Python test files/nodes")
    if runner in _JS_TEST_RUNNERS:
        targets = _test_targets(runner, args)
        if targets and all(_JS_TEST_FILE_RE.search(_path_candidate(arg).replace("\\", "/")) for arg in targets):
            return Classification("focused", f"{runner.removesuffix('.exe')} names an explicit test file")
        return Classification("broad", f"{runner.removesuffix('.exe')} does not name an explicit test file")

    action = _package_action(tokens)
    if action in _BROAD_PACKAGE_ACTIONS:
        return Classification("broad", f"package-wide {action} command")
    if _is_project_tsc(tokens):
        return Classification("broad", "project-wide type or Svelte check")

    command_text = shlex.join(tokens)
    if tokens and tokens[0].lower() in {"manual", "manually", "verify", "check", "run", "launch", "inspect"} and _MANUAL_RE.search(command_text):
        return Classification("manual", "verification requires manual, GPU, or visible-app work")

    return Classification("unscoped", "command is not a recognized focused verification")


def classify(command: str, allowed_paths: Sequence[str]) -> Classification:
    if not command.strip():
        raise ValueError("command must not be empty")
    tokens = _tokenize(command)
    if not tokens:
        raise ValueError("command must not be empty")
    segments = _segments(tokens)

    classified: list[Classification] = []
    for segment in segments:
        initial = _classify_segment(segment)
        runner, runner_args = _runner(segment)
        if initial.category == "focused" and not _all_paths_allowed(_test_targets(runner, runner_args), allowed_paths):
            initial = Classification(
                "unscoped",
                "one or more named test files are outside the task's allowed paths",
            )
        if initial.category == "unscoped" and _is_scoped_check(segment, allowed_paths):
            initial = Classification("scoped_check", "check explicitly references an allowed path")
        classified.append(initial)

    broad = next((item for item in classified if item.category == "broad"), None)
    if broad:
        reason = broad.reason
        if len(classified) > 1:
            reason = f"compound command contains broad segment: {reason}"
        return Classification("broad", reason)

    unscoped = next((item for item in classified if item.category == "unscoped"), None)
    if unscoped:
        reason = unscoped.reason
        if len(classified) > 1:
            reason = f"compound command contains unscoped segment: {reason}"
        return Classification("unscoped", reason)

    manual = next((item for item in classified if item.category == "manual"), None)
    if manual:
        return manual

    focused = next((item for item in classified if item.category == "focused"), None)
    if focused:
        return Classification("focused", "all command segments are focused or scoped checks")
    return Classification("scoped_check", "all command segments are allowed-path checks")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify-scope.py",
        description="Classify a verification command without executing it.",
    )
    parser.add_argument("--command", required=True, help="shell command to classify")
    parser.add_argument(
        "--allowed-path",
        action="append",
        nargs="+",
        required=True,
        metavar="PATH",
        help="path the verification command may inspect (repeatable)",
    )
    args = parser.parse_args(argv)
    allowed_paths = [path for group in args.allowed_path for path in group]

    try:
        result = classify(args.command, allowed_paths)
    except (TypeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2
    except Exception as exc:  # pragma: no cover - last-resort CLI contract
        print(json.dumps({"error": f"internal failure: {exc}"}, sort_keys=True))
        return 1

    print(json.dumps(result.as_json(), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
