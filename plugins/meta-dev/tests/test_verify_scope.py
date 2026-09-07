"""CLI coverage for the non-executing verification scope classifier."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify-scope.py"


def run_classifier(command: str, *allowed_paths: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    argv = [sys.executable, str(SCRIPT), "--command", command]
    for path in allowed_paths or ("plugins/meta-dev/tests/test_verify_scope.py",):
        argv.extend(["--allowed-path", path])
    result = subprocess.run(argv, capture_output=True, check=False, text=True)
    payload = json.loads(result.stdout)
    return result, payload


@pytest.mark.parametrize(
    ("command", "allowed_path", "expected"),
    [
        (
            "pytest plugins/meta-dev/tests/test_verify_scope.py -q",
            "plugins/meta-dev/tests/test_verify_scope.py",
            "focused",
        ),
        (
            "python3 -m pytest plugins/meta-dev/tests/test_verify_scope.py::test_focused -q",
            "plugins/meta-dev/tests/test_verify_scope.py",
            "focused",
        ),
        ("npx vitest run src/lib/widget.test.ts", "src/lib/widget.test.ts", "focused"),
        ("pnpm exec jest frontend/widget.spec.js", "frontend/widget.spec.js", "focused"),
    ],
)
def test_explicit_test_files_are_focused(command: str, allowed_path: str, expected: str):
    result, payload = run_classifier(command, allowed_path)
    assert result.returncode == 0
    assert payload["class"] == expected


def test_named_test_file_outside_allowed_paths_is_unscoped():
    result, payload = run_classifier(
        "pytest plugins/meta-dev/tests/test_verify_scope.py -q",
        "plugins/meta-dev/tests/test_other_feature.py",
    )
    assert result.returncode == 0
    assert payload["class"] == "unscoped"
    assert "outside" in payload["reason"]


@pytest.mark.parametrize("command", [
    "pytest tests/test_owned.py tests/test_other.py -q",
    "npx vitest run src/owned.test.ts src/other.test.ts",
    "bash -n src/owned.test.ts scripts/other.sh",
    "rg pattern src/owned.test.ts other/private.txt",
    "shellcheck scripts/owned.sh scripts/other.sh",
    "python3 scripts/checker.py check scripts/owned.sh scripts/other.sh",
    "rg -f other/patterns.txt src/owned.test.ts",
    "rg --file=other/patterns.txt src/owned.test.ts",
    "rm check scripts/owned.sh",
])
def test_one_owned_path_cannot_authorize_other_targets(command):
    _, payload = run_classifier(command, "tests/test_owned.py", "src/owned.test.ts", "scripts/owned.sh")
    assert payload["class"] == "unscoped"


@pytest.mark.parametrize("command", [
    "pytest tests/test_owned.py tests/ -q",
    "pytest tests/test_owned.py -k selected -q",
    "npx vitest run src/owned.test.ts src/",
])
def test_named_file_cannot_hide_directory_sweep_or_pytest_selection(command):
    _, payload = run_classifier(command, "tests/test_owned.py", "src/owned.test.ts")
    assert payload["class"] == "broad"


def test_interpreter_check_tool_is_not_an_owned_target():
    _, payload = run_classifier("python3 tooling/validator.py check src/owned.json", "src/owned.json")
    assert payload["class"] == "scoped_check"


def test_all_declared_test_paths_and_plugin_options_are_accepted():
    _, payload = run_classifier("python3 -m pytest -p no:cacheprovider tests/test_a.py tests/test_b.py -q", "tests/test_a.py", "tests/test_b.py")
    assert payload["class"] == "focused"


@pytest.mark.parametrize("command", [
    "verify manually by eye && arbitrary_unknown_command",
    "arbitrary_unknown_command && inspect visible-app manually",
    "echo manual && arbitrary_unknown_command",
])
def test_manual_language_cannot_mask_unscoped_commands(command):
    _, payload = run_classifier(command)
    assert payload["class"] == "unscoped"


@pytest.mark.parametrize(
    "command",
    [
        "pytest",
        "pytest plugins/meta-dev/tests -q",
        "pytest -k classifier",
        "vitest run",
        "jest --watch=false",
        "npm run check",
        "pnpm build",
        "yarn test",
        "bun run test",
        "svelte-check --tsconfig ./tsconfig.json",
        "npx tsc --noEmit",
    ],
)
def test_package_wide_and_fileless_checks_are_broad(command: str):
    result, payload = run_classifier(command)
    assert result.returncode == 0
    assert payload["class"] == "broad"


def test_allowed_path_checks_are_scoped_but_other_paths_are_not():
    allowed = "plugins/meta-dev/scripts/verify-scope.py"

    result, payload = run_classifier(f"bash -n {allowed}", allowed)
    assert result.returncode == 0
    assert payload["class"] == "scoped_check"

    result, payload = run_classifier(f"grep Classification {allowed}", allowed)
    assert result.returncode == 0
    assert payload["class"] == "scoped_check"

    result, payload = run_classifier("bash -n plugins/meta-dev/scripts/other.sh", allowed)
    assert result.returncode == 0
    assert payload["class"] == "unscoped"


def test_compound_command_with_broad_segment_is_broad():
    command = "pytest plugins/meta-dev/tests/test_verify_scope.py -q && npm run build"
    result, payload = run_classifier(command)
    assert result.returncode == 0
    assert payload["class"] == "broad"
    assert "compound command contains broad segment" in payload["reason"]


@pytest.mark.parametrize(
    "command",
    [
        "verify manually by eye",
        "run GPU smoke test",
        "launch visible-app check",
        "check result by-hand",
    ],
)
def test_human_verification_is_manual(command: str):
    result, payload = run_classifier(command)
    assert result.returncode == 0
    assert payload["class"] == "manual"


@pytest.mark.parametrize("command", ["cargo test -p core", "go test ./pkg/foo", "make smoke-test"])
def test_unknown_test_commands_are_unscoped(command: str):
    result, payload = run_classifier(command)
    assert result.returncode == 0
    assert payload["class"] == "unscoped"


def test_malformed_shell_command_is_nonzero_json_error():
    result, payload = run_classifier("pytest 'unterminated")
    assert result.returncode != 0
    assert "error" in payload
