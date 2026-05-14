---
name: meta-guard
description: Safety hooks — intercept destructive commands, optionally restrict edits to a directory scope
argument-hint: [freeze <dir>] [off] [status]
allowed-tools: [Read, Write, Bash(bash:*)]
model: haiku
---

# /meta-guard

Destructive command protection + optional edit freeze scope.

## Subcommands

- `freeze <dir>` — restrict Edit/Write to files within `<dir>`. Writes scope to `/tmp/meta-guard-freeze.scope`.
- `off` — remove freeze scope
- `status` — show protection state
- No args — verify baseline hook (careful-check.sh) is registered in settings.json

Used by `/meta-dev` Stage 5 (auto-activate before execute) and Stage 6 (deactivate after review).
