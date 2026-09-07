"""Prompt-hook autonomy stays within task authority and preserves hard gates."""
import json
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks/scripts/on-stage-prompt.sh"
REFERENCE = ROOT / "references/autonomous-mode.md"


def run_hook(prompt, tmp_path, **environment):
    env = dict(os.environ, META_DEV_PLUGIN_ROOT=str(tmp_path), **environment)
    run = subprocess.run(["bash", str(HOOK)], input=json.dumps({"prompt": prompt}),
                         text=True, capture_output=True, env=env, cwd=tmp_path)
    assert run.returncode == 0, run.stderr
    return run.stdout


@pytest.mark.parametrize("prompt", [
    "/meta-audit plans/example --autonomous", "Review the changes --autonomous",
    "--autonomous diagnose the failure", "Plan the feature --autonomous",
    "/meta-execute plans/example --autonomous",
])
def test_autonomy_injection_preserves_scope_and_hard_gates(tmp_path, prompt):
    output = json.loads(run_hook(prompt, tmp_path))["hookSpecificOutput"]
    assert output["hookEventName"] == "UserPromptSubmit"
    context = output["additionalContext"]
    for marker in ("stays read-only", "only for a scoped implementation",
                   "optional cadence", "separate configured authorization",
                   "No automatic Fable consultation", "No deploy, ship, publish",
                   "safety veto list", "NEVER pass `--human`", "stay UNCHECKED",
                   "parked", "residual risk"):
        assert marker in context
    assert "fable-consult.sh" not in context
    assert "They have\npre-authorized this run" not in context


@pytest.mark.parametrize("prompt", ["", "Review this", "--autonomously", "/path/--autonomous",
                                   "Please read --autonomous-mode", "--autonomous=false"])
def test_other_tokens_do_not_enable_autonomy(tmp_path, prompt):
    assert run_hook(prompt, tmp_path) == ""


def test_neutral_plugin_root_and_stage_emission_still_work(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "stage-emit.sh").write_text(
        '#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$META_DEV_PLUGIN_ROOT/emitted"\n')
    run_hook("/meta-planner plans/example --autonomous", tmp_path,
             CLAUDE_PLUGIN_ROOT=str(tmp_path / "unused-vendor-root"))
    assert (tmp_path / "emitted").read_text().splitlines() == ["plans/example", "plan", "in_progress"]


def test_missing_stage_emitter_never_blocks_injection(tmp_path):
    assert "AUTONOMOUS MODE ENGAGED" in run_hook("/meta-execute plans/example --autonomous", tmp_path)


def test_malformed_payload_is_nonblocking(tmp_path):
    run = subprocess.run(["bash", str(HOOK)], input="{broken", text=True,
                         capture_output=True, cwd=tmp_path)
    assert run.returncode == 0
    assert run.stdout == ""


def test_reference_matches_permission_and_consultant_contract():
    text = REFERENCE.read_text()
    for marker in ("read-only request", "new authority", "optional cadence prompts",
                   "safety veto list", "without calling or installing a consultant",
                   "must never pass", "`--human`", "optional configured consultant",
                   "never adds paid external dispatch permission",
                   "only if an authorized", "Unresolved human gates stay unresolved"):
        assert marker in text
    assert "<n> Fable consults" not in text
    assert "Tauri" not in text
