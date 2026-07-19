---
name: meta-version
description: Multi-repo version manager — declarative versioning.json config, semver/calver/custom strategies, atomic version_files updates
argument-hint: "[status [--repo id] | bump [--repo id] [--type major|minor|patch|auto] | sync [--repo id] | config]"
allowed-tools: [Read, Write, Edit, Bash(bash:*), Bash(python3:*), Bash(git:*)]
model: opus
---

# /meta-version

Declarative version management. Config: `plans/_dashboard/versioning.json`

## Subcommands

- `status [--repo id]` → `bash ${CLAUDE_PLUGIN_ROOT}/scripts/version-status.sh`
- `bump [--repo id] [--type T]` → invoke Skill tool with `skill="version-manager"`
- `sync [--repo id]` → `bash ${CLAUDE_PLUGIN_ROOT}/scripts/version-sync.py`
- `config` → opens editor via `/meta-config`

## Auto-bump

Type `auto` reads changelog: any `breaking`→major, any `feat`→minor, else patch.

Detail: skill `version-manager`, `references/version-manager.md`.
