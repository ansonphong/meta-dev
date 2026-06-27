#!/usr/bin/env bash
set -euo pipefail
# PostToolUse hook: fires after Edit/Write/MultiEdit tool calls.
# Matcher: Edit|Write|MultiEdit in plugin.json.
# Input: JSON payload on stdin — { tool_name, tool_input:{file_path,...}, ... }
#
# Plan-edit VALIDATION lives in plan-validate.sh. Plan stage/status is read live
# from YAML frontmatter via plan-index.py — never from the event log — so we do
# NOT emit a plan_edit event on every edit (that bloated state.events.jsonl with
# no-op rows the dashboard never read). We append a plan_edit event ONLY when an
# overlord is actively watching this plan, because meta-overlord's event-driven
# mode tails events.jsonl for plan_edit to trigger its review cycle. No overlord
# watching → no event → no bloat.

PAYLOAD=$(cat)
PATH_EDITED=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.file_path // ""')
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-.}"

case "$PATH_EDITED" in
  *plans/*plan*.md)
    OVERLORD_WATCHING=$(bash "$PLUGIN_ROOT/scripts/state-read.sh" overlord.watching 2>/dev/null || echo "")
    if [ -n "$OVERLORD_WATCHING" ] && [ "$OVERLORD_WATCHING" != "null" ]; then
      case "$PATH_EDITED" in
        *"$OVERLORD_WATCHING"*)
          # Feed the overlord's event-driven loop (events.jsonl tail) + console signal.
          bash "$PLUGIN_ROOT/scripts/state-append.sh" \
            "{\"event\":\"plan_edit\",\"plan\":\"$PATH_EDITED\"}" 2>/dev/null || true
          echo "meta-dev: overlord trigger — plan edited ($(basename "$PATH_EDITED")), review queued"
          ;;
      esac
    fi
    ;;
esac
