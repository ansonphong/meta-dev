# Meta-Dev

Autonomous development harness for Claude Code and Codex. Dashboard, overlord, **6-stage waterfall**, HOTL classification, deep-investigation probe, changelog engine, multi-repo versioning — all configurable via JSON.

## The 6-stage waterfall

This is the core of the harness. `/meta-dev` drives every non-trivial piece of work through **six stages, in this order**. Do not skip stages. Do not write code before Stage 5.

```
 1 BRAINSTORM  →  2 DESIGN  →  3 PLAN  →  4 HARDEN  ━━  5 EXECUTE  →  6 REVIEW
    intent           spec         tasks        gaps          code          verify
                                                 ▲
                                      default stop here
                                      Stage 5 needs an explicit go
```

```mermaid
flowchart LR
  S1["1 BRAINSTORM<br/>explore intent"] --> S2["2 DESIGN<br/>spec + architecture"]
  S2 --> S3["3 PLAN<br/>tasks + files + deps"]
  S3 --> S4["4 HARDEN<br/>gap-scan until clean"]
  S4 --> S5["5 EXECUTE<br/>write code — needs go"]
  S5 --> S6["6 REVIEW<br/>verify + archive"]
```

| # | Stage | What happens | Writes code? | Command |
|---|-------|--------------|--------------|---------|
| **1** | **Brainstorm** | Explore intent, constraints, alternatives. No plan yet. | No | `/meta-dev` |
| **2** | **Design** | Spec and architecture: data models, APIs, UX, decisions. | No | `/meta-dev` |
| **3** | **Plan** | Task-level plan: phases, file paths, deps, focused verify. | No | `/meta-planner` |
| **4** | **Harden** | Gap-scan the plan until no gaps remain. **Default stop.** | No | `/loop-gap` |
| **5** | **Execute** | Implement task-by-task. **Needs an explicit go.** | **Yes** | `/meta-execute` |
| **6** | **Review** | Code review, eval, archive, context sync. | No (review only) | `/meta-eval` |

```bash
/meta-dev <subject>           # Stages 1–4, then halt. Nothing ships until you say go.
/meta-dev <subject> --to 6    # Full waterfall. Stage 5 still needs an explicit go.
```

**Rules that do not bend:**
- Stages 1–4 are planning and docs only. Source code starts at Stage 5.
- Default stop is **Stage 4**. Approving a plan is not permission to execute it.
- Quick fixes (typos, one-file config) may skip to Stage 5. Everything else uses the full waterfall.
- Claude Code and Codex run the same six stages. `planctl` is the only state write door.

## Prerequisites

- **Claude Code** (latest) for the slash-command surface, or **Codex** for the native skill surface
- `jq` ≥ 1.6, `python3` ≥ 3.10, `shellcheck` ≥ 0.7
- Python package: `jsonschema` (`pip install jsonschema`)
- Optional: `ulid-py` (falls back to uuid4)

```bash
brew install jq shellcheck
pip install jsonschema
```

## Install in Claude Code

```bash
/plugin marketplace add ansonphong/meta-dev
/plugin install meta-dev@meta-dev
```

Verify:

```bash
/meta-dashboard
```

## Install in Codex

From this repository's root, add the local marketplace described by
`.agents/plugins/marketplace.json`, then install its available `meta-dev`
plugin:

```bash
codex plugin marketplace add .
codex plugin add meta-dev@meta-dev
```

To refresh an already-installed copy after a push, use the update script — it
upgrades the marketplace snapshot and reinstalls the current version:

```bash
bash plugins/meta-dev/scripts/plugin-refresh.sh
```

Restart Codex after installation. Canonical Claude commands are exposed under
the same names as native Codex skills:

```text
$meta-dev:meta-planner <request-or-plan>
$meta-dev:meta-execute <plan>
$meta-dev:meta-dashboard
$meta-dev:meta-canary <target>
```

In ChatGPT/Codex surfaces with the `@` skill picker, select the same fully
qualified skill, for example `@meta-dev:meta-planner`. Codex CLI and the IDE use
`$`. Literal plugin-defined `/meta-planner` is not a Codex extension surface.

For a normal medium implementation plan, invoke the native Superpowers bridge:

```text
$meta-dev:plan Write a self-contained implementation plan for <change>.
Save it under plans/<repo>/ and do not implement it.
```

For a full master plan with phase files, use the familiar command name:

```text
$meta-dev:meta-planner <request-or-existing-plan>
```

To execute an approved plan, use the matching host-neutral helper. It runs the
execute→review→fix loop directly — one worker per checkbox, focused causal
verification, a durable commit per task, and `planctl` as the only write door —
rather than routing through the Claude command adapter:

```text
$meta-dev:execute <plan>
```

It requires an explicit go for that plan; a saved plan alone is not permission.
The six host-neutral helpers are `plan`, `execute`, `harden`, `review`,
`diagnose`, and `ops`.

Claude can obtain its planning discipline from the external Superpowers plugin.
Codex does not inherit that Claude plugin dependency, so meta-dev packages an
adapted `writing-plans` contract directly. It inspects the live codebase, writes
for a fresh agent with no conversation history, and saves ordinary medium work
as `plans/<repo>/YYYY-MM-DD-<slug>.md`.

Claude commands remain canonical procedures. Codex packages every real command
once under its canonical name. Pure bare redirects such as `planner` →
`meta-planner` remain Claude aliases so Codex's limited initial skill index does
not overflow. `command-router` is retained only as a compatibility fallback.

Codex uses native configured routes: plan, harden, and review default to
GPT-5.6 Sol with high reasoning effort; execute defaults to GPT-5.6 Terra with
medium effort. The `codex-headless-exec` runner also defaults to Terra/medium.
An explicit `--model` overrides `--tier`; an explicit `--effort` overrides the
tier's default effort. Workflow route defaults are configured under
`meta_dev.codex.models`.

Codex lifecycle hooks are bundled with the plugin. Trust the installed plugin
normally so its adapter can apply the shared guard policy to Codex tool events;
do not use `--dangerously-bypass-hook-trust` in normal work.

## Quick Start

```bash
/meta-init              # Bootstrap harness in current project
/meta-dashboard         # View control plane
/meta-config            # Customize settings
```

`/meta-init` creates `plans/_dashboard/` with settings, versioning, changelog, state, and inbox — all validated against JSON schemas. Idempotent (safe to re-run).

## Shared workflow contract

Both host surfaces run the same six-stage waterfall (see the top of this README).
Plans and their state remain host-neutral: `planctl` is the only state write
door, and the conductor owns stage transitions and the checkbox ledger.

Plan artifacts are rendered from the versioned JSON IR in
`schemas/plan-artifact.schema.json`, not hand-written per host. Version `1.0`
preserves the shared Claude and multi-phase contract. Native Codex planning uses
version `1.1` for execution-grade single-file plans: verified codebase ground
truth, decisions, exact task interfaces and anchors, ordered work, focused
commands with expected results, failure handling, blast radius, and rollback.
The renderer emits deterministic frontmatter without `status:`. Multi-phase
plans keep one checkbox ledger in `00-master-plan.md`; version `1.1` single-file
plans contain no Markdown checkbox rows.

Repository topology is likewise host-neutral. Put project repository aliases in
`.meta-dev/repos.json`; the legacy `.claude/meta-dev-repos.json` remains
supported for compatibility. If both exist, the neutral file takes precedence.

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
║  │            │   [1] deploy now → project /deploy or APP /release      │    ║
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

> **`[execute]` = autopilot.** Routes through the orchestrator and runs the full sequence — **harden (`/loop-gap`) → execute (`/meta-execute`) → code review (`superpowers:requesting-code-review`)** — not execute-only. Hardening is default-on; pass `--no-harden` to skip it. See the Autopilot sequence in `meta-orchestrator.md`.

One glance. Every plan, session, inbox advisory, and commit. The Overlord watches plan edits and auto-reviews completed tasks. Issues flow into the inbox. You clear them with a single command. Sweep keeps the repo tidy. All driven by event-sourced state — replayable, auditable, zero drift.

## Architecture

```
plugin root/
├── .claude-plugin/ Manifest for Claude Code
├── .codex-plugin/  Manifest for Codex
├── commands/      Thin entry points (≤30 lines) — delegate to skills/scripts
├── workflow-skills/ Shared Claude procedures — loaded on demand via Skill tool
├── skills/        Canonical Codex command skills plus compact workflow helpers
├── agents/        Specialized subagents — scanner, reviewer, architect, sweeper
├── hooks/         Codex lifecycle hook declarations and adapter
│   └── scripts/   Event-driven bash/Python handlers
├── scripts/       Deterministic ops — no LLM, pure bash/python
├── schemas/       JSON Schema draft-07 — settings, state, inbox, changelog, versioning
├── templates/     Bootstrap files for /meta-init
└── references/    Deep-dive docs per component
```

**Data flow:** hooks write events → `state.events.jsonl` → `state-reduce.py` materializes `state.json` → dashboard/overlord read state. All event-sourced, replayable.

**State layer (`planctl`):** Markdown plan files are git truth; a disposable SQLite read-model at `~/.cache/meta-dev/<project-slug>/` (off-9p, ext4) makes every view fast. `planctl` is the **only write door** for state mutations (check/uncheck, stage, claim, review, runbook). Legacy scripts (`task-done.sh`, `stage-emit.sh`, `worker-claim.sh`) are thin shims over it. Invoke via `bash plugins/meta-dev/scripts/planctl.sh <verb> [--json]`. See `CLAUDE.md` → "State Layer" and `plans/meta/meta-dev-unified-state/` for the design.

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
| `/meta-dev` | 6-stage waterfall: brainstorm → design → plan → harden → execute → review |
| `/meta-classify` | HOTL vs HITL task classification by blast radius |
| `/meta-dod` | Generate definition-of-done contracts from task descriptions |
| `/meta-planner` | Restructure plans for automated execution |
| `/meta-execute` | Subagent-driven plan execution with verify+commit+push per task |
| `/meta-eval` | Dedicated evaluator — tests implementations against design criteria |
| `/meta-canary` | Post-deploy health monitor (ops workflow; learned patterns → APP `/release`) |

### Review & Quality
| Command | Purpose |
|---------|---------|
| `/meta-review-batch` | Batched code review queue with verdict routing |
| `/meta-security` | Security audit — OWASP Top 10 + STRIDE threat modeling |
| `/meta-ux` | Comprehensive UX evaluation — multi-wave assessment |
| `/meta-review-design` | Design quality audit — coherence, originality, craft, anti-slop |
| `/meta-audit` | Harness simplification audit — detect unused/overhead components |
| `/meta-probe` | Exhaustive deep-investigation probe — diverse-agent fan-out, adversarial debate, LLM bias-loop breaking, one report that opens a conversation |

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

## Deep Investigation — `/meta-probe`

The harness's heaviest thinking tool. Point it at one hard question — a bug nobody can crack, an architecture call, a loop where the same wrong answer keeps coming back — and it throws the kitchen sink: many agents across many angles, adversarial debate, real experiments, and a single report that **opens a conversation** instead of closing one. **It never edits source and never commits** — it investigates; fixing is a separate `/meta-execute` step the report can recommend.

```bash
/meta-probe "why does the feed query slow only past ~2k rows" --budget high
/meta-probe backend/app/services/feed.py:142 --budget insane
/probe feature:starlight-decay --budget medium --background
```

**Budget tiers** scale agents, debate rounds, experiments, and recursion:

| Budget | Fan-out | Behavior |
|--------|---------|----------|
| `low` | ~8 agents, 1 round | Focused look at the issue + adjacent angles |
| `medium` | ~18 agents, 2 rounds | Multi-angle + adversarial debate |
| `high` | ~30 agents, 3+ rounds | Full debate + experiments on survivors |
| `insane` | 50+ agents, recursive | Sub-probe per unsettled hypothesis; runs for hours until exhaustive |

**Bias-loop breaking is the core feature** (full protocol: [`references/probe-debiasing.md`](plugins/meta-dev/references/probe-debiasing.md)). Depth alone *amplifies* a shared bias, so the structure forces diversity + adversarial pressure + evidence instead:

- **Neutral re-framing + premise inversion** — strips your framing so agents don't anchor on it.
- **Diverse strategies (DMAD)** — every agent uses a *different* method; never clones.
- **Preset-stance debate + external critique** — hypotheses defended by assigned advocates and attacked by *other* agents (no self-grading).
- **Consider-the-opposite + pre-mortem** — every conclusion must produce its own counterexample.
- **Ground-truth injection** — every load-bearing claim cites `file:line` / command output; experiments settle ties.
- **Banned majority vote** — a hypothesis survives by withstanding the strongest counter, not by being popular.
- **Forbidden ruts** — mistakes already tried (mined from git log + prior probes) are named and banned up front.

**Long-horizon discipline** keeps multi-hour `insane` runs *productive* instead of drifting (grounded in [Anthropic's long-running-agent guidance](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)): the orchestrator holds distilled artifacts only, all state lives in an externalized ledger (`probe-{slug}-state.md`), context compacts between rounds, and a fresh-context reviewer checks the trajectory every 3 rounds.

**Compute is justified only while an unexplored avenue could change the verdict.** Every round ends with a mandatory contemplation — *is there any other avenue we could look down? have we been exhaustive?* — and the probe continues only if a real, potentially-decisive avenue remains. When the frontier is dry, it stops and concludes. Long when it's productive; never spinning for the sake of it.

Output lands at `plans/meta/probe-{slug}-{date}.md`: verdict + confidence, hypothesis tournament, what was ruled out and why, open questions with the experiment that would resolve each, and pointed conversation-starters back to you. Interactive by default; `--background` detaches and posts an inbox advisory when done.

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

## Sonnet / Backend Compatibility

Meta-dev hooks and scripts are pure bash/jq/python — no model-specific code paths. Plans generated by meta-dev are hardened for Sonnet-class models (Claude Sonnet 5, Opus 4.8, and compatible backends):

- All harness primitives (Skills, TaskCreate, Agent, hooks, MCP) work at the harness layer
- Subagents default to the configured model — pass explicit `model:` overrides for reasoning-heavy tasks
- `headless-worker` skill documents env-var inheritance for headless execution
- See `plugins/meta-dev/workflow-skills/headless-worker/references/backend-env.md`

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
