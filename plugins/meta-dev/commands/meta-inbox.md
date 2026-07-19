---
name: meta-inbox
description: Issue inbox — single surface for all issues (overlord findings, review failures, sweep anomalies, repair dossiers). View, resolve, dismiss, or auto-clear.
argument-hint: "[list | add | resolve <id> | dismiss <id> | clear [all | --source S | --severity S | --dry-run] | render | archive]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /meta-inbox

Single surface for all issues across the harness.

## Subcommands

- `list [--status open|all] [--source S] [--severity S]` → `bash ${CLAUDE_PLUGIN_ROOT}/scripts/inbox-list.sh`
- `add` → interactive OR `bash ${CLAUDE_PLUGIN_ROOT}/scripts/inbox-add.sh <flags>`
- `resolve <id> [--note N]` → `bash ${CLAUDE_PLUGIN_ROOT}/scripts/inbox-resolve.sh <id>`
- `dismiss <id> [--reason R]` → resolve with status=dismissed
- `clear [all]` → invoke Skill tool with `skill="inbox-clearer"`, scope = auto-clearable
- `clear with best practices` → Skill tool `skill="inbox-clearer"` with `--code-review-per-fix`
- `clear --source X --severity Y --dry-run --model opus` → filtered/preview/forced-model clear
- `render` → regenerate INBOX.md
- `archive` → `bash ${CLAUDE_PLUGIN_ROOT}/scripts/inbox-archive.sh`

## No-arg behavior

Print rendered inbox via `bash ${CLAUDE_PLUGIN_ROOT}/scripts/inbox-render.py`.

Detail: skill `inbox-clearer`.
