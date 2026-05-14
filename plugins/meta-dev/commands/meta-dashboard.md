---
name: meta-dashboard
description: Control plane dashboard — gathers plan, session, inbox, git state and renders inline
allowed-tools: [Bash(bash:*), Bash(python3:*)]
model: haiku
---

# /meta-dashboard

Control plane for meta-dev harness. Gathers project state and renders an inline dashboard.

## Behavior

Run `bash ${CLAUDE_PLUGIN_ROOT}/scripts/dashboard-data.sh` to gather JSON, pipe to `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dashboard-render.py`, print output.

No subcommands. No agents. Pure scripts — completes in under 2 seconds.

Detail: `references/dashboard-layout.md`.
