# Meta-Dev Plugin — Development Guide

## 🔴 HARD RULE #1 — BUMP VERSION EVERY PUSH

**Every push to origin MUST bump the patch version (third number) in `plugins/meta-dev/.claude-plugin/plugin.json`.** `1.0.X` → increment X by 1 each push (1.1.0 → 1.1.1 → 1.1.2 …).

**Why:** Claude Code caches installed plugins under `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`. The cache is **version-keyed**. If the version does not change, Claude keeps loading the frozen cached snapshot and **new/edited commands, skills, and agents never register** — no matter how many times you `/plugin marketplace update`. Bumping the patch number forces a fresh cache build on the next update.

**Procedure (do this as part of every push, never skip):**
1. Edit `plugin.json` → bump patch (`version` field).
2. Stage the bump with the rest of the change.
3. Commit + push.

After pushing, the user reloads with `/plugin marketplace update meta-dev-marketplace` + `/plugin install meta-dev@meta-dev-marketplace` + restart — the new version cache rebuilds and changes appear.

## Structure

```
meta-dev/
├── .claude-plugin/marketplace.json    # Marketplace catalog
├── plugins/meta-dev/                  # The plugin
│   ├── .claude-plugin/plugin.json     # Plugin manifest
│   ├── commands/                      # Thin entry points (<=30 lines)
│   ├── agents/                        # Specialized subagents
│   ├── skills/                        # Heavy procedures (load on-demand)
│   ├── hooks/scripts/                 # Bash event handlers
│   ├── scripts/                       # Deterministic ops (no LLM)
│   ├── schemas/                       # JSON schemas
│   ├── templates/                     # Bootstrap files for /meta-init
│   └── references/                    # Plugin-level docs
```

## Principles

1. **Skills > commands for reuse.** Command = entry. Skill = procedure.
2. **Scripts > LLM for determinism.** State updates, version bumps, changelog cuts -> scripts/*.sh
3. **Event-driven > polling.** Hooks fire on file/git events.
4. **JSON-first config.** All customization in JSON with schemas.
5. **References pattern.** Command/skill body <=30 lines. Detail in references/.

## Testing

```bash
bash plugins/meta-dev/scripts/test-plugin.sh          # Full suite
bash plugins/meta-dev/scripts/test-plugin.sh --check-schemas  # Schemas only
bash plugins/meta-dev/scripts/test-plugin.sh --check-scripts   # Scripts only
```

## Conventions

- `${CLAUDE_PLUGIN_ROOT}` for all plugin-relative paths
- `${PROJECT_ROOT}` or `plans/` for project-relative paths
- Commit messages: `feat(phase):`, `fix(phase):`, `chore(phase):`
- **Command-pairing invariant:** every `meta-<name>` command has a bare `<name>` shortcut (same dir) that is a pure redirect — body `Execute /meta-<name> $ARGUMENTS`. They are ONE command. When either form is typed, invoke `meta-dev:meta-<name>` directly; never deliberate between the pair (each shortcut's `description:` says so explicitly). Exceptions with no `meta-` counterpart: `housekeeping` (standalone command). `sniff-test` is **skill-only** — it has NO command wrapper; the `sniff-test` skill (`skills/sniff-test/`) is invoked directly as `/sniff-test`, so there is exactly one slash entry, not a command+skill pair.
