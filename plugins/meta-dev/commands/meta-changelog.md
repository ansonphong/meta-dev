---
name: meta-changelog
description: Engineering changelog — append entries during work, cut batched periods to closed files, draft release posts, pair with version bumps
argument-hint: [add --tag T --title T --body B | cut [--dry-run] | status]
allowed-tools: [Read, Write, Edit, Bash(bash:*), Bash(git:*)]
model: opus
---

# /meta-changelog

Active period: `plans/_archive/changelogs/<since>--present.md`

## Subcommands

- `add --tag <feat|fix|chore|breaking|docs> --title T --body B` → `bash ${CLAUDE_PLUGIN_ROOT}/scripts/changelog-add.sh`
- `cut [--dry-run]` → invoke Skill tool with `skill="changelog-engine"`
- `status` → `bash ${CLAUDE_PLUGIN_ROOT}/scripts/changelog-status.sh` (entries since cut, suggested bump)

## No-arg behavior

Print current period summary + suggested next bump.

Detail: skill `changelog-engine`, `references/changelog-engine.md`.
