from __future__ import annotations

from pathlib import Path
import subprocess
import sys


PLUGIN = Path(__file__).resolve().parents[1]
SYNC = PLUGIN / "scripts" / "sync-agent-skill-adapters.py"


def test_sync_rejects_symlinked_generated_adapter_root(tmp_path):
    root = tmp_path / "project"
    source = root / ".agents" / "skills" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")
    target = tmp_path / "adapter-target"
    target.mkdir()
    destination = root / ".claude" / "skills"
    destination.parent.mkdir(parents=True)
    destination.symlink_to(target, target_is_directory=True)

    result = subprocess.run(
        [sys.executable, str(SYNC), "--project-root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "generated adapter root symlink forbidden" in result.stderr
