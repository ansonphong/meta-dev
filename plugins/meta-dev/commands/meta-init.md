---
name: meta-init
description: Bootstrap meta-dev harness in a project — create plans/ structure, copy templates, configure .gitignore and AGENTS-first host adapters
argument-hint: [--auto | --dry-run]
allowed-tools: [Read, Write, Edit, Bash(bash:*), Bash(python3:*), Bash(git:*)]
model: opus
---

# /meta-init

Project bootstrap for meta-dev harness. Runs `${CLAUDE_PLUGIN_ROOT}/scripts/init-project.sh` which handles setup interactively.

## Subcommands

- No args → interactive (prompts for confirmations)
- `--auto` → non-interactive, use defaults
- `--dry-run` → show what would be created without writing

## What it does

1. Detect project name (dir name or package.json)
2. Create `plans/` structure with subdirs
3. Copy templates with `{{var}}` substitution
4. Append .gitignore entries
5. Create root `AGENTS.md` and only the required host adapters
6. Bootstrap changelog
7. Validate JSON files
8. Optional git commit

**Idempotent:** Skips files with existing `$schema` ref.

Detail: `${CLAUDE_PLUGIN_ROOT}/scripts/init-project.sh`.
