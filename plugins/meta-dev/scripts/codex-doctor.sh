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
         Fix: [sandbox_workspace_write] network_access = true in ~/.codex/config.toml, then restart Codex."
else
  good "network egress OK (HTTP $code)"
fi

# 2. Claude CLI + ambient subscription login.
if command -v claude >/dev/null 2>&1; then good "claude CLI: $(claude --version 2>/dev/null | head -1)"
else err "claude CLI not found on PATH"; fi

if [ -d "$HOME/.claude" ]; then good "ambient Claude login directory present"
else warn "~/.claude absent — subscription workers (opus/fable/sonnet) may not authenticate"; fi

# 3. Optional API backends.
[ -n "${DEEPSEEK_API_KEY:-}" ] && good "DEEPSEEK_API_KEY visible" || warn "DEEPSEEK_API_KEY unset (deep backend unavailable)"
[ -n "${GLM_API_KEY:-}" ]      && good "GLM_API_KEY visible"      || warn "GLM_API_KEY unset (glm backend unavailable)"

# 4. Plugin cache freshness.
LOCAL_V="$(python3 -c "import json; print(json.load(open('$PLUGIN_ROOT/.claude-plugin/plugin.json'))['version'])" 2>/dev/null || echo '?')"
CACHE_V="$(ls -1 "$HOME/.codex/plugins/cache/meta-dev/meta-dev" 2>/dev/null | sort -V | tail -1 || echo '?')"
if [ "$LOCAL_V" = "$CACHE_V" ]; then good "plugin version in sync ($LOCAL_V)"
else warn "version drift: working tree $LOCAL_V vs Codex cache $CACHE_V
         Fix: bump patch, push, then /plugin marketplace update meta-dev"; fi

# 5. Command surface reality check.
SKILLS="$(ls -1d "$PLUGIN_ROOT"/skills/*/ 2>/dev/null | wc -l)"
CMDS="$(ls -1 "$PLUGIN_ROOT"/commands/*.md 2>/dev/null | wc -l)"
good "$SKILLS skills reachable via \$meta-dev: · $CMDS commands via \$meta-dev:command-router"

echo
if [ "$ERR" -gt 0 ]; then echo "=== BROKEN: $ERR error(s), $WARN warning(s) ==="; exit 2
elif [ "$WARN" -gt 0 ]; then echo "=== DEGRADED: $WARN warning(s) ==="; exit 1
else echo "=== READY ==="; exit 0; fi
