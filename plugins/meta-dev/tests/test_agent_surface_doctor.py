from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest

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
    stable = run("--project-root", str(root), "--check", "instructions", "--check", "context")
    assert stable.returncode == 0, stable.stderr
    report = json.loads(stable.stdout)
    assert report["ok"] is True
    assert report["projects"][0]["agents"]["bytes"] == 6
    assert report["projects"][0]["agents"]["characters"] == 6

    (root / "AGENTS.md").write_bytes(b"a" * 23999)
    pass_boundary = run("--project-root", str(root), "--check", "instructions")
    assert pass_boundary.returncode == 0, pass_boundary.stderr
    pass_report = json.loads(pass_boundary.stdout)
    assert pass_report["projects"][0]["agents"]["bytes"] == 23999
    assert pass_report["projects"][0]["agents"]["characters"] == 23999
    assert all(finding["code"] != "agents_bytes" for finding in pass_report["projects"][0]["findings"])

    (root / "AGENTS.md").write_bytes(b"a" * 24000)
    pass_boundary = run("--project-root", str(root), "--check", "instructions")
    assert pass_boundary.returncode == 0, pass_boundary.stderr
    pass_report = json.loads(pass_boundary.stdout)
    assert pass_report["projects"][0]["agents"]["bytes"] == 24000
    assert pass_report["projects"][0]["agents"]["characters"] == 24000
    assert all(finding["code"] != "agents_bytes" for finding in pass_report["projects"][0]["findings"])

    (root / "AGENTS.md").write_bytes(b"a" * 24001)
    fail_boundary = run("--project-root", str(root), "--check", "instructions")
    assert fail_boundary.returncode == 1, fail_boundary.stderr
    fail_report = json.loads(fail_boundary.stdout)
    assert fail_report["projects"][0]["agents"]["bytes"] == 24001
    assert fail_report["projects"][0]["agents"]["characters"] == 24001
    assert any(finding["code"] == "agents_bytes" for finding in fail_report["projects"][0]["findings"])

    (root / "AGENTS.md").write_text("🧩" * 39999, encoding="utf-8")
    near_char_limit = run("--project-root", str(root), "--check", "instructions")
    assert near_char_limit.returncode == 1, near_char_limit.stderr
    near_report = json.loads(near_char_limit.stdout)
    assert near_report["projects"][0]["agents"]["characters"] == 39999
    assert all(finding["code"] != "agents_characters" for finding in near_report["projects"][0]["findings"])

    (root / "AGENTS.md").write_text("🧩" * 40000, encoding="utf-8")
    at_char_limit = run("--project-root", str(root), "--check", "instructions")
    assert at_char_limit.returncode == 1, at_char_limit.stderr
    at_report = json.loads(at_char_limit.stdout)
    assert at_report["projects"][0]["agents"]["characters"] == 40000
    assert any(finding["code"] == "agents_characters" for finding in at_report["projects"][0]["findings"])


def test_case_fold_alias_and_symlink_root(tmp_path):
    root = project(tmp_path)
    (root / "agents.md").write_text("other\n", encoding="utf-8")
    assert run("--project-root", str(root), "--check", "case-fold").returncode == 1
    outside = tmp_path / "outside.md"
    outside.write_text("x", encoding="utf-8")
    rejected = subprocess.run([str(CHECK), "--project-root", str(root), "--scope-file", str(outside)], capture_output=True, text=True, check=False)
    assert rejected.returncode == 2
    accepted = subprocess.run([str(CHECK), "--project-root", str(root), "--scope-file", "AGENTS.md", "--check", "instructions"], capture_output=True, text=True, check=False)
    assert accepted.returncode == 0, accepted.stderr


def test_case_fold_alias_recognizes_case_insensitive_inodes():
    mount = Path("/mnt/d")
    if not mount.is_dir():
        pytest.skip("/mnt/d is not available for case-insensitive alias fixture")
    with tempfile.TemporaryDirectory(dir=mount, prefix="agent-surface-doctor-") as tmp_root:
        root = project(Path(tmp_root) / "project")
        agents = root / "AGENTS.md"
        alias = root / "agents.md"
        alias.write_text(agents.read_text(encoding="utf-8"), encoding="utf-8")
        same_inode = (agents.stat().st_dev, agents.stat().st_ino) == (alias.stat().st_dev, alias.stat().st_ino)

        result = run("--project-root", str(root), "--check", "case-fold")
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        findings = report["projects"][0]["findings"]
        codes = {finding["code"] for finding in findings}

        if same_inode:
            assert "casefold_alias" in codes
            assert "conflict" not in codes
        else:
            assert "duplicate_copy" in codes


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
