# Meta-Dev

Autonomous development harness for Claude Code. Dashboard, overlord, 6-phase orchestrator, HOTL classification, changelog engine, multi-repo versioning — all configurable via JSON.

## Install

```bash
/plugin marketplace add ansonphong/meta-dev
/plugin install meta-dev@meta-dev-marketplace
```

## Quick Start

```bash
/meta-init          # Bootstrap harness in current project
/meta-dashboard     # View control plane
/meta-config        # Customize settings
```

## Commands

| Command | Purpose |
|---------|---------|
| `/meta-dashboard` | Control plane — plans, sessions, inbox, sweep log |
| `/meta-init` | Bootstrap harness in any project |
| `/meta-overlord` | Watch plan execution, auto-review, fix gaps |
| `/meta-config` | Read/write harness settings |
| `/meta-inbox` | Single surface for all issues + advisories |
| `/meta-changelog` | Engineering changelog — add, cut, status |
| `/meta-version` | Multi-repo version manager — bump, sync |
| `/meta-classify` | HOTL vs HITL task classification |
| `/meta-execute` | Subagent-driven plan execution |
| `/meta-dod` | Definition of Done — verify completion criteria |
| `/meta-planner` | Restructure plans for automated execution |
| `/meta-ship` | Release pipeline — changelog cut + version bump + deploy |

## Config

All settings in `plans/_dashboard/settings.json`. Three-layer cascade: defaults -> project -> local.

```bash
/meta-config                              # interactive
/meta-config set overlord.model opus
/meta-config set changelog.auto_cut_on weekly --local
```

## Full Docs

See [CLAUDE.md](CLAUDE.md) for full command reference, agent config, skill API, and architecture docs. Reference specs in `plugins/meta-dev/references/`.

## License

MIT
