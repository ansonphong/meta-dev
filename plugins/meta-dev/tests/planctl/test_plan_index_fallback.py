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


def test_status_uses_legacy_vocabulary_like_the_primary_path():
    """`status` is the LEGACY 4-word field in BOTH paths; `derived_status` is
    the new one. The primary path mirrors it through _derive_legacy_status for
    the old render's GLYPH map and for --status filtering, so emitting a raw
    'needs-review' here would make the two paths disagree on the same plan.
    """
    e = _entry({"stage": 6, "repo": "app", "stage_state": "active"}, 5, 10)
    assert e["derived_status"] == "needs-review"   # new vocabulary
    assert e["status"] == "active"                 # legacy mirror
    blocked = _entry({"stage": 3, "repo": "app", "override": "blocked"}, 0, 5)
    assert blocked["status"] == "blocked"
    # done must survive the mapping unchanged — done_for() depends on it.
    assert _entry({"stage": 6, "repo": "app"}, 4, 4)["status"] == "done"


_PLAN_WITH_BY_EYE_GATE = """---
stage: 5
repo: app
---
## Tasks
- [x] `T1` build the thing
- [x] `T2` build the other thing
## Verify by eye
- [ ] `V1` check it by eye
"""


def _entry_from_text(text, fm):
    pi = _plan_index()
    info = {"ok_read": True, "fm": fm, "text": text,
            "progress": pi.count_checkboxes(text)}
    return pi.build_entry("plans/app/x/00-master-plan.md", info)


def test_fallback_derives_from_execution_only_counts():
    """Human-verify boxes must not enter the derive inputs.

    Raw counts here are 2/3, which derives 'executing'. Execution-only counts
    are 2/2, which derives 'needs-review'. Feeding raw totals reproduces the
    completed-is-not-done confusion the stage_state axis exists to remove, and
    makes the fallback disagree with the primary path on the same file.
    """
    e = _entry_from_text(_PLAN_WITH_BY_EYE_GATE, {"stage": 5, "repo": "app"})
    assert e["progress"]["done"] == 2 and e["progress"]["total"] == 3  # raw
    assert e["derived_status"] == "needs-review"                       # exec-only


def test_fallback_normalizes_stage_state():
    """Primary normalizes to lowercase/None; the fallback must match."""
    e = _entry_from_text(_PLAN_WITH_BY_EYE_GATE,
                         {"stage": 6, "repo": "app", "stage_state": "  ACTIVE "})
    assert e["stage_state"] == "active"
    e2 = _entry_from_text(_PLAN_WITH_BY_EYE_GATE, {"stage": 6, "repo": "app"})
    assert e2["stage_state"] is None


def test_undeclared_status_is_flagged_not_guessed_when_derivation_fails(monkeypatch):
    """A plan we cannot derive is marked unreliable rather than defaulted.

    Silently falling back to '' let such rows read as 'draft' and drop out of
    milestone math with no signal. Guessing from a stale declared status is
    worse: it launders an unknown into a plausible answer.
    """
    pi = _plan_index()
    import builtins
    real_import = builtins.__import__

    def _no_planctl(name, *a, **kw):
        if name == "planctl" or name.startswith("planctl."):
            raise ImportError("simulated: planctl unavailable")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", _no_planctl)
    info = {"ok_read": True, "fm": {"stage": 6, "repo": "app"},
            "text": _PLAN_WITH_BY_EYE_GATE, "progress": {"done": 2, "total": 3}}
    e = pi.build_entry("p", info)
    assert e.get("malformed") is True, "undeciderable row must be visible"
    assert e["derived_status"] == ""
