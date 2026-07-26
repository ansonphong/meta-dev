#!/usr/bin/env bash
# Preflight for a Codex session driving the meta-dev harness.
# Codex lifecycle hooks are supported through meta-dev's trusted adapter; this
# remains a diagnostic, not a substitute for hook trust or guard policy.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/plugin-root.sh
source "$SCRIPT_DIR/lib/plugin-root.sh"
PLUGIN_ROOT="$(_md_plugin_root)"
CODEX_CONFIG_DIR="${CODEX_HOME:-${XDG_CONFIG_HOME:+$XDG_CONFIG_HOME/codex}}"
[ -n "$CODEX_CONFIG_DIR" ] || CODEX_CONFIG_DIR="$HOME/.codex"
WARN=0; ERR=0
good() { echo "  [ ok ] $1"; }
warn() { echo "  [warn] $1"; WARN=$((WARN+1)); }
err()  { echo "  [FAIL] $1"; ERR=$((ERR+1)); }

echo "=== codex-doctor ==="

# 0. Codex hook trust. The adapter is loaded by a trusted installed plugin;
# this source checkout can only verify that the adapter is present. Never tell
# users to bypass trust for automation — trust the plugin through Codex's normal
# flow, then the runner can rely on the same guard policy as interactive Codex.
if [ -f "$PLUGIN_ROOT/hooks/hooks.json" ] && [ -x "$PLUGIN_ROOT/hooks/scripts/codex-adapter.py" ]; then
  good "Codex lifecycle hook adapter bundled; trust the installed meta-dev plugin normally (never --dangerously-bypass-hook-trust)"
else
  err "Codex lifecycle hook adapter missing; restore hooks/hooks.json and hooks/scripts/codex-adapter.py"
fi

# 1. Network egress — the #1 blocker for headless dispatch.
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 https://api.anthropic.com/v1/models 2>/dev/null)" || code="000"
if [ "$code" = "000" ]; then
  err "network egress BLOCKED (HTTP 000). Claude workers cannot run.
         STOP and choose a policy before dispatch: prefer restarting Codex with
         -c sandbox_workspace_write.network_access=true for one invocation.
         Global Codex configuration changes require explicit human approval
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
             in the Codex config directory (scope to specific repos, never a wildcard)
         meta-dev's own codex-headless-exec already grants this per-run; this
         failure means you are on a launch path that bypasses it (interactive
         codex, bare 'codex exec', or a fresh machine with no global config)."
fi

# 3. Claude CLI + ambient subscription login.
if command -v claude >/dev/null 2>&1; then good "claude CLI: $(claude --version 2>/dev/null | head -1)"
else err "claude CLI not found on PATH"; fi

CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
if [ -d "$CLAUDE_CONFIG_DIR" ]; then good "ambient Claude login directory present"
else warn "ambient Claude login directory absent — subscription workers (opus/fable/sonnet) may not authenticate"; fi

# 4. Optional API backends.
[ -n "${DEEPSEEK_API_KEY:-}" ] && good "DEEPSEEK_API_KEY visible" || warn "DEEPSEEK_API_KEY unset (deep backend unavailable)"
[ -n "${GLM_API_KEY:-}" ]      && good "GLM_API_KEY visible"      || warn "GLM_API_KEY unset (glm backend unavailable)"

# 5. Plugin cache freshness.
LOCAL_V="$(python3 -c "import json; print(json.load(open('$PLUGIN_ROOT/.claude-plugin/plugin.json'))['version'])" 2>/dev/null || echo '?')"
CACHE_V="$(ls -1 "$CODEX_CONFIG_DIR/plugins/cache/meta-dev/meta-dev" 2>/dev/null | sort -V | tail -1 || echo '?')"
if [ "$LOCAL_V" = "$CACHE_V" ]; then good "plugin version in sync ($LOCAL_V)"
else warn "version drift: working tree $LOCAL_V vs Codex cache $CACHE_V
         Fix: bump patch, push, then /plugin marketplace update meta-dev"; fi

# 6. Command surface reality check.
# Codex autocompletes $meta-dev: against skills, so canonical commands are
# generated as exact native skills. Pure Claude redirect aliases stay behind
# the compatibility router to protect Codex's bounded initial skill index.
NATIVE_SKILLS="$(find "$PLUGIN_ROOT"/skills -mindepth 2 -maxdepth 2 -name SKILL.md 2>/dev/null | wc -l)"
CMDS="$(ls -1 "$PLUGIN_ROOT"/commands/*.md 2>/dev/null | wc -l)"
good "$NATIVE_SKILLS native skills · $CMDS Claude command names
         Canonical: \$meta-dev:meta-planner · fallback aliases: \$meta-dev:command-router planner"

# 7. Headless dispatch readiness — the single most-asked-for command family.
if [ -x "$PLUGIN_ROOT/scripts/claude-headless-exec" ]; then
  good "headless workers ready: claude-headless-exec --backend fable|opus|sonnet|deep|glm
         \$meta-dev:fable-execute and friends are native command skills that
         resolve to this one script + a --backend flag."
else
  err "claude-headless-exec missing or not executable in $PLUGIN_ROOT/scripts/"
fi

echo
if [ "$ERR" -gt 0 ]; then echo "=== BROKEN: $ERR error(s), $WARN warning(s) ==="; exit 2
elif [ "$WARN" -gt 0 ]; then echo "=== DEGRADED: $WARN warning(s) ==="; exit 1
else echo "=== READY ==="; exit 0; fi
