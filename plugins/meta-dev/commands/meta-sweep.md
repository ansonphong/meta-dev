---
name: meta-sweep
description: Call sweep-agent + scripts — archive FINISHED plans (never by age) and wip-commit untracked files
argument-hint: [--archive-only | --wip-only]
allowed-tools: [Read, Write, Bash, Glob, Grep, Agent]
model: opus
---

# /meta-sweep

Plan maintenance. Delegates to `sweep-agent` (`agents/sweep-agent.md`) which calls:

- `bash ${CLAUDE_PLUGIN_ROOT}/scripts/sweep-archive-finished.sh` — archive ONLY finished plans (deterministic guard PASS). **Age is never a reason to archive** — old-but-unfinished plans stay put.
- `bash ${CLAUDE_PLUGIN_ROOT}/scripts/sweep-wip-commit.sh` — wip-commit untracked files

Flags:
- `--archive-only` — skip wip commit
- `--wip-only` — skip archive

Config: `plans/_dashboard/settings.json` (archive path).
