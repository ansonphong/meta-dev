"""Focused contracts for the deterministic archive gate."""

from __future__ import annotations

from pathlib import Path
import subprocess


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
GUARD = PLUGIN_ROOT / "scripts" / "archive-guard.sh"


def _plan(
    tmp_path: Path,
    *,
    stage: int = 6,
    stage_state: str = "done",
    body: str = "- [x] #a1b2 `T1.1` Complete the work\n",
    override: str | None = None,
) -> Path:
    project = tmp_path / "project"
    plan = project / "plans" / "app" / "fixture.md"
    plan.parent.mkdir(parents=True)
    frontmatter = ["---", f"stage: {stage}", f"stage_state: {stage_state}", "repo: app"]
    if override:
        frontmatter.append(f"override: {override}")
    frontmatter.extend(["context: none", "docs: none", "---", "", "# Fixture", ""])
    plan.write_text("\n".join(frontmatter) + body, encoding="utf-8")
    (project / "plans" / "meta-runbook.md").write_text(
        "# Runbook\n\n## Sequence\n\n## Residual\n", encoding="utf-8"
    )
    return plan


def _run(plan: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(GUARD), str(plan)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_passes_derived_done_without_typed_status_and_ignores_prose(tmp_path: Path):
    plan = _plan(
        tmp_path,
        body=(
            "- [x] #a1b2 `T1.1` Complete the work\n\n"
            "Every claimed live symbol is in the anchor table.\n"
            "## Render in progress panel\n"
            "### Task 2: [x] Explain the WIP lifecycle\n"
        ),
    )

    result = _run(plan)

    assert result.returncode == 0
    assert result.stdout == "PASS\n"


def test_blocks_derived_non_done_and_override_states(tmp_path: Path):
    active = _run(_plan(tmp_path / "active", stage_state="active"))
    parked = _run(_plan(tmp_path / "parked", override="parked"))

    assert active.returncode == 1
    assert "derived status is 'needs-review', not done" in active.stdout
    assert parked.returncode == 1
    assert "derived status is 'parked', not done" in parked.stdout


def test_blocks_unchecked_tasks_and_explicit_claim_markers(tmp_path: Path):
    unchecked = _run(
        _plan(tmp_path / "unchecked", body="- [ ] #a1b2 `T1.1` Finish the work\n")
    )
    claimed = _run(
        _plan(
            tmp_path / "claimed",
            body="- [x] #a1b2 `T1.1` CLAIMED Finish the work\n",
        )
    )
    legacy_heading = _run(
        _plan(
            tmp_path / "legacy-heading",
            body="### Task 2: [ ] `CLAIMED` Finish the work\n",
        )
    )
    state_line = _run(
        _plan(
            tmp_path / "state-line",
            body="- [x] #a1b2 `T1.1` Complete the work\n\n**Status:** in progress\n",
        )
    )
    alpha_handle = _run(
        _plan(
            tmp_path / "alpha-handle",
            body="- [x] #a1b2 `TA.1` CLAIMED Finish the work\n",
        )
    )
    mixed_handle = _run(
        _plan(
            tmp_path / "mixed-handle",
            body="- [x] #a1b2 `T4b.2` CLAIMED Finish the work\n",
        )
    )

    assert unchecked.returncode == 1
    assert "unchecked checkbox(es)" in unchecked.stdout
    assert claimed.returncode == 1
    assert "active-work marker" in claimed.stdout
    assert legacy_heading.returncode == 1
    assert "active-work marker" in legacy_heading.stdout
    assert state_line.returncode == 1
    assert "active-work marker" in state_line.stdout
    assert alpha_handle.returncode == 1
    assert "active-work marker" in alpha_handle.stdout
    assert mixed_handle.returncode == 1
    assert "active-work marker" in mixed_handle.stdout


def test_blocks_plan_listed_in_live_sequence(tmp_path: Path):
    plan = _plan(tmp_path)
    project = plan.parents[2]
    (project / "plans" / "meta-runbook.md").write_text(
        "# Runbook\n\n## Sequence\n"
        "plans/app/fixture.md\n\n## Residual\n",
        encoding="utf-8",
    )

    result = _run(plan)

    assert result.returncode == 1
    assert "listed active in meta-runbook.md" in result.stdout


def test_blocks_bulleted_plan_listed_in_live_sequence(tmp_path: Path):
    for name, bullet in (("dash", "- "), ("star", "* "), ("numeric", "1. ")):
        plan = _plan(tmp_path / name)
        project = plan.parents[2]
        (project / "plans" / "meta-runbook.md").write_text(
            "# Runbook\n\n## Sequence\n"
            f"{bullet}plans/app/fixture.md\n\n## Residual\n",
            encoding="utf-8",
        )

        result = _run(plan)

        assert result.returncode == 1
        assert "listed active in meta-runbook.md" in result.stdout


def test_blocks_when_live_ledger_is_missing(tmp_path: Path):
    plan = _plan(tmp_path)
    project = plan.parents[2]
    (project / "plans" / "meta-runbook.md").unlink()

    result = _run(plan)

    assert result.returncode == 1
    assert "cannot inspect meta-runbook.md Sequence" in result.stdout


def test_blocks_when_live_ledger_has_no_sequence_section(tmp_path: Path):
    plan = _plan(tmp_path)
    project = plan.parents[2]
    (project / "plans" / "meta-runbook.md").write_text(
        "# Runbook\n\n## Residual\n", encoding="utf-8"
    )

    result = _run(plan)

    assert result.returncode == 1
    assert "no readable `## Sequence` section" in result.stdout


def test_blocks_plan_outside_a_plans_tree(tmp_path: Path):
    plan = tmp_path / "fixture.md"
    plan.write_text(
        "---\nstage: 6\nstage_state: done\nrepo: app\n---\n"
        "- [x] #a1b2 `T1.1` Complete the work\n",
        encoding="utf-8",
    )

    result = _run(plan)

    assert result.returncode == 1
    assert "not inside a plans directory" in result.stdout
