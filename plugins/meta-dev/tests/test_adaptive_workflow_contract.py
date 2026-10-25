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


@pytest.mark.parametrize("path", [
    "commands/meta-execute.md", "commands/auto-execute.md",
    "references/execute-dispatch.md", "references/adaptive-workflow.md",
    "workflow-skills/agentic-exec-loop/references/loop-protocol.md",
])
def test_execution_routes_share_completion_policy_without_blanket_parking(path):
    text = (ROOT / path).read_text()
    assert "references/execute-charter.md" in text
    for obsolete in ["At most two repair attempts before parking",
                     "at most two scoped repair attempts",
                     "At most two scoped repair attempts",
                     "at most two attempts before disposition",
                     "Persistent ownership ends at completion, scope change"]:
        assert obsolete not in text, (path, obsolete)


def test_framework_preamble_keeps_ownership_without_stopping_on_stale_symbols():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/lib/framework-preamble.py"), str(ROOT)],
        capture_output=True, text=True, check=True,
    )
    assert "references/execute-charter.md" in result.stdout
    assert "ordinary repairs and whole-task acceptance" in result.stdout
    assert "Resolve changed technical assumptions within scope" in result.stdout
    assert "STOP and report" not in result.stdout


def test_default_lifecycle_uses_stage_outcomes_without_mandatory_command_chain():
    protocol = (ROOT / "references/workflows/protocol.md").read_text()
    for stage in ["Brainstorm", "Design", "Plan", "Harden", "Execute", "Review"]:
        assert f"| {stage} |" in protocol
    assert "one short record" in protocol
    assert "native host" in protocol
    command = (ROOT / "commands/meta-dev.md").read_text()
    for forced in ["Follow `references/dev-swarms.md`", "`/meta-planner`",
                   "`/meta-loop-gap`", "workflow-skills/waterfall-tracking/SKILL.md",
                   "model: opus"]:
        assert forced not in command


@pytest.mark.parametrize("path,forced", [
    ("skills/plan/SKILL.md", "workflow-skills/dod-contract/SKILL.md"),
    ("skills/execute/SKILL.md", "workflow-skills/agentic-exec-loop/SKILL.md"),
    ("skills/harden/SKILL.md", "commands/meta-loop-gap.md"),
])
def test_native_skills_do_not_automatically_stack_specialist_workflows(path, forced):
    assert forced not in (ROOT / path).read_text()


def test_default_plan_can_share_a_record_without_forced_ir_or_feature_folder():
    skill = (ROOT / "skills/plan/SKILL.md").read_text()
    guide = (ROOT / "references/codex-writing-plans.md").read_text()
    assert "Do not write plan Markdown directly" not in skill
    assert "Always create a feature folder" not in guide
    assert "planctl" in guide
    assert "plan-artifact-render.py" in guide


def test_default_dispatch_brief_is_bounded_and_retains_execution_boundaries():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/lib/framework-preamble.py"), str(ROOT)],
        capture_output=True, text=True, check=True,
    )
    assert len(result.stdout.split()) < 230
    assert "Read-only work never edits or commits" in result.stdout
    assert "Workers never push or farm sub-workers" in result.stdout
    assert "PROTOCOLS (" not in result.stdout
