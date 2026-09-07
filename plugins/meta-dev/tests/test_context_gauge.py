"""Hermetic host/session telemetry and threshold regression coverage."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "context-gauge.py"
SPEC = importlib.util.spec_from_file_location("context_gauge", SCRIPT)
gauge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gauge)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    for name in list(gauge.os.environ):
        if name.startswith("META_DEV_CONTEXT_") or name in {
            "CODEX_THREAD_ID", "CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID",
            "CLAUDE_CONFIG_DIR", "CLAUDE_PROJECTS_DIR", "CODEX_HOME",
        }:
            monkeypatch.delenv(name)
    monkeypatch.setenv("HOME", str(tmp_path))


def args(**overrides):
    values = dict(host=None, session_id=None, transcript=None, telemetry=None,
                  model=None, context_window=None, threshold=None, threshold_ratio=None)
    values.update(overrides)
    return argparse.Namespace(**values)


def jsonl(path, *records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    return str(path)


def claude_record(count=10, **extra):
    return {"message": {"usage": {"input_tokens": count, **extra}}}


def codex_record(count=100, output=20, cached=90):
    return {"type": "event_msg", "payload": {"type": "token_count", "info": {
        "last_token_usage": {"input_tokens": count, "output_tokens": output,
                             "cached_input_tokens": cached},
        "total_token_usage": {"input_tokens": 9999999},
        "model_context_window": 1000,
    }}}


def telemetry(tmp_path, **overrides):
    data = dict(host="grok", session_id="active", context_tokens=800, context_window=1000)
    data.update(overrides)
    path = tmp_path / "usage.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_missing_identity_never_uses_other_claude_session(tmp_path):
    jsonl(tmp_path / ".claude/projects/project/other.jsonl", claude_record())
    result = gauge.evaluate(args(threshold="100"), {})
    assert result["verdict"] == "UNKNOWN"
    assert result["transcript"] is None


def test_requested_identity_absent_does_not_fallback(tmp_path, monkeypatch):
    jsonl(tmp_path / ".claude/projects/project/other.jsonl", claude_record())
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "active")
    assert gauge.evaluate(args(threshold="100"), {})["verdict"] == "UNKNOWN"


def test_ambiguous_host_requires_explicit_selection(tmp_path, monkeypatch):
    jsonl(tmp_path / ".claude/projects/project/active.jsonl", claude_record())
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "active")
    monkeypatch.setenv("CODEX_THREAD_ID", "another")
    assert gauge.evaluate(args(threshold="100"), {})["verdict"] == "UNKNOWN"
    assert gauge.evaluate(args(host="claude", threshold="100"), {})["verdict"] == "OK"


def test_duplicate_exact_transcripts_are_ambiguous(tmp_path):
    for project in ("one", "two"):
        jsonl(tmp_path / f".claude/projects/{project}/active.jsonl", claude_record())
    assert gauge.evaluate(args(host="claude", session_id="active", threshold="100"), {})["verdict"] == "UNKNOWN"


@pytest.mark.parametrize("sid", ["../other", "*", "", "a/b"])
def test_unsafe_session_identity(sid):
    assert gauge.evaluate(args(host="claude", session_id=sid), {})["verdict"] == "UNKNOWN"


def test_claude_cache_semantics_latest_not_cumulative(tmp_path):
    path = jsonl(tmp_path / "active.jsonl", claude_record(9999),
                 claude_record(10, cache_read_input_tokens=50, cache_creation_input_tokens=20))
    result = gauge.evaluate(args(host="claude", session_id="active", transcript=path, threshold="80"), {})
    assert result["tokens"] == 80
    assert result["verdict"] == "OVER"


def test_claude_wrong_filename_or_embedded_identity(tmp_path):
    for name, record in (("other", claude_record()),
                         ("active", dict(claude_record(), sessionId="other"))):
        path = jsonl(tmp_path / f"{name}.jsonl", record)
        result = gauge.evaluate(args(host="claude", session_id="active", transcript=path, threshold="100"), {})
        assert result["verdict"] == "UNKNOWN"


def test_codex_binds_metadata_and_does_not_double_count_cache(tmp_path, monkeypatch):
    path = tmp_path / ".codex/sessions/2026/09/06/rollout-stamp-active.jsonl"
    jsonl(path, {"type": "session_meta", "payload": {"id": "active"}},
          codex_record(900, 10), codex_record())
    monkeypatch.setenv("CODEX_THREAD_ID", "active")
    result = gauge.evaluate(args(), {})
    assert result["tokens"] == 120
    assert result["context_window"] == 1000
    assert result["threshold"] == 800
    assert result["verdict"] == "OK"


@pytest.mark.parametrize("records", [
    [codex_record()],
    [{"type": "session_meta", "payload": {"id": "other"}}, codex_record()],
    [{"type": "session_meta", "payload": {"id": "active"}}, codex_record(),
     {"type": "session_meta", "payload": {"id": "other"}}],
])
def test_codex_rejects_unbound_or_mismatched_usage(tmp_path, records):
    path = jsonl(tmp_path / "rollout.jsonl", *records)
    result = gauge.evaluate(args(host="codex", session_id="active", transcript=path), {})
    assert result["verdict"] == "UNKNOWN"


def test_generic_session_bound_telemetry(tmp_path):
    path = telemetry(tmp_path)
    result = gauge.evaluate(args(host="grok", session_id="active", telemetry=path), {})
    assert result["verdict"] == "OVER"
    assert result["pct"] == 100


@pytest.mark.parametrize("override", [{"host": "other"}, {"session_id": "other"},
                                      {"context_tokens": -1}, {"context_tokens": True},
                                      {"context_tokens": 1.5}, {"context_window": 0},
                                      {"context_window": float("inf")}])
def test_generic_invalid_identity_or_usage(tmp_path, override):
    path = telemetry(tmp_path, **override)
    assert gauge.evaluate(args(host="grok", session_id="active", telemetry=path), {})["verdict"] == "UNKNOWN"


@pytest.mark.parametrize("overrides", [{"threshold": "0"}, {"threshold": "-1"},
                                      {"threshold": "bad"}, {"threshold": "1001"},
                                      {"threshold_ratio": "nan"}, {"threshold_ratio": "inf"},
                                      {"threshold_ratio": "0"}, {"threshold_ratio": "1.01"},
                                      {"context_window": "0"}])
def test_invalid_threshold_policy_is_nonblocking(tmp_path, overrides):
    result = gauge.evaluate(args(host="grok", session_id="active", telemetry=telemetry(tmp_path), **overrides), {})
    assert result["verdict"] == "UNKNOWN"


def test_no_fixed_default_window(tmp_path):
    path = telemetry(tmp_path, context_window=None)
    result = gauge.evaluate(args(host="grok", session_id="active", telemetry=path), {})
    assert result["verdict"] == "UNKNOWN"
    assert result["threshold"] is None


def test_config_window_and_model_fallback(tmp_path):
    path = telemetry(tmp_path, context_window=None)
    options = args(host="grok", session_id="active", telemetry=path, model="custom-model")
    config = {"model_windows": {"custom-model": 2000}, "threshold_ratio": 0.5}
    assert gauge.evaluate(options, config)["threshold"] == 1000
    config["context_window"] = 3000
    assert gauge.evaluate(options, config)["threshold"] == 1500


def test_cli_env_config_precedence(tmp_path, monkeypatch):
    path = telemetry(tmp_path)
    monkeypatch.setenv("META_DEV_CONTEXT_THRESHOLD", "950")
    options = args(host="grok", session_id="active", telemetry=path)
    assert gauge.evaluate(options, {"threshold": 850})["threshold"] == 950
    options.threshold = "900"
    assert gauge.evaluate(options, {"threshold": 850})["threshold"] == 900


@pytest.mark.parametrize("content", ["{bad", "[]", '{"context_tokens":NaN}'])
def test_malformed_generic_telemetry(tmp_path, content):
    path = tmp_path / "bad.json"
    path.write_text(content)
    assert gauge.evaluate(args(host="grok", session_id="active", telemetry=str(path)), {})["verdict"] == "UNKNOWN"


def test_malformed_latest_record_does_not_reuse_stale_usage(tmp_path):
    path = Path(jsonl(tmp_path / "active.jsonl", claude_record()))
    path.write_text(path.read_text() + "{broken")
    result = gauge.evaluate(args(host="claude", session_id="active", transcript=str(path), threshold="100"), {})
    assert result["verdict"] == "UNKNOWN"


def test_main_exit_contract(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gauge, "context_settings", lambda project_root=None: {})
    cli = ["--host", "grok", "--session-id", "active", "--telemetry", telemetry(tmp_path), "--json"]
    assert gauge.main(cli) == 10
    assert json.loads(capsys.readouterr().out)["verdict"] == "OVER"
    assert gauge.main(cli + ["--threshold", "900"]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "OK"
    assert gauge.main(cli + ["--threshold", "bad"]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "UNKNOWN"


def test_invalid_settings_never_blocks(monkeypatch, capsys):
    def invalid(project_root=None):
        raise ValueError("bad config")
    monkeypatch.setattr(gauge, "context_settings", invalid)
    assert gauge.main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "UNKNOWN"


def test_project_root_pins_three_layer_cascade(tmp_path, monkeypatch):
    dashboard = tmp_path / "selected/plans/_dashboard"
    dashboard.mkdir(parents=True)
    (dashboard / "settings.json").write_text(json.dumps({"meta_dev": {"context": {"threshold": 900}}}))
    (dashboard / "settings.local.json").write_text(json.dumps({"meta_dev": {"context": {"threshold": 700}}}))
    foreign = tmp_path / "foreign.json"
    foreign.write_text(json.dumps({"root": str(tmp_path / "another-project"), "repos": {}}))
    monkeypatch.setenv("META_DEV_REPOS_FILE", str(foreign))
    monkeypatch.setenv("META_DEV_PLUGIN_ROOT", str(SCRIPT.parent.parent))
    path = telemetry(tmp_path)
    command = [sys.executable, str(SCRIPT), "--project-root", str(tmp_path / "selected"),
               "--host", "grok", "--session-id", "active", "--telemetry", path, "--json"]
    run = subprocess.run(command, text=True, capture_output=True)
    assert run.returncode == 10, run.stderr
    assert json.loads(run.stdout)["threshold"] == 700
    run = subprocess.run(command + ["--threshold", "950"], text=True, capture_output=True)
    assert run.returncode == 0
    assert json.loads(run.stdout)["threshold"] == 950
    assert gauge.os.environ["META_DEV_REPOS_FILE"] == str(foreign)


def test_missing_project_root_returns_unknown(tmp_path, capsys):
    assert gauge.main(["--project-root", str(tmp_path / "missing"), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "UNKNOWN"
