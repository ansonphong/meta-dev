"""Focused integration of adaptive policy, entrypoints, and measurement contract."""
import json
from pathlib import Path
import subprocess
import sys

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("path", [
    "commands/meta-dev.md", "commands/meta-planner.md",
    "commands/meta-execute.md", "commands/meta-loop-gap.md",
    "references/workflows/protocol.md", "skills/plan/SKILL.md",
    "skills/execute/SKILL.md",
])
def test_stage_entrypoints_reach_one_adaptive_policy(path):
    text = (ROOT / path).read_text()
    assert "references/adaptive-workflow.md" in text
    assert (ROOT / "references/adaptive-workflow.md").is_file()


@pytest.mark.parametrize("path", [
    "commands/meta-dev.md", "commands/meta-execute.md",
    "commands/meta-loop-gap.md", "references/dev-swarms.md",
    "references/dev-modes.md", "references/execute-charter.md",
    "references/execute-dispatch.md", "references/work-ladder.md",
])
def test_active_doctrine_does_not_ship_personal_or_fixed_fanout_rules(path):
    text = (ROOT / path).read_text()
    for obsolete in ["Phong", "credits are exhausted", "19 agents",
                     "TAKE IT AND KEEP MOVING", "default 300000",
                     ".claude/context/harness/subagent-picker.md"]:
        assert obsolete not in text, (path, obsolete)


def test_sensitive_classifier_tags_reach_same_policy_as_planner(tmp_path):
    policy = ROOT / "scripts/workflow-policy.py"
    for tag in ["security-boundary", "schema-drift", "money-path"]:
        result = subprocess.run(
            [sys.executable, str(policy), "--project-root", str(tmp_path),
             "--host", "codex", "--model", "gpt-6-astra", "--risk", tag],
            capture_output=True, text=True, check=True,
        )
        resolved = json.loads(result.stdout)
        assert resolved["plan_target"] != "lean"
        assert resolved["execution"]["granularity"] == "task"
        assert resolved["review"]["cross_family"] is False


def test_measurement_preserves_unknown_usage_and_failure():
    schema = json.loads((ROOT / "schemas/workflow-measurement.schema.json").read_text())
    record = dict(policy="adaptive", model="configured-model", host="minimal",
                  revision="abc123", task_id="T1.1", outcome="infra_red",
                  accepted_outcomes=0, elapsed_seconds=5, input_tokens=None,
                  output_tokens=None, cost=None, rework=0, missed_defects=None,
                  unnecessary_interruptions=0)
    jsonschema.validate(record, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(dict(record, accepted_outcomes=-1), schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(dict(record, elapsed_seconds=-1), schema)


def test_closing_review_uses_declared_policy_not_a_new_test_quota():
    rubric = (ROOT / "workflow-skills/code-review-protocol/references/review-dimensions.md").read_text()
    assert "Declared test policy" in rubric
    assert "Ordinary `test: no` work may pass" in rubric
    assert "No tests for new functionality" not in rubric
    assert "Required critical tests and human gates remain mandatory" in rubric
