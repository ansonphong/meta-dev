"""Release pins for the current plugin surface."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

PLUGIN = Path(__file__).resolve().parents[1]
REPO = PLUGIN.parents[1]


def test_jev_release_pins_and_codex_surface():
    claude = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    codex = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text())
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert claude["version"] == codex["version"] == "1.5.10"
    assert "## 1.5.10" in changelog

    pin = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "plugins/meta-dev/tests/test_host_neutral_references.py::test_portability_release_keeps_manifests_and_marketplaces_in_lockstep",
            "-q",
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert pin.returncode == 0, pin.stdout + pin.stderr

    surface = subprocess.run(
        ["bash", "plugins/meta-dev/tests/test-codex-package-surface.sh"],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert surface.returncode == 0, surface.stdout + surface.stderr
