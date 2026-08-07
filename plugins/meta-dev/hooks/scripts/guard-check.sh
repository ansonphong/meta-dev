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

  # Shared-worktree git policy — HEADLESS-WORKER CHARTER ONLY, never interactive.
  #
  # scripts/lib/git_policy.py is deny-by-default over the whole git surface: it
  # bans reset/restore/checkout/stash/clean/rebase/revert outright, demands
  # `git -C <absolute> add -- <files>` and `commit --only -m ... -- <files>`, and
  # refuses every subcommand nobody explicitly enumerated (cat-file, worktree,
  # apply, grep, for-each-ref, cherry-pick, submodule, ...). That contract exists
  # so N concurrent headless workers cannot destroy or sweep up each other's
  # in-flight edits in ONE shared tree — it is enforced at its proper home,
  # hooks/scripts/worker-git-guard.sh, which self-gates on META_WORKER_MANIFEST.
  #
  # Running it from here applied the worker charter to every interactive session
  # the plugin is installed in, so ordinary conductor work (`git cat-file`,
  # `git config --list`, `git restore`, plain `git add -p`) was denied with a
  # "shared-worktree policy" reason that named a worktree the user never entered.
  # Under Codex the same policy also runs ahead of this script in
  # codex-adapter.py, so calling it here was pure duplication. Fixed 2026-08-04.
  #
  # The destructive-command guards BELOW are the interactive contract and still
  # apply everywhere: reset --hard, checkout/restore ., clean -f, broad `git add`
  # sweeps, force-push to main. Gate only the worker charter.
  if [ -n "${META_WORKER_MANIFEST:-}" ] || [ "${META_DEV_GIT_POLICY_IN_CLAUDE:-}" = "1" ]; then
    GIT_POLICY="$PLUGIN_ROOT/scripts/lib/git_policy.py"
    if [ -f "$GIT_POLICY" ]; then
      set +e
      GIT_POLICY_REASON=$(python3 "$GIT_POLICY" --command "$COMMAND" 2>&1)
      GIT_POLICY_RC=$?
      set -e
      if [ "$GIT_POLICY_RC" -ne 0 ]; then
        emit_deny "shared-worktree git policy blocked command: $GIT_POLICY_REASON"
      fi
    fi
  fi

  # rm .git/index — catastrophic, NEVER overrideable (config can only block).
  if printf '%s' "$COMMAND" | grep -qiE 'rm\s+(-[a-zA-Z]+\s+)*\.git/index($|[[:space:]])'; then
    A=$(cfg rm_git_index block)
    [ "$A" = "warn" ] && A=block  # schema forbids allow; force block regardless
    apply_action "$A" "rm .git/index destroys the git index — NEVER do this. Remove only .git/index.lock from a Windows terminal, then 'git add -A'."
  fi

  # git reset --hard — destroys uncommitted changes.
  if printf '%s' "$COMMAND" | grep -qiE 'git\s+reset\s+(-[a-zA-Z]+\s+)*--hard'; then
    apply_action "$(cfg git_reset_hard block)" "git reset --hard destroys uncommitted changes. Stash or commit first."
  fi

  # git checkout . / git restore . — overwrites working tree.
  if printf '%s' "$COMMAND" | grep -qiE 'git\s+(checkout|restore)\s+(--\s+)?\.($|[[:space:]])'; then
    apply_action "$(cfg git_checkout_dot block)" "git checkout/restore . overwrites uncommitted working-tree changes. Stash or commit first."
  fi

  # git clean -f — permanently deletes untracked files. Folded under git_checkout_dot.
  if printf '%s' "$COMMAND" | grep -qiE 'git\s+clean\s+-[a-zA-Z]*f'; then
    apply_action "$(cfg git_checkout_dot block)" "git clean -f permanently deletes untracked files."
  fi

  # git add -A/-u/./<dir/> — the COMMIT-SWEEP guard (incident 2026-07-05).
  # The meta repo working tree is SHARED across concurrent sessions. A broad
  # `git add` stages EVERY dirty file under a path — including another live
  # session's in-flight worker edits — sweeping foreign work into this commit.
  # Charter rule: the conductor stages EXACTLY its task's declared files.
  # There is no override for directory staging: a shared worktree cannot prove
  # that every file under a directory belongs to this session.
  # The shared parser above also checks existing bare directory paths; this
  # regex is retained as a fast, explanatory backstop for familiar forms.
  if printf '%s' "$COMMAND" | grep -qiE '\bgit\s+add\b' \
     ; then
    SWEEP=""
    printf '%s' "$COMMAND" | grep -qiE '\bgit\s+add\s+([^&|;]*[[:space:]])?(-A|--all|-u|--update)([[:space:]]|$)' && SWEEP="the -A/-u/--all/--update flag"
    printf '%s' "$COMMAND" | grep -qiE '\bgit\s+add\s+([^&|;]*[[:space:]])?\.([[:space:]/]|$)'                    && SWEEP="a bare '.'"
    printf '%s' "$COMMAND" | grep -qiE '\bgit\s+add\s+([^&|;]*[[:space:]])?[^[:space:]&|;]+/([[:space:]]|$)'       && SWEEP="a directory path (trailing '/')"
    if [ -n "$SWEEP" ]; then
      apply_action "$(cfg git_add_sweep block)" "git add with $SWEEP stages EVERY dirty file under that path — in a SHARED tree that sweeps another concurrent session's in-flight worker edits into your commit (commit-sweep, incident 2026-07-05). Stage explicit file paths only: 'git -C <absolute-repo> add -- <file1> <file2>'."
    fi
  fi

  # git push --force on main/master — overwrites remote history.
  if printf '%s' "$COMMAND" | grep -qiE 'git\s+push\s+.*(--force([^-]|$)|-f([[:space:]]|$))'; then
    if printf '%s' "$COMMAND" | grep -qiE '(main|master)'; then
      apply_action "$(cfg git_push_force_main block)" "git push --force on main/master overwrites shared history. Use --force-with-lease and a non-protected branch."
    else
      emit_warn_allow "git push --force — prefer --force-with-lease to avoid clobbering remote work."
    fi
  fi

  # git branch -D — force-deletes a branch without merge check (warn).
  if printf '%s' "$COMMAND" | grep -qiE 'git\s+branch\s+-D'; then
    emit_warn_allow "git branch -D force-deletes a branch with no merge check."
  fi

  # --no-verify — bypasses safety hooks.
  if printf '%s' "$COMMAND" | grep -qiE '(--no-verify|--no-gpg-sign)'; then
    apply_action "$(cfg no_verify_flag warn)" "--no-verify / --no-gpg-sign bypasses safety hooks. Fix the underlying failure instead."
  fi

  # rm -rf / rm -r on non-temp paths.
  if printf '%s' "$COMMAND" | grep -qiE 'rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r|-r[[:space:]])'; then
    # Carve-out: rm under a temp dir is routine and safe.
    if printf '%s' "$COMMAND" | grep -qiE 'rm\s+(-[a-zA-Z]+\s+)*("?(/tmp/|/var/tmp/|\$\{?TMPDIR)|"?\./?(tmp|\.tmp|node_modules|dist|build)/)'; then
      emit_allow
    fi
    apply_action "$(cfg rm_rf_non_temp block)" "Recursive delete (rm -rf) outside a temp/build path. Verify the target carefully — this is irreversible."
  fi

  # SQL data destruction.
  if printf '%s' "$COMMAND" | grep -qiE 'DROP\s+(TABLE|DATABASE)|TRUNCATE\s+TABLE'; then
    apply_action "$(cfg drop_table block)" "DROP TABLE/DATABASE or TRUNCATE is irreversible data destruction."
  fi
  if printf '%s' "$COMMAND" | grep -qiE 'DELETE\s+FROM\s+[A-Za-z_][A-Za-z0-9_."]*\s*;'; then
    apply_action "$(cfg drop_table block)" "DELETE FROM with no WHERE clause deletes every row. Add a WHERE filter."
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
