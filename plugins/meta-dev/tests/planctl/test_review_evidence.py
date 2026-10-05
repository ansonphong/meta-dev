"""Hermetic regression coverage for scoped, content-bound closing reviews."""
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from planctl import db, events, mutate, reconcile, review_evidence, stage


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), "-c", "user.name=Review Test",
                             "-c", "user.email=review@example.invalid", *args], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def reviewed_repo():
    root = Path(os.environ["META_DEV_ROOT"])
    root.mkdir()
    git(root, "init", "-q")
    (root / "src").mkdir()
    (root / "src/feature.py").write_text("VALUE = 1\n")
    plan = root / "plans/demo/feature/00-master-plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("---\nstage: 5\nrepo: demo\n---\n# Feature\n\n## Task Checklist\n"
                    "- [x] `T1.1` Implement contract\n\n## Acceptance\nOne scoped outcome.\n")
    git(root, "add", "--", "src/feature.py", "plans/demo/feature/00-master-plan.md")
    git(root, "commit", "-qm", "fixture")
    return root, plan


def capture(root, plan, scope=None):
    return review_evidence.capture(plan, root, scope or ["src/feature.py"], "HEAD", "HEAD")


def valid_verdict(root, scope=None):
    sha = git(root, "rev-parse", "HEAD")
    return {
        "verdict": "PASS", "confidence": 0.9, "blast_radius": "module",
        "dimensions": {name: "PASS" for name in review_evidence.DIMENSIONS},
        "issues": [], "summary": "Inspected complete scope and integration joins",
        "reviewed": {"base_ref": sha, "target_ref": sha,
                     "scope": scope if scope is not None else ["src/feature.py"],
                     "integration_reviewed": True},
    }


def review_args(root, plan, **overrides):
    verdict_file = root / "review-verdict.json"
    verdict_file.write_text(json.dumps(valid_verdict(root)))
    return SimpleNamespace(**{
        "plan": str(plan), "verdict": "pass", "by": "fixture-reviewer",
        "repo_root": str(root), "scope": ["src/feature.py"], "base_ref": "HEAD",
        "target_ref": "HEAD", "verdict_file": str(verdict_file), "json": True,
        **overrides,
    })


def test_cli_pass_requires_matching_structured_verdict(reviewed_repo):
    root, plan = reviewed_repo
    verdict_file = root / "review-verdict.json"
    verdict_file.write_text(json.dumps(valid_verdict(root)))
    sha = git(root, "rev-parse", "HEAD")
    run = subprocess.run([
        "bash", str(Path(__file__).resolve().parents[2] / "scripts/planctl.sh"),
        "review", str(plan), "pass", "--by", "fixture-reviewer",
        "--repo-root", str(root), "--base-ref", sha, "--target-ref", sha,
        "--scope", "src/feature.py", "--verdict-file", str(verdict_file), "--json",
    ], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["evidence"]["verdict_digest"] == review_evidence._digest(verdict_file.read_bytes())
    assert len(events.query(event="review_verdict")) == 1


@pytest.mark.parametrize("invalid", ["missing", "malformed", "contradictory", "fail",
                                    "batch", "wrong_ref", "wrong_scope", "partial"])
def test_cli_refuses_unbound_or_incomplete_pass_without_event(reviewed_repo, invalid):
    root, plan = reviewed_repo
    verdict_file = root / "review-verdict.json"
    verdict = valid_verdict(root)
    if invalid == "contradictory":
        verdict["dimensions"]["coverage"] = "NEEDS_REVIEW"
    elif invalid == "fail":
        verdict["verdict"] = "FAIL"
        verdict["dimensions"]["coverage"] = "NEEDS_REVIEW"
    elif invalid == "batch":
        verdict = {"reviews": [{**verdict, "target": "feature"}]}
    elif invalid == "wrong_ref":
        verdict["reviewed"]["target_ref"] = "0" * 40
    elif invalid == "wrong_scope":
        verdict["reviewed"]["scope"] = ["other.py"]
    elif invalid == "partial":
        verdict["reviewed"]["integration_reviewed"] = False
    verdict_file.write_text("{" if invalid == "malformed" else json.dumps(verdict))
    sha = git(root, "rev-parse", "HEAD")
    command = ["bash", str(Path(__file__).resolve().parents[2] / "scripts/planctl.sh"),
               "review", str(plan), "pass", "--repo-root", str(root),
               "--base-ref", sha, "--target-ref", sha, "--scope", "src/feature.py", "--json"]
    if invalid != "missing":
        command.extend(("--verdict-file", str(verdict_file)))
    run = subprocess.run(command, capture_output=True, text=True)
    assert run.returncode == 2
    assert "planctl review:" in run.stderr
    assert events.query(event="review_verdict") == []


def test_bound_review_survives_ledger_only_and_unrelated_commits(reviewed_repo):
    root, plan = reviewed_repo
    evidence = capture(root, plan)
    original_target = evidence["target_ref"]
    plan.write_text(plan.read_text().replace("stage: 5", "stage: 6\nstage_state: done").replace("- [x]", "- [ ]"))
    (root / "unrelated.txt").write_text("another outcome\n")
    git(root, "add", "--", "plans/demo/feature/00-master-plan.md", "unrelated.txt")
    git(root, "commit", "-qm", "ledger and unrelated work")
    assert git(root, "rev-parse", "HEAD") != original_target
    assert review_evidence.is_current(plan, evidence)


@pytest.mark.parametrize("change", ["source", "acceptance", "task", "deletion"])
def test_scope_or_plan_contract_change_invalidates_review(reviewed_repo, change):
    root, plan = reviewed_repo
    evidence = capture(root, plan)
    if change == "source":
        (root / "src/feature.py").write_text("VALUE = 2\n")
    elif change == "deletion":
        (root / "src/feature.py").unlink()
    elif change == "acceptance":
        plan.write_text(plan.read_text().replace("One scoped outcome.", "Different acceptance contract."))
    else:
        plan.write_text(plan.read_text() + "\n- [x] `T1.2` A new task\n")
    assert not review_evidence.is_current(plan, evidence)


def test_linked_phase_contract_change_invalidates_review(reviewed_repo):
    root, plan = reviewed_repo
    plan.write_text(plan.read_text() + "\n### Phase 1: Detail ([detail.md](detail.md))\n")
    detail = plan.parent / "detail.md"
    detail.write_text("# Phase 1\n### Task 1.1\nAccept this behavior.\n")
    evidence = capture(root, plan)
    detail.write_text(detail.read_text() + "New contract.\n")
    assert not review_evidence.is_current(plan, evidence)


@pytest.mark.parametrize("scope", [["src"], ["../escape.py"], ["/absolute.py"], ["src/missing.py"]])
def test_scope_must_be_exact_relevant_files(reviewed_repo, scope):
    root, plan = reviewed_repo
    with pytest.raises(ValueError):
        capture(root, plan, scope)


def test_capture_rejects_uncommitted_scope_and_unbound_pass(reviewed_repo, capsys):
    root, plan = reviewed_repo
    assert stage.cmd_review(review_args(root, plan, scope=[])) == 2
    assert "requires --scope" in capsys.readouterr().err
    assert events.query(event="review_verdict") == []
    (root / "src/feature.py").write_text("VALUE = 2\n")
    assert stage.cmd_review(review_args(root, plan)) == 2
    assert "differs from --target-ref" in capsys.readouterr().err
    assert events.query(event="review_verdict") == []


def test_deleted_file_is_bound_to_reviewed_deletion(reviewed_repo):
    root, plan = reviewed_repo
    base = git(root, "rev-parse", "HEAD")
    (root / "src/feature.py").unlink()
    git(root, "add", "--", "src/feature.py")
    git(root, "commit", "-qm", "delete scoped file")
    evidence = review_evidence.capture(plan, root, ["src/feature.py"], base, "HEAD")
    assert evidence["scope"][0]["mode"] == "missing"
    assert review_evidence.is_current(plan, evidence)
    (root / "src/feature.py").write_text("resurrected\n")
    assert not review_evidence.is_current(plan, evidence)


def test_directory_targets_resolve_for_stage_check_and_review(reviewed_repo, capsys):
    root, plan = reviewed_repo
    assert mutate._resolve_plan_arg(str(plan.parent))[1] == str(plan)
    assert stage.cmd_stage(SimpleNamespace(plan=str(plan.parent), stage="6", status="in_progress", json=True)) == 0
    assert "stage: 6" in plan.read_text()
    capsys.readouterr()
    assert stage.cmd_review(review_args(root, plan.parent)) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["plan"] == "plans/demo/feature/00-master-plan.md"
    assert result["evidence"]["target_ref"] == git(root, "rev-parse", "HEAD")
    assert reconcile._lookup_review_verdict(reconcile._build_review_cache(), result["plan"]) == "pass"


def test_legacy_unbound_pass_cannot_authorize_new_completion(reviewed_repo):
    _, plan = reviewed_repo
    rel = "plans/demo/feature/00-master-plan.md"
    assert reconcile._lookup_review_verdict({rel: ("pass", 1.0)}, rel) is None
    assert reconcile._lookup_review_verdict({rel: ("fail", 1.0)}, rel) == "fail"


def test_completed_bound_plan_reopens_after_scope_change(reviewed_repo, capsys):
    root, plan = reviewed_repo
    assert stage.cmd_review(review_args(root, plan)) == 0
    assert stage.cmd_stage(SimpleNamespace(plan=str(plan), stage="6", status="completed", json=True)) == 0
    cache = reconcile._build_review_cache()
    (root / "src/feature.py").write_text("VALUE = 3\n")
    conn = db.open_db()
    try:
        reconcile._reopen_stale_reviews(conn, str(root), cache, True)
    finally:
        conn.close()
    assert "stage_state: active" in plan.read_text()
    assert events.query(event="review_invalidated")


def test_no_historical_filename_exemption(reviewed_repo):
    _, plan = reviewed_repo
    renamed = plan.parent / "exec-order-2026-06-26.md"
    plan.rename(renamed)
    assert stage.cmd_stage(SimpleNamespace(plan=str(renamed), stage="4", status="completed", json=False)) == 0
    assert "stage: 4" in renamed.read_text()


def test_review_respects_git_filemode_policy(reviewed_repo):
    root, plan = reviewed_repo
    git(root, "config", "core.filemode", "false")
    source = root / "src/feature.py"
    source.chmod(source.stat().st_mode | 0o111)
    evidence = capture(root, plan)
    assert evidence["track_filemode"] is False
    assert review_evidence.is_current(plan, evidence)


def test_full_reconcile_refuses_legacy_pass_and_accepts_fresh_bound_pass(reviewed_repo, capsys):
    root, plan = reviewed_repo
    rel = "plans/demo/feature/00-master-plan.md"
    events.append({"event": "review_verdict", "plan": rel, "data": {"verdict": "pass", "by": "old"}})
    assert reconcile.cmd_reconcile(SimpleNamespace(json=True)) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["decisions"] == [{"plan": rel, "decision": "review_missing"}]
    assert stage.cmd_review(review_args(root, plan)) == 0
    capsys.readouterr()
    assert reconcile.cmd_reconcile(SimpleNamespace(json=True)) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["decisions"] == [{"plan": rel, "decision": "done", "runbook": None}]
    assert "stage_state: done" in plan.read_text()


def test_full_reconcile_reopens_completed_pass_for_dirty_scoped_code(reviewed_repo, capsys):
    root, plan = reviewed_repo
    assert stage.cmd_review(review_args(root, plan)) == 0
    assert stage.cmd_stage(SimpleNamespace(plan=str(plan), stage="6", status="completed", json=True)) == 0
    capsys.readouterr()
    (root / "src/feature.py").write_text("VALUE = 9\n")
    assert reconcile.cmd_reconcile(SimpleNamespace(json=True)) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["decisions"] == [{"plan": "plans/demo/feature/00-master-plan.md", "decision": "review_missing"}]
    assert "stage_state: active" in plan.read_text()
