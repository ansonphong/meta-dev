#!/usr/bin/env python3
"""derive.py — THE ONE status interpreter (invariant I2).

Every consumer imports/queries status from here — ``status:`` is never typed
again; it is computed from declared ``stage`` + EXECUTION-only checkbox counts +
``override``. The derivation golden table
(``tests/planctl/test_derive.py``, design §10 item 1) regression-locks the
``completed != done`` class that today reads 0% on the control plane.

``DERIVE_V`` is the rule-version constant callers pass into ``db.is_stale``; v2
makes stage-6 derivation ``stage_state``-aware. Bump it on ANY rule change so a
full sync rebuilds the index under the current semantics.
``db.py`` deliberately does NOT import this module (cycle avoidance) — callers
wire ``DERIVE_V`` in by hand: ``db.is_stale(conn, derive.DERIVE_V)``.

Stdlib only.
"""

DERIVE_V = 2

# Derived vocabulary (canon, closed — design §3.2).
PLAN_STATUSES = ("draft", "ready", "executing", "needs-review", "done")
OVERRIDES = ("blocked", "parked", "superseded")

# Glyph map (design §3.2). Non-canon status → '?' via glyph() (never KeyError).
GLYPHS = {
    "draft": "◦",
    "ready": "▹",
    "executing": "→",
    "needs-review": "⊙",
    "done": "✓",
    "blocked": "!",
    "parked": "‖",
    "superseded": "⌀",
}


# Emoji vocabulary for RENDERED-MARKDOWN surfaces (the runbook progress block),
# where colour makes a 30-row table scannable at a glance. The GLYPHS above stay
# the vocabulary for terminal/box views: emoji are double-width and would break
# the fixed-cell layouts.
EMOJI = {
    "draft": "📝",
    "ready": "▶️",
    "executing": "🔄",
    "needs-review": "👀",
    "done": "✅",
    "blocked": "⛔",
    "parked": "⏸️",
    "superseded": "🚫",
}
EMOJI_MISSING = "❌"


def emoji(status, drift=False):
    """Emoji counterpart of ``glyph`` — same precedence, same non-canon safety.

    ``done`` with ``drift`` → ``'✅⚠️'`` (declared done with open work; the warning
    must survive into every rendered view). Unknown status → ``'❔'``, never a
    ``KeyError``."""
    if status == "done" and drift:
        return "✅⚠️"
    return EMOJI.get(status, "❔")


def glyph(status, drift=False):
    """Render the glyph for a derived status.

    ``done`` with ``drift`` → ``'✓⚠'`` (declared-done-with-open-work, rendered
    loudly in every view). A non-canon status (e.g. a hand-edited bogus override
    that slipped past parse) → ``'?'`` — NEVER a ``KeyError`` (G0b-6 read-side)."""
    if status == "done" and drift:
        return "✓⚠"
    return GLYPHS.get(status, "?")


def pct(done, total):
    """Banker's-round percentage — ``round(100*done/total)``, ``0`` when
    ``total==0`` (R3/VC-3).

    Parity-bound to ``plan-index.py:154`` (``round(100*done/total)``) and
    ``runbook-render.py``; ``int()`` truncation breaks parity (``done=2,total=3``
    → ``67``, not ``66``)."""
    if not total:
        return 0
    return round(100 * done / total)


def derive_plan(fm, tasks_done, tasks_total):
    """Derive ``(status, drift)`` for a PLAN — design §3.2 precedence, EXACTLY.

    Inputs are EXECUTION-only counts (human-verify boxes NEVER enter here — they
    are tracked as ``human_open``/``human_total`` by the caller, R2/VC-1).
    ``fm`` is the parsed frontmatter dict (``override``, ``stage``).

    Precedence:
      1. ``override`` present            → ``(override_value, False)``
         (caller shows ``note``; drift suppressed).
      2. ``stage >= 6``                  → ``('done', drift)`` where
         ``drift = tasks_done < tasks_total`` (open EXECUTION boxes remain) —
         UNLESS ``stage_state == 'active'``, which means the review itself is
         still running and derives ``('needs-review', drift)``. An ABSENT
         ``stage_state`` is legacy-equivalent to ``done`` (no migration).
      3. ``tasks_total>0 and tasks_done==tasks_total``
                                         → ``('needs-review', False)``
         (execution work complete at stage <6 — a human-only-open plan at stage 5
         still hits this; G0b-2).
      4. ``tasks_done > 0``              → ``('executing', False)``.
      5. ``stage in 3..5``               → ``('ready', False)``.
      6. ``stage <= 2``                  → ``('draft', False)``.

    ``exec_total == 0`` (a human-only / review-only plan) derives ``ready``
    indefinitely — ACCEPTED (VC-ACK: nothing to execute).
    """
    fm = fm or {}
    try:
        stage = int(fm.get("stage", 0))
    except (ValueError, TypeError):
        stage = 0
    override = fm.get("override")

    # 1. override wins; drift suppressed.
    if override:
        return override, False
    # 2. stage >= 6 -> done, UNLESS the review is still actively running.
    #    stage_state ABSENT means legacy semantics (== done) so no live plan
    #    file needs migrating; only an explicit "active" changes the outcome.
    if stage >= 6:
        if str(fm.get("stage_state", "")).strip().lower() == "active":
            return "needs-review", tasks_done < tasks_total
        return "done", tasks_done < tasks_total
    # 3. all EXEC done at stage <6 -> needs-review (rule-3 beats rule-5).
    if tasks_total > 0 and tasks_done == tasks_total:
        return "needs-review", False
    # 4. some EXEC done -> executing.
    if tasks_done > 0:
        return "executing", False
    # 5. planned/hardened, no boxes flipped -> ready.
    if 3 <= stage <= 5:
        return "ready", False
    # 6. otherwise -> draft.
    return "draft", False


# ── runbook rollup (pure aggregation; the recursive CTE lives in runbook.py/0e) ─
def rollup(child_results):
    """Pure aggregation over a runbook's DIRECT member results (design §3.2/§4).

    Each ``child_result`` is a pre-computed dict (the recursive CTE in
    ``runbook.py``/0e produces these bottom-up; this function is the pure
    aggregation layer the CTE calls at each level):

      ``{'path', 'kind': 'plan'|'runbook', 'done': bool, 'overridden': bool,
         'effective_stage': int|None, 'tasks_done': int, 'tasks_total': int,
         'now': str|None}``

    Pinned (R4/VC-4):
      * ``members_done``/``members_total`` — DIRECT members only (a nested runbook
        is **1 unit** whose done ≡ its derived done).
      * ``tasks_done``/``tasks_total`` — sum over children's leaf-exec counts
        (DISTINCT dedup on diamond memberships is realized by the 0e recursive
        CTE; children arrive here pre-deduped).
      * ``effective_stage`` — ``min`` over non-done AND non-overridden members,
        recursing on each nested member's EFFECTIVE stage (a blocked member drags
        the min, so overrides exclude it).
      * ``now`` — first non-done, non-blocked member's ``now`` (member order);
        DESCENDS into a nested runbook to its leaf ``now``.
      * empty runbook (0 members) → ``0/0`` (caller renders ``'—'``, never 100%).

    Returns a dict with the above plus advisory ``status``/``drift`` (a runbook's
    STATUS is computed-on-read in 0e, never stored — §4).
    """
    members_total = len(child_results)
    if members_total == 0:
        return {
            "members_done": 0, "members_total": 0,
            "tasks_done": 0, "tasks_total": 0,
            "effective_stage": None, "now": None,
            "status": None, "drift": False,
        }

    members_done = sum(1 for c in child_results if c.get("done"))
    tasks_done = sum(int(c.get("tasks_done", 0)) for c in child_results)
    tasks_total = sum(int(c.get("tasks_total", 0)) for c in child_results)

    stages = [
        int(c["effective_stage"])
        for c in child_results
        if not c.get("done") and not c.get("overridden")
        and c.get("effective_stage") is not None
    ]
    effective_stage = min(stages) if stages else None

    now = None
    for c in child_results:
        if c.get("done") or c.get("overridden"):
            continue
        if c.get("now"):
            now = c["now"]
            break

    status, drift = _derive_runbook_status(
        members_done, members_total, tasks_done, tasks_total, effective_stage)
    return {
        "members_done": members_done, "members_total": members_total,
        "tasks_done": tasks_done, "tasks_total": tasks_total,
        "effective_stage": effective_stage, "now": now,
        "status": status, "drift": drift,
    }


def _derive_runbook_status(members_done, members_total, tasks_done, tasks_total,
                           effective_stage):
    """Advisory runbook status from the member rollup.

    The authoritative runbook status is computed-on-read in 0e (§4); this gives
    rollup consumers a reasonable status without a second pass. Same precedence
    family as ``derive_plan`` (override-less): all-members-done → done; else
    leaf-exec-derived."""
    if members_total > 0 and members_done == members_total:
        return "done", tasks_done < tasks_total
    if effective_stage is not None and effective_stage >= 6:
        return "done", tasks_done < tasks_total
    if tasks_total > 0 and tasks_done == tasks_total:
        return "needs-review", False
    if tasks_done > 0:
        return "executing", False
    return "ready", False


def derive_runbook(members, child_results):
    """Derive a runbook's rollup from its ordered member list + pre-computed
    child results.

    ``members`` is the ordered member-path list (ledger order); ``child_results``
    is the matching list of per-member result dicts (see ``rollup``). The
    recursive descent + DISTINCT diamond-dedup + cycle guard live in
    ``runbook.py``/0e's recursive CTE — this is the pure aggregation entry point
    it calls once child results are resolved bottom-up.
    """
    return rollup(child_results)
