# Meta-Dev Plugin — Development Guide

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
