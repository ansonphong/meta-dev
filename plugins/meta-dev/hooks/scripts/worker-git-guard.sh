#!/usr/bin/env bash
set -euo pipefail
# ============================================================================
# worker-git-guard.sh — PreToolUse hook, HEADLESS-WORKER context only.
#
# Headless workers are COMMIT-FREE by law: the CONDUCTOR owns git. A worker
# that stages/commits/checks-out in the SHARED meta working tree can sweep or
# clobber a concurrent session's in-flight work (incident 2026-07-05). This
# hook BLOCKS the mutating git subcommands while leaving read-only git
# (status/diff/log/show) available for context-gathering.
#
# Injected by claude-headless-exec via `--settings` (the worker is a separate
# `claude -p` process that does NOT inherit the project's plugin hooks). It
# fires even under `--permission-mode bypassPermissions`, because PreToolUse
# hooks are a separate enforcement layer from the permission engine — which is
# exactly why --disallowedTools is not a reliable substitute here.
#
# Self-gating: active ONLY when META_WORKER_MANIFEST is set (the wrapper sets
# it). In any other context it allows unconditionally, so it can never
# accidentally constrain a normal interactive session that happens to load it.
#
# PreToolUse protocol: exit 0 with a JSON permissionDecision on stdout.
# ============================================================================

emit_allow() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}\n'
  exit 0
}

# Not a headless worker → do nothing.
[ -n "${META_WORKER_MANIFEST:-}" ] || emit_allow

PAYLOAD=$(cat)
TOOL=$(printf '%s' "$PAYLOAD" | jq -r '.tool_name // empty' 2>/dev/null || echo "")
[ "$TOOL" = "Bash" ] || emit_allow

CMD=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.command // empty' 2>/dev/null || echo "")
[ -n "$CMD" ] || emit_allow

# Mutating git subcommands — blocked. Read-only (status|diff|log|show|blame|
# rev-parse|ls-files|branch (list)) is intentionally NOT matched, so a worker
# can still orient itself in the tree.
if printf '%s' "$CMD" | grep -qiE '\bgit\s+(add|commit|stash|checkout|switch|restore|reset|rebase|merge|cherry-pick|revert|push|pull|fetch|am|apply|clean|tag|worktree)\b'; then
  jq -nc '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:"Headless workers are COMMIT-FREE — the conductor owns git. Do NOT run git add/commit/stash/checkout/reset/rebase/merge/pull/push. Your edited files are auto-captured to the manifest; just Read/Edit/Write and report. Read-only git (status/diff/log/show) is allowed."},systemMessage:"meta-dev worker-guard BLOCK: git mutation attempted in headless-worker context."}'
  exit 0
fi

emit_allow
