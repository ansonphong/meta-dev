"""Focused guardrails for host-neutral packaged runtime assets."""
import json
import os
from pathlib import Path
import subprocess
import sys


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
STATE_REDUCE = PLUGIN_ROOT / "scripts" / "state-reduce.py"
CONFIG_MERGE = PLUGIN_ROOT / "scripts" / "config-merge.py"

# These files intentionally identify the package publisher or the published
# schema location. They are provenance, never runtime routing or approval text.
PROVENANCE_ALLOWLIST = {
    Path(".claude-plugin/plugin.json"),
    Path(".codex-plugin/plugin.json"),
    *{Path("schemas") / path.name for path in (PLUGIN_ROOT / "schemas").glob("*.json")},
    *{Path("templates") / path.name for path in (PLUGIN_ROOT / "templates").glob("*.json")},
}

SCAN_DIRS = ("commands", "references", "skills", "codex-skills", "scripts")
SKIP_PATHS = {
    Path("scripts/sweep-wip-commit.sh"),
    Path("scripts/version-bump.py"),
    Path("scripts/test-plugin.sh"),
}
FORBIDDEN = (
    "360-" + "hextile",
    "p" + "hong",
    "/mnt/" + "c/Users/",
    "/mnt/" + "d/Users/",
    "/home/",
    "~/" + ".codex",
    "~/" + ".claude",
    "CLAUDE_PLUGIN_ROOT" + ":-.",
)


def _package_files():
    for directory in SCAN_DIRS:
        root = PLUGIN_ROOT / directory
        for path in root.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                relative = path.relative_to(PLUGIN_ROOT)
                if relative not in SKIP_PATHS:
                    yield relative, path
    for relative in PROVENANCE_ALLOWLIST:
        yield relative, PLUGIN_ROOT / relative


def test_packaged_runtime_assets_are_host_neutral():
    violations = []
    for relative, path in _package_files():
        if relative in PROVENANCE_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for forbidden in FORBIDDEN:
            if forbidden.lower() in text:
                violations.append(f"{relative}: {forbidden}")

    assert not violations, "host-branded runtime reference(s):\n" + "\n".join(violations)


def test_state_reducer_writes_to_the_resolved_project_root(tmp_path):
    project = tmp_path / "host-project"
    project.mkdir()
    (project / ".meta-dev").mkdir()
    (project / ".meta-dev" / "repos.json").write_text(
        json.dumps({"root": "..", "repos": {}}), encoding="utf-8"
    )
    dashboard = project / "plans" / "_dashboard"
    dashboard.mkdir(parents=True)
    (dashboard / "state.events.jsonl").write_text(
        '{"event":"session_start","session_id":"portable"}\n', encoding="utf-8"
    )
    (dashboard / "settings.local.json").write_text(
        json.dumps({"meta_dev": {"inbox": {"max_open_items": 77}}}), encoding="utf-8"
    )
    wrong_cwd = tmp_path / "unrelated"
    wrong_cwd.mkdir()

    env = dict(os.environ, META_DEV_PROJECT_ROOT=str(project), META_DEV_PLUGIN_ROOT=str(PLUGIN_ROOT))
    result = subprocess.run(
        [sys.executable, str(STATE_REDUCE)],
        cwd=wrong_cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (project / "plans" / "_dashboard" / "state.json").is_file()
    assert not (wrong_cwd / "plans" / "_dashboard" / "state.json").exists()

    config = subprocess.run(
        [sys.executable, str(CONFIG_MERGE)], cwd=wrong_cwd, env=env,
        capture_output=True, text=True, check=False,
    )
    assert config.returncode == 0, config.stderr
    assert json.loads(config.stdout)["meta_dev"]["inbox"]["max_open_items"] == 77
