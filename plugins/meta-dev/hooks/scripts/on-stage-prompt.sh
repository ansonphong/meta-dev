#!/usr/bin/env bash
set -uo pipefail
# UserPromptSubmit hook: fires when the user submits a prompt.
# Input: JSON payload on stdin — { prompt, session_id, cwd, ... }
#
# Two independent jobs, in order:
#
# 1. AUTONOMOUS MODE — if the prompt invokes `--autonomous`, inject the
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
# Require a command invocation or a leading flag on the first line. Ignore
# quoted arguments and examples; a prose mention must not enable execution.
if printf '%s' "$PROMPT" | jq -Rse "$(cat <<'FILTER'
  split("\n")[0]
  | select(test("^\\s*(/[A-Za-z0-9_:-]+\\s+|--autonomous(?:\\s|$))"))
  | gsub("\"(?:\\\\.|[^\"\\\\])*(?:\"|$)|'[^']*(?:'|$)|`[^`]*(?:`|$)"; "_")
  | sub("(^|\\s)--(\\s|$).*"; "")
  | test("(^|\\s)--autonomous(\\s|$)")
FILTER
)" >/dev/null 2>&1; then
  CONTEXT=$(cat <<'AUTOEOF'
⟡ AUTONOMOUS MODE ENGAGED — `--autonomous` was invoked.

Own the explicitly authorized job through completion. Carry authorization across
stages, workers, repairs, verification, and necessary integration within scope;
include the authority and constraints in worker briefs and handoffs. A standalone
read-only request stays read-only; a scoped implementation request includes its
necessary repairs. Neither the flag nor a stage ceiling expands the job's scope.

It implies cruise mode, `--gate none`, and `--no-pause` for optional cadence
prompts only. Preserve the instruction hierarchy and explicitly reserved human gates.
- Do not ask routine "proceed?" questions for already-authorized work.
- Make reversible decisions within granted scope and record the rationale.
- Perform already-authorized sensitive work without redundant approval. Auth,
  schema, money-path, destructive, cross-repo, deploy/publish/release, and spend-or-send
  work need authority covering that action and target, not a new prompt each stage.
- Park only concrete blockers: genuinely new authority, material scope ambiguity,
  an unavailable capability, a mandatory protection, or a reserved human gate.
  Record evidence and what unblocks the branch; continue independent authorized work.
- External consultants are optional; use existing authorization when it covers dispatch.
  No automatic Fable consultation or paid dispatch follows from this flag.
  A consultant's confidence never replaces security or acceptance evidence.
- Gates needing human eyes are deferred to a punch list, never marked complete.

THE HARD FLOOR — unattended never means unsafe:
  1. Mandatory environment protections, guard-hook denies, and every applicable
     git ban remain. Do not bypass sandbox restrictions or denied operations.
  2. Use credentials only through authorized mechanisms for the approved target;
     never expose secrets or obtain broader access to get around a blocker.
  3. Explicitly reserved approvals still apply, even within an authorized job.
  4. Human-verify boxes (`by eye`/`by hand`/`gpu`/`manual`) stay UNCHECKED.
     NEVER pass `--human` to planctl. Flipping the user's own smoke test while
     unattended forges a verification rather than automating one. Defer it.
  5. Verify with actual evidence. Never claim unlimited authority, invent tool
     availability, or report a denied, unavailable, skipped, or failed operation as done.

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
