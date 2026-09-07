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
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="${META_DEV_PLUGIN_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}}}"
CONTEXT=""

PROMPT=$(printf '%s' "$PAYLOAD" | jq -r '.prompt // ""' 2>/dev/null || echo "")
[ -z "$PROMPT" ] && exit 0

# ── 1. Autonomous mode ────────────────────────────────────────────────────
# Whole-token match, so `--autonomously` or a path fragment cannot trip it.
if printf '%s' "$PROMPT" | grep -qiE '(^|[[:space:]])--autonomous([[:space:]]|$)' 2>/dev/null; then
  CONTEXT=$(cat <<'AUTOEOF'
⟡ AUTONOMOUS MODE ENGAGED — `--autonomous` is present in this prompt.

Continue unattended within the selected task's existing scope. Classify that
task first: an audit, review, diagnosis, explanation, or plan stays read-only.
The flag does not authorize implementation of findings, external services, or
scope expansion. It supplies Stage-5 permission only for a scoped implementation
request. Neither `--autonomous` nor a stage ceiling turns read-only work into edits.

It implies cruise mode, `--gate none`, and `--no-pause` for optional cadence
prompts only. Existing permission boundaries and human acceptance gates remain.
- Do not ask routine "proceed?" questions for already-authorized work.
- Make reversible decisions within granted scope and record the rationale.
- Park material ambiguity, new permission requirements, or unsafe work with
  evidence; continue independent authorized subjects.
- External consultants are optional and require separate configured authorization.
  No automatic Fable consultation or paid dispatch follows from this flag.
  A consultant's confidence never replaces security or acceptance evidence.
- Gates needing human eyes are deferred to a punch list, never marked complete.

THE HARD FLOOR — unattended never means unsafe:
  1. Guard-hook denies + every git ban (rebase/stash/amend/force-push/tree-wide add).
  2. No deploy, ship, publish, release, or real migration. Prepare, then stop.
  3. The safety veto list — destructive, security, money-path, schema,
     cross-repo contract, spend-or-send, scope expansion → park the subject.
  4. Human-verify boxes (`by eye`/`by hand`/`gpu`/`manual`) stay UNCHECKED.
     NEVER pass `--human` to planctl. Flipping the user's own smoke test while
     unattended forges a verification rather than automating one. Defer it.
  5. TRUE BLOCKERs still halt — but they park THAT SUBJECT ONLY and the run
     continues elsewhere. Halting is not the same as asking.

CLOSE WITH THE AUTONOMOUS RUN REPORT — completed / decisions and evidence /
parked / human-verification punch list / residual risk. Report only work and
consultations that occurred. A red test says red. A skipped step says skipped.

Full contract: meta-dev `references/autonomous-mode.md`.
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
