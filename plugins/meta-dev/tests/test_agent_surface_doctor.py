from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


PLUGIN = Path(__file__).resolve().parents[1]
DOCTOR = PLUGIN / "scripts" / "agent-surface-doctor.py"
CHECK = PLUGIN / "scripts" / "agent-surface-check"


def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "AGENTS.md").write_text("rules\n", encoding="utf-8")
    (root / ".claude").mkdir()
    (root / ".claude" / "CLAUDE.md").write_text("@../AGENTS.md\n", encoding="utf-8")
    (root / "docs" / "agent-context").mkdir(parents=True)
    (root / "docs" / "agent-context" / "note.md").write_text("context\n", encoding="utf-8")
    (root / ".agents" / "skills" / "demo" / "references").mkdir(parents=True)
    (root / ".agents" / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")
    (root / ".agents" / "skills" / "demo" / "references" / "note.md").write_text("x\n", encoding="utf-8")
    return root


def run(*args: str):
    return subprocess.run([sys.executable, str(DOCTOR), *args], capture_output=True, text=True, check=False)


def test_doctor_reports_stable_json_and_boundaries(tmp_path):
    root = project(tmp_path)
    result = run("--project-root", str(root), "--check", "instructions", "--check", "context")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["projects"][0]["agents"]["bytes"] == 6
    assert report["projects"][0]["agents"]["characters"] == 6

    (root / "AGENTS.md").write_bytes(b"a" * 24001)
    assert run("--project-root", str(root), "--check", "instructions").returncode == 1
    (root / "AGENTS.md").write_text("a" * 40000, encoding="utf-8")
    assert run("--project-root", str(root), "--check", "instructions").returncode == 1


def test_case_conflict_and_scope_wrapper(tmp_path):
    root = project(tmp_path)
    (root / "agents.md").write_text("other\n", encoding="utf-8")
    assert run("--project-root", str(root), "--check", "case-fold").returncode == 1
    outside = tmp_path / "outside.md"
    outside.write_text("x", encoding="utf-8")
    rejected = subprocess.run([str(CHECK), "--project-root", str(root), "--scope-file", str(outside)], capture_output=True, text=True, check=False)
    assert rejected.returncode == 2
    accepted = subprocess.run([str(CHECK), "--project-root", str(root), "--scope-file", "AGENTS.md", "--check", "instructions"], capture_output=True, text=True, check=False)
    assert accepted.returncode == 0, accepted.stderr
