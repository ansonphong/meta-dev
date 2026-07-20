#!/usr/bin/env bash
# Preflight for a Codex session driving the meta-dev harness.
# Codex has no PreToolUse hook, so this is the explicit stand-in.
set -uo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WARN=0; ERR=0
good() { echo "  [ ok ] $1"; }
warn() { echo "  [warn] $1"; WARN=$((WARN+1)); }
err()  { echo "  [FAIL] $1"; ERR=$((ERR+1)); }

echo "=== codex-doctor ==="

# 1. Network egress — the #1 blocker for headless dispatch.
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 https://api.anthropic.com/v1/models 2>/dev/null)" || code="000"
if [ "$code" = "000" ]; then
  err "network egress BLOCKED (HTTP 000). Claude workers cannot run.
         STOP and choose a policy before dispatch: prefer restarting Codex with
         -c sandbox_workspace_write.network_access=true for one invocation.
         Global ~/.codex/config.toml changes require Phong's explicit approval
         and weaken every workspace-write session machine-wide, permanently."
else
  good "network egress OK (HTTP $code)"
fi

# 2. .git writability — COMMIT-ON-RED is unenforceable without it.
# Codex `workspace-write` treats .git as a PROTECTED path (read-only, recursive)
# even inside a writable root — upstream default, documented under "Protected
# paths in writable roots". A worker then cannot honor the harness law that it
# commits its own scoped edits, and its work sits unowned until a peer's broad
# `git add` adopts it. Diagnosed here because the alternative is what actually
# happened on 2026-07-20: the constraint got discovered mid-task and "fixed" by
# writing "run NO git command" into task briefs, which then leaked onto Claude
# workers that could commit fine.
# Reports on the repo the session is sitting in — that is the one whose .git a
# worker here would need to write.
_GITDIR="$(git rev-parse --absolute-git-dir 2>/dev/null || true)"
if [ -z "$_GITDIR" ]; then
  warn "not inside a git repo — cannot check .git writability from here"
elif [ -w "$_GITDIR" ]; then
  good ".git writable — workers can self-commit ($_GITDIR)"
else
  err ".git READ-ONLY ($_GITDIR). Workers cannot commit; their edits will be
         left unowned for a peer's broad 'git add' to adopt.
         DO NOT work around this by telling workers to skip git — that is a
         per-backend exemption in prose and it leaks to other backends.
         Fix the sandbox instead, by either:
           - per-invocation: -c 'sandbox_workspace_write.writable_roots=[\"$_GITDIR\"]'
           - permanent: add \"$_GITDIR\" to [sandbox_workspace_write] writable_roots
             in ~/.codex/config.toml (scope to specific repos, never a wildcard)
         meta-dev's own codex-headless-exec already grants this per-run; this
         failure means you are on a launch path that bypasses it (interactive
         codex, bare 'codex exec', or a fresh machine with no global config)."
fi

# 3. Claude CLI + ambient subscription login.
if command -v claude >/dev/null 2>&1; then good "claude CLI: $(claude --version 2>/dev/null | head -1)"
else err "claude CLI not found on PATH"; fi

if [ -d "$HOME/.claude" ]; then good "ambient Claude login directory present"
else warn "~/.claude absent — subscription workers (opus/fable/sonnet) may not authenticate"; fi

# 4. Optional API backends.
[ -n "${DEEPSEEK_API_KEY:-}" ] && good "DEEPSEEK_API_KEY visible" || warn "DEEPSEEK_API_KEY unset (deep backend unavailable)"
[ -n "${GLM_API_KEY:-}" ]      && good "GLM_API_KEY visible"      || warn "GLM_API_KEY unset (glm backend unavailable)"

# 5. Plugin cache freshness.
LOCAL_V="$(python3 -c "import json; print(json.load(open('$PLUGIN_ROOT/.claude-plugin/plugin.json'))['version'])" 2>/dev/null || echo '?')"
CACHE_V="$(ls -1 "$HOME/.codex/plugins/cache/meta-dev/meta-dev" 2>/dev/null | sort -V | tail -1 || echo '?')"
if [ "$LOCAL_V" = "$CACHE_V" ]; then good "plugin version in sync ($LOCAL_V)"
else warn "version drift: working tree $LOCAL_V vs Codex cache $CACHE_V
         Fix: bump patch, push, then /plugin marketplace update meta-dev"; fi

# 6. Command surface reality check.
SKILLS="$(ls -1d "$PLUGIN_ROOT"/skills/*/ 2>/dev/null | wc -l)"
CMDS="$(ls -1 "$PLUGIN_ROOT"/commands/*.md 2>/dev/null | wc -l)"
good "$SKILLS skills reachable via \$meta-dev: · $CMDS commands via \$meta-dev:command-router"

echo
if [ "$ERR" -gt 0 ]; then echo "=== BROKEN: $ERR error(s), $WARN warning(s) ==="; exit 2
elif [ "$WARN" -gt 0 ]; then echo "=== DEGRADED: $WARN warning(s) ==="; exit 1
else echo "=== READY ==="; exit 0; fi
