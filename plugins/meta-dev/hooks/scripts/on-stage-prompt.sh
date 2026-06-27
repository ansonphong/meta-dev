#!/usr/bin/env bash
set -euo pipefail
# UserPromptSubmit hook: fires when the user submits a prompt.
# Input: JSON payload on stdin — { prompt, session_id, cwd, ... }
#
# When the prompt invokes a waterfall STAGE command, durably emit a
# stage_transition(in_progress) so /meta-dashboard flips that plan's stage the
# instant the command is submitted — independent of whether the model later
# runs stage-emit.sh itself. This hardens the START of a stage for typed
# commands (completion stays instruction-based — it's a semantic judgment no
# hook can make). Fire-and-forget: NEVER block the prompt, never error out.
#
# Stage commands matched (+ aliases): /meta-planner|/planner → plan,
#   /meta-loop-gap|/loop-gap → harden, /meta-execute → execute,
#   /meta-eval → review.

PAYLOAD=$(cat)
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-.}"

PROMPT=$(printf '%s' "$PAYLOAD" | jq -r '.prompt // ""' 2>/dev/null || echo "")
[ -z "$PROMPT" ] && exit 0

# Identify the leading slash command (allow leading whitespace).
CMD=$(printf '%s' "$PROMPT" | grep -oiE '^[[:space:]]*/(meta-)?(planner|loop-gap|loopgap|execute|eval)([[:space:]]|$)' 2>/dev/null | tr -d '[:space:]/' | sed 's/^meta-//' || true)
[ -z "$CMD" ] && exit 0

case "$CMD" in
  planner)           STAGE=plan ;;
  loop-gap|loopgap)  STAGE=harden ;;
  execute)           STAGE=execute ;;
  eval)              STAGE=review ;;
  *)                 exit 0 ;;
esac

# Extract the first arg that looks like a plan path (must reference plans/).
# If we can't identify a plan, no-op safely — the instruction-based emit and
# the conductor-emit still cover those cases.
PLAN=$(printf '%s' "$PROMPT" \
  | sed -E 's#^[[:space:]]*/[a-zA-Z-]+[[:space:]]+##' \
  | grep -oE '[^[:space:]]*plans/[^[:space:]]+' 2>/dev/null | head -1 || true)
[ -z "$PLAN" ] && exit 0

# Fire-and-forget — a dashboard emit must never disrupt the user's command.
bash "$PLUGIN_ROOT/scripts/stage-emit.sh" "$PLAN" "$STAGE" in_progress >/dev/null 2>&1 || true
exit 0
