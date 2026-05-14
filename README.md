# Meta-Dev

Autonomous development harness for Claude Code. Dashboard, overlord, 6-phase orchestrator, HOTL classification, changelog engine, multi-repo versioning — all configurable via JSON.

## Prerequisites

- **Claude Code** (latest)
- `jq` ≥ 1.6, `python3` ≥ 3.10, `shellcheck` ≥ 0.7
- Python package: `jsonschema` (`pip install jsonschema`)
- Optional: `ulid-py` (falls back to uuid4)

```bash
brew install jq shellcheck
pip install jsonschema
```

## Install

```bash
/plugin marketplace add ansonphong/meta-dev
/plugin install meta-dev@meta-dev-marketplace
```

Verify:

```bash
/meta-dashboard
```

## Quick Start

```bash
/meta-init              # Bootstrap harness in current project
/meta-dashboard         # View control plane
/meta-config            # Customize settings
```

`/meta-init` creates `plans/_dashboard/` with settings, versioning, changelog, state, and inbox — all validated against JSON schemas. Idempotent (safe to re-run).

## Architecture

```
CLAUDE_PLUGIN_ROOT/
├── commands/      Thin entry points (≤30 lines) — delegate to skills/scripts
├── skills/        Heavy procedures — loaded on demand via Skill tool
├── agents/        Specialized subagents — scanner, reviewer, architect, sweeper
├── hooks/scripts/ Event-driven bash handlers — SessionStart, PostToolUse
├── scripts/       Deterministic ops — no LLM, pure bash/python
├── schemas/       JSON Schema draft-07 — settings, state, inbox, changelog, versioning
├── templates/     Bootstrap files for /meta-init
└── references/    Deep-dive docs per component
```

**Data flow:** hooks write events → `state.events.jsonl` → `state-reduce.py` materializes `state.json` → dashboard/overlord read state. All event-sourced, replayable.

## Commands

### Control Plane
| Command | Purpose |
|---------|---------|
| `/meta-dashboard` | Control plane — plans, sessions, inbox, sweep log, recent commits |
| `/meta-config` | Read/write harness settings (3-layer cascade) |
| `/meta-inbox` | Single surface for all issues + advisories |
| `/meta-overlord` | Watch plan execution, auto-review, fix gaps within threshold |

### Development Lifecycle
| Command | Purpose |
|---------|---------|
| `/meta-dev` | 6-phase orchestrator: classify → dod → plan → execute → review → ship |
| `/meta-classify` | HOTL vs HITL task classification by blast radius |
| `/meta-dod` | Generate definition-of-done contracts from task descriptions |
| `/meta-planner` | Restructure plans for automated execution |
| `/meta-execute` | Subagent-driven plan execution with verify+commit+push per task |
| `/meta-eval` | Dedicated evaluator — tests implementations against design criteria |
| `/meta-ship` | Release pipeline — changelog cut + version bump + deploy |

### Review & Quality
| Command | Purpose |
|---------|---------|
| `/meta-review-batch` | Batched code review queue with verdict routing |
| `/meta-security` | Security audit — OWASP Top 10 + STRIDE threat modeling |
| `/meta-ux` | Comprehensive UX evaluation — multi-wave assessment |
| `/meta-review-design` | Design quality audit — coherence, originality, craft, anti-slop |
| `/meta-audit` | Harness simplification audit — detect unused/overhead components |

### Maintenance
| Command | Purpose |
|---------|---------|
| `/meta-changelog` | Engineering changelog — add, cut, status |
| `/meta-version` | Multi-repo version manager — bump, sync, cascade |
| `/meta-sweep` | Autonomous cleanup — archive stale plans, wip commits |
| `/meta-repair` | 3-attempt auto-fix loop with failure dossier |
| `/meta-headless` | Headless `claude -p` worker with tool allowlists |
| `/meta-init-check` | Pre-execution environment health check |
| `/meta-canary` | Post-deploy health monitor |
| `/meta-guard` | Safety hooks — intercept dangerous commands |
| `/housekeeping` | Post-completion cleanup — archive plans, update status |

## Config

All settings in `plans/_dashboard/settings.json`. Three-layer deep merge:

| Layer | Path | Purpose |
|-------|------|---------|
| Defaults | `templates/settings.json` | Shipped with plugin, read-only |
| Project | `plans/_dashboard/settings.json` | Committed, shared with team |
| Local | `plans/_dashboard/settings.local.json` | Gitignored, per-machine overrides |

```bash
/meta-config                                    # print merged config
/meta-config get meta_dev.overlord.model        # dot-notation lookup
/meta-config set meta_dev.overlord.model opus   # set in project layer
/meta-config set changelog.auto_cut_on weekly --local  # local override
/meta-config reset                              # restore defaults
```

Key settings:

```json
{
  "meta_dev": {
    "components": { "overlord": true, "changelog": true },
    "overlord": { "trigger": "on_plan_edit", "auto_fix": "moderate_and_below" },
    "gates": { "low_risk": "auto_execute", "medium_risk": "review_after", "high_risk": "gate_before_execute" }
  }
}
```

## DeepSeek V4 / Backend Compatibility

Meta-dev hooks and scripts are pure bash/jq/python — no model-specific code paths. If running Claude Code with DeepSeek V4 Pro via the Anthropic-compatible shim (`ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`):

- All harness primitives (Skills, TaskCreate, Agent, hooks, MCP) work at the harness layer
- Subagents default to V4-Flash — commands that spawn agents at runtime pass explicit `model:` overrides
- `headless-worker` skill documents env-var inheritance (`ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` needed)
- See `plugins/meta-dev/skills/headless-worker/references/backend-env.md`

## Testing

```bash
bash plugins/meta-dev/scripts/test-plugin.sh           # all checks
bash plugins/meta-dev/scripts/test-plugin.sh --check-schemas   # schemas only
bash plugins/meta-dev/scripts/test-plugin.sh --check-scripts    # scripts only
```

## Contributing

See [CLAUDE.md](CLAUDE.md) for plugin architecture, conventions, and development guide.

## License

MIT
