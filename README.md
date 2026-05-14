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

## Dashboard

Run `/meta-dashboard` to see your entire development operation at a glance.

```
🎛  Control Plane — acme-platform

2026-05-14 14:22 UTC

╔══════════════════════════════════════════════════════════════════════════════╗
║                              P L A N S                                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  🔐 auth-refactor           ████████████████████  24/24   ✅ shipped        ║
║  💳 payments-v2             ██████████████░░░░░░  18/28   🟡 in-flight      ║
║  🏠 onboarding-flow         ██████░░░░░░░░░░░░░░   7/22   🟡 in-flight      ║
║  🔍 search-v3               ░░░░░░░░░░░░░░░░░░░░   0/14   ⬜ pending        ║
║                                                                              ║
║  ────────────────────────────────────────────────────────────────────────   ║
║  TOTAL                                           49/88   56%                 ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║                       A C T I V E   S E S S I O N S                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ┌──────────────────┬──────────────────────┬───────────┬──────────────────┐  ║
║  │     Session      │        Plan          │   Task    │      Stage       │  ║
║  ├──────────────────┼──────────────────────┼───────────┼──────────────────┤  ║
║  │ meta-exec-03     │ payments-v2          │ P4.3/7    │ review           │  ║
║  │ meta-exec-04     │ onboarding-flow      │ P2.1/5    │ implement        │  ║
║  │ overlord-watch   │ payments-v2          │ —         │ reviewing P4.2    │  ║
║  └──────────────────┴──────────────────────┴───────────┴──────────────────┘  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║              I N B O X   ·   A D V I S O R I E S                            ║
║                     awaiting your green-light                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ┌────────────┬─────────────────────────────────────────────────────────┐    ║
║  │     ID     │                        Awaits                           │    ║
║  ├────────────┼─────────────────────────────────────────────────────────┤    ║
║  │ inb_01h9a2 │ 🟦 loop-gap done on auth-refactor — approve?            │    ║
║  │            │   advice: executable, risk-low, 0 blockers               │    ║
║  │            │   [1] approve → /meta-execute plans/auth-refactor       │    ║
║  │            │   [2] another review pass                                │    ║
║  │            │   [3] hold + ask question                                │    ║
║  ├────────────┼─────────────────────────────────────────────────────────┤    ║
║  │ inb_01h9b7 │ 🟦 deploy gate — auth-refactor ready for production     │    ║
║  │            │   [1] deploy now → /meta-ship auth-refactor             │    ║
║  │            │   [2] schedule for later                                 │    ║
║  └────────────┴─────────────────────────────────────────────────────────┘    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║                I N B O X   ·   I S S U E S                                  ║
║                  7 open  ·  4 auto-clearable                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ┌────────────┬──────────────────────────────────┬─────────────┬────────────┐ ║
║  │     ID     │              Title               │   Source    │  Severity  │ ║
║  ├────────────┼──────────────────────────────────┼─────────────┼────────────┤ ║
║  │ inb_01h7c3 │ Checkbox drift on P4.6c          │ overlord    │ 🟡 mod     │ ║
║  │ inb_01h7d1 │ Test flake: rate_limit_429       │ review      │ 🔴 high    │ ║
║  │ inb_01h7e8 │ Unused import in auth.py         │ sweep       │ 🟢 low     │ ║
║  │ inb_01h7f2 │ Schema drift on payment_status   │ overlord    │ 🟡 mod     │ ║
║  │ inb_01h7f9 │ Stale TODO in plan checklist     │ sweep       │ ⚪ trivial  │ ║
║  │ inb_01h8a4 │ Missing coverage: webhook.py     │ review      │ 🟡 mod     │ ║
║  │ inb_01h8b1 │ Config missing from local layer  │ review      │ 🟢 low     │ ║
║  └────────────┴──────────────────────────────────┴─────────────┴────────────┘ ║
║                                                                              ║
║  → /meta-inbox clear all          (clears 4 auto items, sonnet/haiku)       ║
║  → /meta-inbox clear with best practices   (review-gated)                   ║
║  → /meta-inbox clear --model opus          (heavy thinking for hard items)  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║                    S W E E P   L O G   ( 2 4 h )                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ✓  archived 2 stale plans — search-prototype, api-experiment  (14:00 UTC)  ║
║  ✓  wip commit on 3 untracked files  (13:15 UTC)                            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║                 R E C E N T   C O M M I T S                                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  a7f3d92  feat(payments): add Stripe webhook handler          2 min ago     ║
║  b2e8c41  fix(auth): resolve token refresh race               14 min ago    ║
║  9c1d5f6  chore(plan): mark P4.2 checkboxes DONE              31 min ago    ║
║  e4f7a83  feat(payments): implement checkout session create   1 hour ago    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

refresh: fast  ·  agents: 2 haiku  ·  dirty: 3  ·  unpushed: 0

  [new idea]    [plan]    [execute]    [review]    [ship]    [overlord]
```

One glance. Every plan, session, inbox advisory, and commit. The Overlord watches plan edits and auto-reviews completed tasks. Issues flow into the inbox. You clear them with a single command. Sweep keeps the repo tidy. All driven by event-sourced state — replayable, auditable, zero drift.

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
