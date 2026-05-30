---
name: meta-dashboard
description: Control plane dashboard — gathers plan, session, inbox, git state and renders inline
allowed-tools: [Bash(bash:*), Bash(python3:*)]
model: haiku
---

# /meta-dashboard

Control plane for meta-dev harness. Gathers project state and renders an inline dashboard.

## Behavior

1. Run the pipeline from the project root:

   ```
   bash ${CLAUDE_PLUGIN_ROOT}/scripts/dashboard-data.sh | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dashboard-render.py
   ```

2. **Reproduce the script's output verbatim in your reply, inside a fenced code block.**
   Harness tool output is collapsed (the user must press Ctrl+O to expand it), so the
   dashboard only appears *inline* if you echo it back. Copy it exactly — the rounded
   box borders are pre-aligned; do not reformat, re-wrap, re-indent, or "improve" them,
   and add no commentary above or below unless the user asked a question. The code block
   is the whole response.

No subcommands. No agents. Pure scripts — completes in under 2 seconds.

Detail: `references/dashboard-layout.md`.
