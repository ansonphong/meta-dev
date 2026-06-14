---
name: meta-config
description: Read/write meta-dev harness configuration. Three-layer JSON cascade with schema validation.
argument-hint: [get <path> | set <path> <value> [--local] | reset | export | import <file>]
allowed-tools: [Read, Write, Bash(bash:*)]
model: opus
---

# /meta-config

Manage `plans/_dashboard/settings.json` (and `versioning.json`, `changelog.json`).

## Subcommands

- `get <path>` -- `bash ${CLAUDE_PLUGIN_ROOT}/scripts/config-get.sh <path>`
- `set <path> <value> [--local]` -- `bash ${CLAUDE_PLUGIN_ROOT}/scripts/config-set.sh <path> <value> [project|local]`
- `reset` -- copy templates over project settings (confirm first)
- `export` -- print merged config via `${CLAUDE_PLUGIN_ROOT}/scripts/config-merge.py`
- `import <file>` -- replace from file (validate first)

## No-arg behavior

Run `${CLAUDE_PLUGIN_ROOT}/scripts/config-merge.py`, print current merged settings tree interactively.

Detail: `references/config-cascade.md`.
