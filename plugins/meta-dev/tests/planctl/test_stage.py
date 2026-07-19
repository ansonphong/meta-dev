#!/usr/bin/env python3
"""Critical regression guard for ``planctl stage`` frontmatter state."""
import os
import pathlib
import subprocess
import sys


_SCRIPTS = str(pathlib.Path(__file__).resolve().parent.parent.parent / "scripts")


def test_stage_without_status_removes_stale_stage_state():
    """A bare stage transition must not inherit a stale completion bit."""
    root = os.environ["META_DEV_ROOT"]
    rel = "plans/meta/stale-stage-state.md"
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(
            "---\n"
            "stage: 5\n"
            "stage_state: done\n"
            "repo: meta\n"
            "---\n\n"
            "# Fixture\n"
        )

    env = dict(os.environ, PYTHONPATH=_SCRIPTS)
    result = subprocess.run(
        [sys.executable, "-m", "planctl", "stage", rel, "6"],
        env=env,
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    text = open(path, encoding="utf-8").read()
    assert "stage: 6\n" in text
    assert "stage_state:" not in text
