#!/usr/bin/env python3
"""plan-index's filesystem fallback must DERIVE status, not read frontmatter.

`build_entry` runs only when the planctl read-model is unavailable. It used to
publish `fm['status']` verbatim. Almost no plan declares `status:` (6 of 60 live
master plans) because status is derived and `planctl stage` refuses to write it,
so a COMPLETED plan surfaced as `''`.

That is not cosmetic: `done_for()` in the milestone roll-up tests
`entry['status'] == 'done'` directly, so completed plans silently stopped
counting toward their milestone — no warning, just a low number. Caught by a
Codex cross-family review, which is also why the fix has a test.
"""
import importlib.util
import os

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")


def _plan_index():
    path = os.path.abspath(os.path.join(SCRIPTS, "plan-index.py"))
    spec = importlib.util.spec_from_file_location("plan_index_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _entry(fm, done, total):
    pi = _plan_index()
    info = {"ok_read": True, "fm": fm,
            "progress": {"done": done, "total": total,
                         "pct": int(100 * done / total) if total else 0}}
    return pi.build_entry("plans/app/x/00-master-plan.md", info)


def test_completed_plan_without_status_key_still_counts_as_done():
    """The regression: stage 6, every box checked, no `status:` declared."""
    e = _entry({"stage": 6, "repo": "app"}, 10, 10)
    assert e["status"] == "done", "milestone roll-up tests status == 'done'"
    assert e["derived_status"] == "done"
    assert not e.get("malformed"), "a status-less plan is not malformed"


def test_stage6_active_is_not_done_in_fallback():
    """The fallback must honour stage_state, or it re-introduces the very
    done-while-incomplete class this axis was added to remove."""
    e = _entry({"stage": 6, "repo": "app", "stage_state": "active"}, 5, 10)
    assert e["derived_status"] == "needs-review"
    assert e["status"] != "done"
    assert e["drift"] is True


def test_early_stage_still_derives_draft():
    """Guard the other direction — deriving must not make everything 'done'."""
    assert _entry({"stage": 1, "repo": "app"}, 0, 0)["derived_status"] == "draft"


def test_missing_required_key_still_flags_malformed():
    """`stage`/`repo` are declared truth and remain required."""
    assert _entry({"stage": 6}, 1, 1).get("malformed") is True
    assert _entry({"repo": "app"}, 1, 1).get("malformed") is True
