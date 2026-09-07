"""Adaptive policy must be deterministic, portable, bounded, and conservative."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/workflow-policy.py"
SPEC = importlib.util.spec_from_file_location("workflow_policy", SCRIPT)
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


@pytest.fixture
def settings():
    return json.loads((ROOT / "templates/settings.json").read_text())


@pytest.mark.parametrize("model", ["gpt-6-astra", "astra", "sol", "gpt-5.6-sol", "gpt-5.6",
                                   "claude-opus-4-8", "opus-4.8", "opus-5", "claude-opus-5",
                                   "grok-4.6", "grok-4-6"])
def test_frontier_profiles(settings, model):
    result = POLICY.resolve_policy(settings, model=model)
    assert result["plan_target"] == "lean"
    assert result["execution"]["granularity"] == "slice"
    assert result["execution"]["max_tasks_per_slice"] == 3
    assert result["hardening"]["max_reviewers"] == 1
    assert not any(result["capabilities"].values())
    assert not result["review"]["cross_family"]


@pytest.mark.parametrize("model,target", [("terra", "standard"), ("sonnet-5", "standard"),
                                         ("luna", "explicit"), ("spark", "explicit"),
                                         ("haiku", "explicit"), ("future-opus", "standard"),
                                         ("opus", "standard")])
def test_bounded_and_unknown_profiles(settings, model, target):
    result = POLICY.resolve_policy(settings, model=model)
    assert result["plan_target"] == target
    assert result["execution"]["granularity"] == "task"


def test_executor_precedence(settings):
    assert POLICY.resolve_policy(settings, host="codex")["executor"]["model"] == "gpt-5.6-terra"
    settings["meta_dev"]["workflow"]["host_execute_models"]["codex"] = "sol"
    assert POLICY.resolve_policy(settings, host="codex")["executor"]["model"] == "gpt-5.6-sol"
    result = POLICY.resolve_policy(settings, host="codex", model="astra")
    assert result["executor"]["source"] == "explicit"
    assert result["executor"]["model"] == "gpt-6-astra"
    settings["meta_dev"]["models"]["stage_overrides"]["execute"] = "opus-5"
    assert POLICY.resolve_policy(settings, host="claude")["plan_target"] == "lean"


@pytest.mark.parametrize("risk", ["auth", "payments", "migration", "security", "cross_service", "critical"])
def test_risk_floor_survives_configuration(settings, risk):
    settings["meta_dev"]["workflow"]["sensitive_risks"] = []
    result = POLICY.resolve_policy(settings, model="astra", target="lean", risks=[risk], granularity="slice")
    assert result["plan_target"] == "standard"
    assert result["execution"]["granularity"] == "task"
    assert result["hardening"]["depth"] == "full"
    assert "security_checks" in result["invariants"]
    assert not result["review"]["cross_family"]


def test_explicit_overrides_and_capacity(settings):
    result = POLICY.resolve_policy(settings, model="astra", target="explicit", granularity="task",
                                   research="full", harden="full", cross_family=True, available_workers=2)
    assert result["plan_target"] == "explicit"
    assert result["execution"]["max_parallel_workers"] == 2
    assert result["research"]["max_reviewers"] == 2
    assert result["hardening"]["max_reviewers"] == 2
    assert result["review"]["cross_family"]


def test_only_confirmed_host_capabilities(settings):
    settings["meta_dev"]["workflow"]["host_capabilities"]["custom"] = {"async_tools": True}
    assert POLICY.resolve_policy(settings, host="custom", model="astra")["capabilities"] == {
        "async_tools": True, "dynamic_effort": False}
    assert not POLICY.resolve_policy(settings, host="codex", model="astra")["capabilities"]["async_tools"]


def test_schema_and_neutral_defaults(settings):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((ROOT / "schemas/settings.schema.json").read_text())
    jsonschema.validate(settings, schema)
    assert settings["meta_dev"]["ladder"]["pool"] == []
    assert settings["meta_dev"]["ladder"]["paused"] == []
    assert settings["meta_dev"]["canary"]["targets"] == {}
    assert settings["meta_dev"]["ux"]["design_system_rules"] == []
    settings["meta_dev"]["models"]["stage_overrides"]["execute"] = "some-future-model"
    jsonschema.validate(settings, schema)
    settings["meta_dev"]["workflow"]["max_tasks_per_slice"] = 50
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(settings, schema)


@pytest.mark.parametrize("field,value", [("max_tasks_per_slice", 0), ("max_parallel_workers", 99),
                                         ("max_review_rounds", True), ("cross_family_review", "true"),
                                         ("plan_target", "magic")])
def test_invalid_config_fails_without_optional_schema(settings, field, value):
    settings["meta_dev"]["workflow"][field] = value
    with pytest.raises(ValueError):
        POLICY.resolve_policy(settings)


def test_alias_cycle(settings):
    settings["meta_dev"]["workflow"]["model_aliases"].update({"a": "b", "b": "a"})
    with pytest.raises(ValueError, match="cycle"):
        POLICY.resolve_policy(settings, model="a")


def test_cli_three_layer_cascade_and_exact_project_root(tmp_path):
    dashboard = tmp_path / "plans/_dashboard"
    dashboard.mkdir(parents=True)
    (dashboard / "settings.json").write_text(json.dumps({"meta_dev": {"workflow": {
        "host_execute_models": {"custom": "astra"}, "max_tasks_per_slice": 2,
        "cross_family_review": True}}}))
    (dashboard / "settings.local.json").write_text(json.dumps({"meta_dev": {"workflow": {
        "max_tasks_per_slice": 1, "cross_family_review": False}}}))
    env = dict(os.environ, META_DEV_PLUGIN_ROOT=str(ROOT))
    run = subprocess.run([sys.executable, str(SCRIPT), "--host", "custom", "--project-root", str(tmp_path)],
                         text=True, capture_output=True, env=env)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["executor"]["model"] == "gpt-6-astra"
    assert result["execution"]["max_tasks_per_slice"] == 1
    assert not result["review"]["cross_family"]
    (dashboard / "settings.local.json").write_text("not json")
    run = subprocess.run([sys.executable, str(SCRIPT), "--project-root", str(tmp_path)],
                         text=True, capture_output=True, env=env)
    assert run.returncode == 2
    assert "invalid configuration" in run.stderr
