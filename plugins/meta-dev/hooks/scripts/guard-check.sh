#!/usr/bin/env bash
set -euo pipefail
# PreToolUse hook: fires before Bash / Edit / Write / MultiEdit tool calls.
# Matcher: Bash and Edit|Write|MultiEdit in plugin.json (PreToolUse).
# Input: JSON payload on stdin — { tool_name, tool_input:{command|file_path,...}, ... }
#
# Purpose: BLOCK destructive commands, unsafe shared-worktree git commands, and
# out-of-scope edits BEFORE they execute.
# This is the load-bearing half of /meta-guard (the PostToolUse hooks are telemetry only).
#
# Protocol (Claude Code PreToolUse): exit 0 with JSON on stdout —
#   allow -> {"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}
#   block -> {"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny",
#             "permissionDecisionReason":"..."},"systemMessage":"..."}
# A "warn" category is surfaced via systemMessage but still allowed.
#
# Constraints: must complete <100ms, no network. All checks are local regex + one cached
# config read. Read-only tools (Read/Grep/Glob) are never inspected. `.claude/` edits are
# always allowed so meta-commands can self-modify (Learned Patterns loop).

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-.}"

# Freeze-scope file lives in a temp location, set by /meta-guard freeze <dir>.
# Override path via META_GUARD_FREEZE_FILE for testing.
FREEZE_FILE="${META_GUARD_FREEZE_FILE:-${TMPDIR:-/tmp}/meta-guard-freeze.scope}"

# --- JSON emit helpers ---
emit_allow() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}\n'
  exit 0
}

emit_deny() {
  # $1 = reason
  jq -nc --arg r "$1" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r},systemMessage:("meta-guard BLOCK: " + $r)}'
  exit 0
}

emit_warn_allow() {
  # $1 = message — surfaced to Claude but the call proceeds
  jq -nc --arg m "$1" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow"},systemMessage:("meta-guard WARN: " + $m)}'
  exit 0
}

PAYLOAD=$(cat)
TOOL_NAME=$(printf '%s' "$PAYLOAD" | jq -r '.tool_name // empty' 2>/dev/null || echo "")

# Read-only tools are always safe — never inspected.
case "$TOOL_NAME" in
  Read|Grep|Glob|NotebookRead|"") emit_allow ;;
esac

# --- Load guard config once, cascade-aware, via jq (fast: no python startup) ---
# Mirrors scripts/config-merge.py's cascade (defaults -> project -> local) but reads
# only the meta_dev.guard subtree and merges with jq's recursive `*` operator. This keeps
# the hot path under the <100ms budget (a python3 config-get round-trip is ~140ms). Schema
# validation is intentionally skipped — the hook only reads values, never writes them.
GUARD_CFG=""
load_guard_cfg() {
  [ -n "$GUARD_CFG" ] && return 0
  local defaults="$PLUGIN_ROOT/templates/settings.json"
  local project="plans/_dashboard/settings.json"
  local local_f="plans/_dashboard/settings.local.json"
  local files=""
  for f in "$defaults" "$project" "$local_f"; do
    [ -f "$f" ] && files="$files $f"
  done
  if [ -z "$files" ]; then GUARD_CFG="{}"; return 0; fi
  # shellcheck disable=SC2086
  GUARD_CFG=$(jq -s 'reduce .[] as $x ({}; . * $x) | (.meta_dev.guard // {})' $files 2>/dev/null || echo "{}")
}

cfg() {
  # $1 = key under meta_dev.guard.destructive_categories; $2 = default action
  load_guard_cfg
  local v
  v=$(printf '%s' "$GUARD_CFG" | jq -r --arg k "$1" '.destructive_categories[$k] // empty' 2>/dev/null || echo "")
  if [ -z "$v" ] || [ "$v" = "null" ]; then echo "$2"; else echo "$v"; fi
}

# Per-category action resolver: emits deny/warn/allow based on configured action.
# $1 = configured action (block|warn|allow), $2 = reason
apply_action() {
  case "$1" in
    block) emit_deny "$2" ;;
    warn)  emit_warn_allow "$2" ;;
    *)     ;;  # allow -> fall through, no emit
  esac
}

# ============================================================
# BASH COMMAND PROTECTION
# ============================================================
if [ "$TOOL_NAME" = "Bash" ]; then
  COMMAND=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.command // empty' 2>/dev/null || echo "")
  [ -z "$COMMAND" ] && emit_allow

  # ---- GIT: one shell-aware policy, no duplicated regexes ------------------
  #
  # scripts/lib/git_policy.py is now a DESTRUCTIVE-ONLY DENYLIST (inverted from
  # the old deny-by-default allowlist on 2026-08-07). It blocks exactly the set
  # that can destroy uncommitted or published work — reset --hard, stash, broad
  # checkout/restore, clean -f, rebase, non-ff merge/pull, force push, tree-wide
  # add/commit -a, amend, filter-branch, reflog expire, update-ref -d, branch -D
  # — and allows everything else with no required flag shape and no mandatory
  # -C. So it is safe to run in EVERY context, and it runs unconditionally here.
  #
  # It replaces the hand-rolled regexes that used to live below — git AND non-git
  # alike. Those were duplicates with a worse engine: grep cannot tell a command
  # from a string, so `python3 - <<'PY'` with "git reset --hard" in a Python
  # string literal was denied, a grep for a destructive command was denied, and a
  # COMMIT MESSAGE describing one was denied. The policy parses the shell and
  # checks each simple command's executable, so data reads as data.
  #
  # `--guard` also applies the non-git rules (rm -rf outside temp, rm .git/index,
  # destructive SQL on a database command line) and returns the settings.json
  # category, so meta_dev.guard.destructive_categories still tunes each one.
  #
  # META_DEV_GIT_POLICY_SKIP=1 disables it outright for a deliberate rescue.
  GIT_POLICY="$PLUGIN_ROOT/scripts/lib/git_policy.py"
  if [ -f "$GIT_POLICY" ] && [ "${META_DEV_GIT_POLICY_SKIP:-}" != "1" ]; then
    set +e
    VERDICT=$(python3 "$GIT_POLICY" --guard --command "$COMMAND" 2>/dev/null)
    set -e
    if [ -n "$VERDICT" ] && [ "$(printf '%s' "$VERDICT" | jq -r '.allowed')" = "false" ]; then
      REASON=$(printf '%s' "$VERDICT" | jq -r '.reason')
      CATEGORY=$(printf '%s' "$VERDICT" | jq -r '.category')
      case "$CATEGORY" in
        git)
          emit_deny "$REASON" ;;
        rm_git_index)
          A=$(cfg rm_git_index block)
          [ "$A" = "warn" ] && A=block  # schema forbids allow; force block regardless
          apply_action "$A" "$REASON" ;;
        *)
          apply_action "$(cfg "$CATEGORY" block)" "$REASON" ;;
      esac
    fi
  fi

  # --no-verify — bypasses safety hooks.
  if printf '%s' "$COMMAND" | grep -qiE '(--no-verify|--no-gpg-sign)'; then
    apply_action "$(cfg no_verify_flag warn)" "--no-verify / --no-gpg-sign bypasses safety hooks. Fix the underlying failure instead."
  fi

  emit_allow
fi

# ============================================================
# EDIT / WRITE FREEZE-SCOPE ENFORCEMENT
# ============================================================
case "$TOOL_NAME" in
  Edit|Write|MultiEdit)
    # No freeze active → nothing to enforce.
    [ -f "$FREEZE_FILE" ] || emit_allow

    SCOPE=$(cat "$FREEZE_FILE" 2>/dev/null || echo "")
    [ -z "$SCOPE" ] && emit_allow

    FILE_PATH=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.file_path // empty' 2>/dev/null || echo "")
    [ -z "$FILE_PATH" ] && emit_allow

    # ALWAYS allow .claude/ edits — meta-commands self-modify for Learned Patterns.
    case "$FILE_PATH" in
      */.claude/*|.claude/*) emit_allow ;;
    esac

    # Allow plan files (checkbox / status updates during execution).
    case "$FILE_PATH" in
      */plans/*|plans/*) emit_allow ;;
    esac

    # In-scope?
    case "$FILE_PATH" in
      *"$SCOPE"*) emit_allow ;;
    esac

    emit_deny "Edit target '$FILE_PATH' is outside the frozen scope '$SCOPE'. Run '/meta-guard unfreeze' to release, or '/meta-guard freeze <dir>' to re-scope."
    ;;
esac

# Any other tool — allow.
emit_allow
