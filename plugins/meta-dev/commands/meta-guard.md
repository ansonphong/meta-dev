---
name: meta-guard
description: Safety hooks — intercept destructive commands, optionally restrict edits to a directory scope
argument-hint: [freeze <dir>] [off] [status]
allowed-tools: [Read, Write, Bash(bash:*)]
model: haiku
---

# /meta-guard

Safety hooks. Intercepts destructive commands and enforces directory-scoped edit restrictions.

## Subcommands

- **`freeze`** — Lock scope. Any edit outside scope-root blocked. Destructive commands blocked.
- **`unfreeze`** — Release scope lock.
- **`status`** — Show current guard state (active/inactive, scope-root, blocked patterns list).

## Destructive Patterns

See `references/guard-patterns.md` for the full table. Key blocks:
- `rm -rf` (non-temp), `rm .git/index` (NEVER overrideable)
- `git reset --hard`, `git checkout .`, `git restore .` (with uncommitted changes)
- `git push --force` on main/master
- `--no-verify` flag (warn)
- `DROP TABLE/DATABASE`

## Freeze-Scope

When frozen, all edits are restricted to `scope-root`. Per `references/guard-patterns.md` freeze-scope protocol.

## Integration

Activated by `/meta-execute` during plan execution. Scope = plan's declared file set.

Config: `bash scripts/config-get.sh` for guard settings.
