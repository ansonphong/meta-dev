"""Focused portability coverage for plugin/project/repository root resolution."""
import json
import os
import pathlib
import subprocess
import sys

from planctl import runbook, statedir


_PLUGIN = pathlib.Path(__file__).resolve().parents[2]
_TOPOLOGY = _PLUGIN / "scripts" / "lib" / "repo-topology.py"
_PLUGIN_ROOT = _PLUGIN / "scripts" / "lib" / "plugin-root.sh"
_TEMPLATE = _PLUGIN / "templates" / "repo-topology.json"


def _topology(path, root, repos):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"root": root, "repos": repos}), encoding="utf-8")


def _run_topology(*args, env, cwd):
    return subprocess.run(
        [sys.executable, str(_TOPOLOGY), *args], env=env, cwd=cwd,
        capture_output=True, text=True, check=False,
    )


def test_neutral_topology_beats_legacy_and_supports_arbitrary_slugs(
    tmp_path, monkeypatch
):
    project = tmp_path / "host-project"
    api = project / "services" / "api"
    legacy = project / "legacy-repo"
    api.mkdir(parents=True)
    legacy.mkdir()
    neutral_path = project / ".meta-dev" / "repos.json"
    legacy_path = project / ".claude" / "meta-dev-repos.json"
    _topology(neutral_path, "..", {"studio-api": "services/api"})
    _topology(legacy_path, "..", {"old-app": "legacy-repo"})

    env = dict(os.environ)
    for name in ("META_DEV_REPOS_FILE", "META_DEV_ROOT", "CLAUDE_PROJECT_DIR"):
        env.pop(name, None)
    env["META_DEV_PROJECT_ROOT"] = str(project)
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()

    resolved = _run_topology("studio-api", env=env, cwd=unrelated)
    assert resolved.returncode == 0
    assert resolved.stdout == str(api)
    assert str(legacy_path) in resolved.stderr
    assert _run_topology("old-app", env=env, cwd=unrelated).returncode == 1

    diagnose = _run_topology("--diagnose", env=env, cwd=unrelated)
    assert diagnose.returncode == 0
    assert "selected\t%s" % neutral_path in diagnose.stdout
    assert "shadowed\t%s" % legacy_path in diagnose.stdout

    monkeypatch.delenv("META_DEV_ROOT", raising=False)
    monkeypatch.setenv("META_DEV_PROJECT_ROOT", str(project))
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("META_DEV_REPOS_FILE", raising=False)
    statedir._ROOT_MEMO.clear()
    assert statedir.project_root() == str(project)


def test_explicit_topology_and_plugin_root_precedence(tmp_path):
    project = tmp_path / "host"
    project.mkdir()
    explicit_repo = project / "custom"
    explicit_repo.mkdir()
    explicit = tmp_path / "override.json"
    _topology(explicit, str(project), {"custom-slug": "custom"})

    env = dict(os.environ, META_DEV_REPOS_FILE=str(explicit))
    result = _run_topology("custom-slug", env=env, cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout == str(explicit_repo)

    roots = []
    for name in ("meta", "plugin", "claude"):
        path = tmp_path / name
        path.mkdir()
        roots.append(path)
    result = subprocess.run(
        ["bash", "-c", "source \"$1\"; _md_plugin_root", "bash", str(_PLUGIN_ROOT)],
        env=dict(env, META_DEV_PLUGIN_ROOT=str(roots[0]), PLUGIN_ROOT=str(roots[1]),
                 CLAUDE_PLUGIN_ROOT=str(roots[2])),
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == str(roots[0])

    fallback_env = dict(env)
    for name in ("META_DEV_PLUGIN_ROOT", "PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):
        fallback_env.pop(name, None)
    fallback = subprocess.run(
        ["bash", "-c", "source \"$1\"; _md_plugin_root", "bash", str(_PLUGIN_ROOT)],
        env=fallback_env, capture_output=True, text=True, check=False,
    )
    assert fallback.returncode == 0
    assert fallback.stdout.strip() == str(_PLUGIN)


def test_project_root_is_authoritative_without_or_over_unrelated_topology(tmp_path):
    project = tmp_path / "configured-project"
    project.mkdir()
    empty = tmp_path / "no-topology"
    empty.mkdir()
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    _topology(unrelated / ".meta-dev" / "repos.json", str(unrelated), {"wrong": "."})
    env = dict(os.environ, META_DEV_PROJECT_ROOT=str(project))
    for name in ("META_DEV_REPOS_FILE", "META_DEV_ROOT", "CLAUDE_PROJECT_DIR"):
        env.pop(name, None)

    root = _run_topology("--root", env=env, cwd=unrelated)
    assert root.returncode == 0
    assert root.stdout == str(project)
    root_without_topology = _run_topology("--root", env=env, cwd=empty)
    assert root_without_topology.returncode == 0
    assert root_without_topology.stdout == str(project)
    assert _run_topology("wrong", env=env, cwd=unrelated).returncode == 1


def test_template_is_host_neutral_and_runbook_labels_dynamic_repo_buckets():
    assert json.loads(_TEMPLATE.read_text(encoding="utf-8")) == {
        "root": "..", "repos": {}
    }
    assert runbook._member_label(
        "plans/custom-slug/2026-08-01-plan.md", "plan"
    ) == "**2026-08-01-plan**"
    assert "release-arc" in runbook._member_label(
        "plans/custom-slug/release-arc/00-master-plan.md", "plan"
    )
