#!/usr/bin/env bash
set -euo pipefail
# PostToolUse hook: fires after Edit/Write/MultiEdit tool calls.
# Matcher: Edit|Write|MultiEdit in plugin.json.
# Input: JSON payload on stdin — { tool_name, tool_input:{file_path,...}, ... }
#
# Two independent passes:
#   (a) OVERLORD WATCH: on ``*plans/*plan*.md`` edits, emit a ``plan_edit``
#       event when the overlord is actively watching the path (event-driven
#       review cycle). Narrow — ``_runbook-*.md`` and ``meta-runbook.md`` are
#       excluded by design.
#   (b) SINGLE-FILE SYNC (M3b): on ALL ``plans/**`` edits (plans/runbooks/
#       ledgers), sync the index via ``planctl sync --file <F>`` (~10-30ms) so
#       the read-model stays hot. Fire-and-forget — a sync failure never blocks
#       the edit. Non-plan files early-exit both passes.
#
# Plan-edit VALIDATION lives in plan-validate.sh (separate hook — fires on
# Edit only, not Write/MultiEdit).

PAYLOAD=$(cat)
PATH_EDITED=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.file_path // ""')
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-.}"

# Non-plan files → early-exit (W3B-4: PostToolUse budget covers 2 python
# spawns; the sync only fires for plan-path edits).
#
# MUST accept ABSOLUTE paths: Claude Code sends tool_input.file_path as an
# absolute path (/mnt/d/…/plans/meta/foo.md), never repo-relative. A bare
# ``plans/*`` gate rejects every real payload — which silently disables BOTH
# passes below (the M3b sync AND the pre-existing overlord plan_edit event).
# The ``*/plans/*`` arm mirrors the leading-``*`` convention the overlord
# matcher below already relies on for exactly this reason.
case "$PATH_EDITED" in
  plans/*|*/plans/*)
    ;;
  *)
    exit 0
    ;;
esac

# ── (b) Single-file sync — keep the index hot (~10-30ms). ─────────────────
# Separate from the overlord case (W1-D4): the old matcher ``*plan*.md`` never
# matched ``_runbook-*.md`` or ``meta-runbook.md``, so sync would silently
# skip runbooks/ledgers. ``plans/**`` catches them all.
# Fire-and-forget: ``|| true`` so a sync failure never blocks the edit.
if [ -f "$PLUGIN_ROOT/scripts/planctl.sh" ]; then
  bash "$PLUGIN_ROOT/scripts/planctl.sh" sync --file "$PATH_EDITED" >/dev/null 2>&1 || true
fi

# ── (a) Overlord watch — narrow ``*plan*.md`` matcher. ─────────────────────
case "$PATH_EDITED" in
  *plans/*plan*.md)
    OVERLORD_WATCHING=$(bash "$PLUGIN_ROOT/scripts/state-read.sh" overlord.watching 2>/dev/null || echo "")
    if [ -n "$OVERLORD_WATCHING" ] && [ "$OVERLORD_WATCHING" != "null" ]; then
      case "$PATH_EDITED" in
        *"$OVERLORD_WATCHING"*)
          bash "$PLUGIN_ROOT/scripts/state-append.sh" \
            "{\"event\":\"plan_edit\",\"plan\":\"$PATH_EDITED\"}" 2>/dev/null || true
          echo "meta-dev: overlord trigger — plan edited ($(basename "$PATH_EDITED")), review queued"
          ;;
      esac
    fi
    ;;
esac
