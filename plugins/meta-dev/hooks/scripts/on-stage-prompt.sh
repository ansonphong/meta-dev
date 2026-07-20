#!/usr/bin/env bash
set -uo pipefail
# UserPromptSubmit hook: fires when the user submits a prompt.
# Input: JSON payload on stdin — { prompt, session_id, cwd, ... }
#
# Two independent jobs, in order:
#
# 1. AUTONOMOUS MODE — if the prompt carries `--autonomous` anywhere, inject the
#    autonomous contract as additionalContext. This is what makes the flag work
#    across ALL commands: meta-dev has no central argument parser (each command's
#    markdown parses its own flags), so a per-command flag would have meant
#    editing ~67 files and would STILL miss bare prompts. The hook sees the raw
#    prompt before anything dispatches, so one place covers every entry point.
#
# 2. STAGE EMIT — when the prompt invokes a waterfall STAGE command, durably emit
#    a stage_transition(in_progress) so /meta-dashboard flips that plan's stage
#    the instant the command is submitted, independent of whether the model later
#    runs stage-emit.sh itself. (Completion stays instruction-based — a semantic
#    judgment no hook can make.)
#
#    Stage commands matched (+ aliases): /meta-planner|/planner → plan,
#      /meta-loop-gap|/loop-gap → harden, /meta-execute → execute,
#      /meta-eval → review.
#
# Fire-and-forget: NEVER block the prompt, never error out. `set -e` is
# deliberately NOT set — an abort partway through would silently swallow the
# injection in (3) after (1) had already decided to emit it.

PAYLOAD=$(cat)
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-.}"
CONTEXT=""

PROMPT=$(printf '%s' "$PAYLOAD" | jq -r '.prompt // ""' 2>/dev/null || echo "")
[ -z "$PROMPT" ] && exit 0

# ── 1. Autonomous mode ────────────────────────────────────────────────────
# Whole-token match, so `--autonomously` or a path fragment cannot trip it.
if printf '%s' "$PROMPT" | grep -qiE '(^|[[:space:]])--autonomous([[:space:]]|$)' 2>/dev/null; then
  CONTEXT=$(cat <<'AUTOEOF'
⟡ AUTONOMOUS MODE ENGAGED — `--autonomous` is present in this prompt.

It means one thing: **run to the end, do not wake the user.** They have
pre-authorized this run and left. `--autonomous` IS the explicit Stage-5
permission — it authorizes execution exactly as "go" or `--to 6` does. It
implies cruise mode, `--gate none`, and `--no-pause`; do not ask for those too.

RESOLVE EVERY AMBIGUITY TOWARD "keep going and report in the morning."
- Do NOT ask "proceed?", "ready?", "shall I dispatch?" — the flag is the GO.
- Do NOT stop between stages, phases, or tasks for confirmation.
- A judgment call you would otherwise ask about goes to `fable-consult` FIRST:
  bash ${CLAUDE_PLUGIN_ROOT}/scripts/fable-consult.sh --question "..." --autonomous
  exit 0=adopt · 10/11=escalate · 12=defer(REVIEW-ME) · 2=error→escalate.
- Gates needing human eyes are DEFERRED to a punch list, never asked mid-run.

THE HARD FLOOR — `--autonomous` buys *unattended*, never *unsafe*. None of
these is a question about the user's preference; each is a thing that cannot be
undone in the morning. They hold exactly as they always do:
  1. Guard-hook denies + every git ban (rebase/stash/amend/force-push/tree-wide add).
  2. No deploy, ship, publish, release, or real migration. Prepare, then stop.
  3. The fable-consult veto list — destructive, security, money-path, schema,
     cross-repo contract, spend-or-send, scope expansion → park the subject.
  4. Human-verify boxes (`by eye`/`by hand`/`gpu`/`manual`) stay UNCHECKED.
     NEVER pass `--human` to planctl. Flipping the user's own smoke test while
     they sleep forges a verification rather than automating one. Defer it.
  5. TRUE BLOCKERs still halt — but they park THAT SUBJECT ONLY and the run
     continues elsewhere. Halting is not the same as asking.

CLOSE WITH THE AUTONOMOUS RUN REPORT — landed / decided (with Fable's real
confidences) / parked / your-eyes punch list / residual risk. The user was
asleep; this report is the entire record of the night, so it must be honest.
A red test says red. A skipped step says skipped.

Full contract: meta-dev `references/autonomous-mode.md`.
Consult contract + calibration guard: skill `fable-consult`.
AUTOEOF
)
fi

# ── 2. Stage emit ─────────────────────────────────────────────────────────
# Identify the leading slash command (allow leading whitespace).
CMD=$(printf '%s' "$PROMPT" | grep -oiE '^[[:space:]]*/(meta-)?(planner|loop-gap|loopgap|execute|eval)([[:space:]]|$)' 2>/dev/null | tr -d '[:space:]/' | sed 's/^meta-//' || true)

if [ -n "$CMD" ]; then
  STAGE=""
  case "$CMD" in
    planner)           STAGE=plan ;;
    loop-gap|loopgap)  STAGE=harden ;;
    execute)           STAGE=execute ;;
    eval)              STAGE=review ;;
  esac

  # Extract the first arg that looks like a plan path (must reference plans/).
  # If we can't identify a plan, no-op safely — the instruction-based emit and
  # the conductor-emit still cover those cases.
  PLAN=$(printf '%s' "$PROMPT" \
    | sed -E 's#^[[:space:]]*/[a-zA-Z-]+[[:space:]]+##' \
    | grep -oE '[^[:space:]]*plans/[^[:space:]]+' 2>/dev/null | head -1 || true)

  # Fire-and-forget — a dashboard emit must never disrupt the user's command.
  if [ -n "$STAGE" ] && [ -n "$PLAN" ]; then
    bash "$PLUGIN_ROOT/scripts/stage-emit.sh" "$PLAN" "$STAGE" in_progress >/dev/null 2>&1 || true
  fi
fi

# ── 3. Emit injected context, if any ──────────────────────────────────────
if [ -n "$CONTEXT" ]; then
  jq -nc --arg ctx "$CONTEXT" \
    '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$ctx}}' \
    2>/dev/null || printf '%s\n' "$CONTEXT"
fi
exit 0
