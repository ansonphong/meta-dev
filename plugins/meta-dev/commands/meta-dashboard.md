---
name: meta-dashboard
description: Control plane dashboard — spawns 3 haiku scanner agents in parallel, pipes structured JSON through dashboard-render.py for ASCII output
argument-hint: [--watch <seconds>]
allowed-tools: [Read, Bash(bash:*), Bash(python3:*), Agent]
model: haiku
---

# /meta-dashboard

ASCII dashboard for meta-dev harness. Spawn parallel haiku scanner agents, collect JSON, render via `dashboard-render.py`.

## Subcommands

- No args → single render cycle. Run `bash ${CLAUDE_PLUGIN_ROOT}/scripts/dashboard-render.py` with scanner output piped as JSON.
- `--watch N` → refresh every N seconds (min 5, max 300).

## No-arg behavior

Spawn 3 haiku scanners in parallel:
1. `Agent` dashboard-scanner reads STATUS.md, exec-order.md, git state
2. `Agent` inbox-scanner reads inbox state
3. `Agent` session-scanner reads active sessions

Pipe merged JSON → `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dashboard-render.py`

Detail: `references/dashboard-layout.md`.
