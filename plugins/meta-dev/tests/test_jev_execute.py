"""Mock-path checks for jev-decide.sh and jev-execute.sh."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DECIDE = ROOT / "scripts" / "jev-decide.sh"
EXECUTE = ROOT / "scripts" / "jev-execute.sh"


def _env():
    env = os.environ.copy()
    env["JEV_MOCK"] = "1"
    env.pop("TYPESAFE_API_KEY", None)
    env.pop("OPENROUTER_API_KEY", None)
    return env


def test_decide_auth_payment_stays_high():
    proc = subprocess.run(
        ["bash", str(DECIDE), "--", "fix the auth payment webhook"],
        check=False,
        capture_output=True,
        text=True,
        env=_env(),
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["budget"] == "high"
    assert out["hotl"] is False
    assert "ts_" not in proc.stdout
    assert "sk-or-" not in proc.stdout


def test_execute_mock_prints_typed_fields():
    proc = subprocess.run(
        ["bash", str(EXECUTE), "--mock", "--", "is this a billing ticket?"],
        check=False,
        capture_output=True,
        text=True,
        env=_env(),
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    answers = out["answers"]
    assert answers["safe_to_auto"]["type"] == "noul"
    assert answers["task_shape"]["type"] == "choice"
    assert "probabilities" in answers["task_shape"]
    assert answers["stakes"]["type"] == "score"
    assert "spawn" not in proc.stdout
