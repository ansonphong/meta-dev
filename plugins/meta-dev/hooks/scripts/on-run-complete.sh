#!/usr/bin/env bash
# on-run-complete.sh — Stop hook. Deterministically enforces DONE at end-of-run.
#
# PRIME DIRECTIVE: after any execution run, the plan MUST read 100% DONE on the
# dashboard automatically (no human step), or the run MUST FAIL LOUDLY.
#
# Delegates to ``planctl reconcile`` (M3b — the responsiveness fix). The DONE-gate
# decision matrix is preserved verbatim — it reads the SQLite index instead of
# re-walking the tree with inline python. Budget <1s typical.
#
# FIRE MODEL: planctl reconcile runs sync → DONE-gate-as-SQL → render only dirty
# runbooks. The 5 outcome classes are unchanged:
#   (A) clean + reviewed         → stamp stage 6 + render runbook + done_gate
#   (B) clean + no review        → review_missing event (no stamp)
#   (C) docs evidence missing     → docs_missing event (no stamp)
#   (D) open boxes + drift       → FAIL LOUD (fail_open_boxes event)
#   (E) open + executing/blocked → no-op (run alive)
#
# THREE INVARIANTS survive this rewrite (non-negotiable):
#   1. stop_hook_active re-entry guard
#   2. exit 0 ALWAYS — a planctl crash/cold DB/missing binary NEVER blocks a run
#   3. CLAUDE_PROJECT_DIR fallback-walk for root resolution
#
# Codex finding #12 (fixed): if planctl fails, surface ONE concise warning line
# (exit code + truncated stderr) through stderr. Non-blocking, non-silent.
set -uo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -z "$PLUGIN_ROOT" ] && PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- Invariant 1: re-entry guard (never run inside another stop-hook pass). ---
PAYLOAD="$(cat 2>/dev/null || true)"
if printf '%s' "$PAYLOAD" | python3 -c 'import json,sys; sys.exit(0 if json.loads(sys.stdin.read() or "{}").get("stop_hook_active") else 1)' 2>/dev/null; then
  exit 0
fi

# --- Invariant 3: resolve the project root cwd-INDEPENDENTLY. -------------------
PROJECT_ROOT=""
if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && [ -d "${CLAUDE_PROJECT_DIR}/plans" ]; then
  PROJECT_ROOT="$CLAUDE_PROJECT_DIR"
else
  _d="$(pwd)"
  while [ -n "$_d" ] && [ "$_d" != "/" ]; do
    if [ -d "$_d/plans" ]; then PROJECT_ROOT="$_d"; break; fi
    _d="$(dirname "$_d")"
  done
fi
[ -z "$PROJECT_ROOT" ] && exit 0
cd "$PROJECT_ROOT" || exit 0
[ -d "plans" ] || exit 0

# --- Call planctl reconcile (the entire DONE-gate + runbook render pass). -------
# planctl's statedir.project_root() resolves CLAUDE_PROJECT_DIR independently,
# so we pass the PROJECT_ROOT in case planctl.sh needs the cwd context.
PLANCTL="$PLUGIN_ROOT/scripts/planctl.sh"
# NOTE: existence only — NOT -x. It is invoked via `bash "$PLANCTL"`, which
# needs no exec bit, and requiring one turns a lost mode bit (fresh clone, 9p
# remount, archive extract) into a SILENT total no-op of the DONE gate.
if [ ! -f "$PLANCTL" ]; then
  # planctl not available — silent exit (invariant 2: never block)
  exit 0
fi

# Capture both stdout and stderr so we can surface a warning on failure.
# Fire-and-forget: || true ensures exit 0 always (invariant 2).
#
# Hard timeout: this tree runs 4-20 concurrent workers, so a reconcile can block
# on a contended SQLite writer lock. Without a bound, the Stop hook stalls every
# session until the harness timeout. 15s leaves headroom under the 20s budget.
# Degrade gracefully if coreutils `timeout` is unavailable.
if command -v timeout >/dev/null 2>&1; then
  PLANCTL_CMD=(timeout 15 bash "$PLANCTL" reconcile)
else
  PLANCTL_CMD=(bash "$PLANCTL" reconcile)
fi
set +e
PLANCTL_OUT="$("${PLANCTL_CMD[@]}" 2>&1)"
PLANCTL_RC=$?
set -e

# --- Invariant 2: exit 0 ALWAYS. A failure must never block the run. -----------
# Codex finding #12: non-blocking AND non-silent. On failure, surface ONE
# concise warning line with the exit code and truncated stderr.
if [ "$PLANCTL_RC" -ne 0 ]; then
  WARN_LINE="$(printf '%s' "$PLANCTL_OUT" | head -1 | cut -c1-200)"
  printf '[meta-dev] planctl reconcile failed (exit %d): %s\n' \
    "$PLANCTL_RC" "$WARN_LINE" >&2
  exit 0
fi

# Normal output: let planctl's human-readable summary flow to stdout.
if [ -n "$PLANCTL_OUT" ]; then
  printf '%s\n' "$PLANCTL_OUT"
fi

exit 0
