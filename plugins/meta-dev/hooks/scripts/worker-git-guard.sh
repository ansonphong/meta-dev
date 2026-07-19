#!/usr/bin/env bash
set -euo pipefail
# ============================================================================
# worker-git-guard.sh — PreToolUse hook, HEADLESS-WORKER context only.
#
# Headless workers COMMIT THEIR OWN WORK (policy change 2026-07-19). Modular,
# per-task commits beat one end-of-run conductor sweep: the history reads as
# coherent units, and finished work is durable the moment it is done instead of
# sitting uncommitted until the conductor gets to it.
#
# What the 2026-07-05 incident was ACTUALLY about was never `commit` — it was
# TREE-WIDE STAGING and TREE-MUTATING commands in a SHARED working tree with
# many concurrent agents. `git add -A` sweeps a peer's in-flight lines into your
# commit; checkout/reset/stash/restore DESTROY them. Those stay blocked. A
# commit of explicitly-named paths is additive, recoverable, and safe.
#
# So this hook blocks exactly three things:
#   1. Destructive / history-rewriting / network git subcommands
#   2. Tree-wide staging (`git add -A|.|-u|<dir>/`, `git commit -a`)
#   3. `git commit --amend` (history rewrite)
# Everything else — `git add <explicit paths>`, `git commit -m`, and all
# read-only git — is ALLOWED.
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

emit_deny() {
  jq -nc --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason},systemMessage:"meta-dev worker-guard BLOCK: unsafe git mutation attempted in headless-worker context."}'
  exit 0
}

# Not a headless worker → do nothing.
[ -n "${META_WORKER_MANIFEST:-}" ] || emit_allow

PAYLOAD=$(cat)
TOOL=$(printf '%s' "$PAYLOAD" | jq -r '.tool_name // empty' 2>/dev/null || echo "")
[ "$TOOL" = "Bash" ] || emit_allow

CMD=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.command // empty' 2>/dev/null || echo "")
[ -n "$CMD" ] || emit_allow

# ── 1. Destructive / history-rewriting / network subcommands ────────────────
# These either DESTROY a peer's uncommitted work (checkout/restore/reset/clean/
# stash) or rewrite/move shared history (rebase/merge/cherry-pick/revert/am/
# filter-branch) or touch the remote (push/pull/fetch). `add` and `commit` are
# deliberately NOT in this list. Read-only git (status|diff|log|show|blame|
# rev-parse|ls-files) is not matched either, so a worker can orient itself.
if printf '%s' "$CMD" | grep -qiE '\bgit\s+([^|;&]*\s)?(stash|checkout|switch|restore|reset|rebase|merge|cherry-pick|revert|push|pull|fetch|am|apply|clean|tag|worktree|filter-branch)\b'; then
  emit_deny "BLOCKED: destructive/history/network git in worker context. You MAY 'git add <explicit paths>' and 'git commit' your own work — but never stash/checkout/restore/reset/clean (these destroy concurrent sessions' uncommitted work), never rebase/merge/cherry-pick/revert/am (these rewrite shared history), and never push/pull/fetch (the conductor owns the remote). Read-only git (status/diff/log/show) is allowed."
fi

# ── 2. Tree-wide staging ───────────────────────────────────────────────────
# `git add -A|--all|-u|--update|.|*` or a bare directory arg (trailing slash)
# sweeps a concurrent session's in-flight edits into YOUR commit — the actual
# 2026-07-05 failure mode. Stage the exact files you touched, by name.
if printf '%s' "$CMD" | grep -qiE '\bgit\s+(-C\s+\S+\s+)?add\b[^|;&]*(\s-{1,2}(A|all|u|update)\b|\s\.(\s|$)|\s\*|\s["'"'"']?\S*/["'"'"']?(\s|$))'; then
  emit_deny "BLOCKED: tree-wide staging. 'git add -A/./-u/<dir>/' sweeps other agents' in-flight edits into your commit (incident 2026-07-05). Stage the exact files you edited, by full path: git -C <abs-repo-root> add path/to/a.ts path/to/b.svelte"
fi

# `git commit -a` / `--all` stages every tracked modification — same sweep.
if printf '%s' "$CMD" | grep -qiE '\bgit\s+(-C\s+\S+\s+)?commit\b[^|;&]*(\s-[a-zA-Z]*a[a-zA-Z]*(\s|$)|\s--all\b)'; then
  emit_deny "BLOCKED: 'git commit -a/--all' stages every tracked modification, including other agents' in-flight edits. Stage your exact paths with 'git add <paths>' first, then plain 'git commit -m'."
fi

# ── 3. Commit history rewrite ──────────────────────────────────────────────
if printf '%s' "$CMD" | grep -qiE '\bgit\s+([^|;&]*\s)?commit\b[^|;&]*\s--amend\b'; then
  emit_deny "BLOCKED: 'git commit --amend' rewrites history another agent may already have built on. Make a new commit instead."
fi

emit_allow
