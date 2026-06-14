---
name: meta-sweep
description: Call sweep-agent + scripts — archive stale plans and wip-commit untracked files
argument-hint: [--archive-only | --wip-only]
allowed-tools: [Read, Write, Bash, Glob, Grep, Agent]
model: opus
---

# /meta-sweep

Plan maintenance. Delegates to `sweep-agent` (`agents/sweep-agent.md`) which calls:

- `bash ${CLAUDE_PLUGIN_ROOT}/scripts/sweep-archive-stale.sh` — archive completed + inactive plans
- `bash ${CLAUDE_PLUGIN_ROOT}/scripts/sweep-wip-commit.sh` — wip-commit untracked files

Flags:
- `--archive-only` — skip wip commit
- `--wip-only` — skip archive

Config: `plans/_dashboard/settings.json` (stale threshold days, archive path).
