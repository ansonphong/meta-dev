# Meta-Dev Plugin — Development Guide

## 🔴 HARD RULE #1 — BUMP THE VERSION *AND* PUSH. BOTH. EVERY TIME.

**The rule runs in both directions and neither half is optional:**

- **Every push MUST carry a patch bump** — increment the third number in **both** `plugins/meta-dev/.claude-plugin/plugin.json` **and** `plugins/meta-dev/.codex-plugin/plugin.json` (their base versions must match; `tests/test-codex-package-surface.sh` fails on drift). `1.4.9` → `1.4.10` → `1.4.11` …
- **Every bump MUST be pushed, in the same act.** A version bump that sits local is worse than no bump: the manifest claims a version the remote has never served. **Never commit meta-dev and stop.** Commit and push are ONE action, always, no confirmation step.

**Why the bump:** plugin caches are **version-keyed** — Claude Code at `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, Codex at `~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/`. If the version does not change, the host keeps loading the frozen snapshot and **new/edited commands, skills, and agents never register**, no matter how many times you run `/plugin marketplace update`. Bumping forces a fresh cache build.

**Why the push:** the marketplace pulls from **`origin/main`, never your disk.** An unpushed commit is invisible to it — the buggy or stale version stays live and the "fix" is an illusion. This is not theoretical: on 2026-07-30 the Codex cache was still on `1.3.75` from five days earlier because two commits carrying `1.4.10` were left unpushed, so `$meta-dev:plan` did not exist in any loaded build even though the skill had been on disk the whole time.

**Procedure — one unit of work, never split:**
1. Make the change.
2. Bump the patch in **both** manifests.
3. Stage the exact paths, commit.
4. **`git -C /mnt/d/Projects/360-Hextile/meta-dev push origin main`** — note the branch is **`main`** here, not `master` like the other repos.

**Found unpushed commits on this repo? Push them.** Discovering someone else's local-only commits is not a new decision to escalate — it is this same act, interrupted. Push, then report. **The remote is the source of truth for every host, so keep it current constantly.**

After pushing, reload: `/plugin marketplace update meta-dev` + `/plugin install meta-dev@meta-dev` + restart the host — the new version cache rebuilds and the changes appear.

## Structure

> **Path confidence — read before searching.** Everything editable lives **one level down** under `plugins/meta-dev/`. The meta-dev repo root holds only `plugins/` and `.claude-plugin/` — there is **no** `commands/`, `agents/`, `skills/`, or `scripts/` at the root. So a command is `plugins/meta-dev/commands/<name>.md`, a skill is `plugins/meta-dev/skills/<name>/SKILL.md`, a script is `plugins/meta-dev/scripts/<name>`. Don't `find`/`grep` for these — the path is known.

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

## Codex Tier Quick-Reference

`/codex-execute --tier <t>` maps to a model + a default reasoning effort (override with `--effort`). Effort scale: `none | low | medium | high | xhigh | max`. **Spark bills to a SEPARATE weekly quota** from the shared `gpt-5.6` pool — route mechanical work to it first (it's effectively free capacity).

| Tier | Model | Default effort | Use for |
| --- | --- | --- | --- |
| `spark` | `gpt-5.3-codex-spark` | `low` | Bulk mechanical *code*: renames, boilerplate, lint/format, syntax triage. Free relative to the 5.6 pool. |
| `luna` | `gpt-5.6-luna` | `low` | Efficient high-volume; generalist prose/analysis lookups. |
| `terra` | `gpt-5.6-terra` | `medium` | Balanced default: normal bug fix, known-scope feature, standard diff review. |
| `sol` | `gpt-5.6-sol` | `high` | Flagship reasoning: ambiguous root cause, cross-module behavior, security, architecture, migrations. |

Source of truth: `plugins/meta-dev/scripts/codex-headless-exec` (tier→model map) + `plugins/meta-dev/commands/codex-execute.md` (routing doctrine). `gpt-5.6-codex` is deliberately absent — rejected by the ChatGPT-account API.

## Plan Targets — Authoring Depth

Plans carry an optional `target: lean | standard | explicit` (absent means `standard`) that scales authoring depth and gap-scan breadth to the capability of the executing model. **`plugins/meta-dev/references/plan-targets.md` is the ONE definition** — tier table, tier↔backend map, capability ordering, blast-radius override, and the dispatch mismatch rule. `meta-planner`, `codex-writing-plans`, and `meta-loop-gap` link to it; none restates it, and neither should anything else.

The field is optional at both IR versions. `plan-artifact-render.py` hand-rolls every check (stdlib only, no `jsonschema`), so an enum lives in **two** places — the schema for authoring and `validate_ir` for runtime. Changing one alone silently does nothing.

## Principles

1. **Skills > commands for reuse.** Command = entry. Skill = procedure.
2. **Scripts > LLM for determinism.** State updates, version bumps, changelog cuts -> scripts/*.sh
3. **Event-driven > polling.** Hooks fire on file/git events.
4. **JSON-first config.** All customization in JSON with schemas.
5. **References pattern.** Command/skill body <=30 lines. Detail in references/.

## State Layer (`planctl`)

Markdown plan files are the **git truth**; a disposable SQLite read-model at `~/.cache/meta-dev/<project-slug>/` (off-9p, ext4) makes every view fast. **`planctl` is the ONLY write door** — every state mutation (check/uncheck, stage, claim, review, runbook) routes through `python3 -m planctl <verb>` (via the `scripts/planctl.sh` bash shim). Legacy shells (`task-done.sh`, `stage-emit.sh`, `worker-claim.sh`) are now thin shims delegating to planctl.

- Design doc: `plans/meta/meta-dev-unified-state/2026-07-17-unified-state-layer-design.md`
- Master plan: `plans/meta/meta-dev-unified-state/00-master-plan.md`
- Source: `plugins/meta-dev/scripts/planctl/` (python3 stdlib only)
- Invocation: `bash plugins/meta-dev/scripts/planctl.sh <verb> [--json]`

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
- **Command-pairing invariant:** every `meta-<name>` command has a bare `<name>` shortcut (same dir) that is a pure redirect — body `Execute /meta-<name> $ARGUMENTS`. They are ONE command. When either form is typed, invoke `meta-dev:meta-<name>` directly; never deliberate between the pair (each shortcut's `description:` says so explicitly). Exceptions with no `meta-` counterpart: `housekeeping` (standalone command). Exceptions with no **bare** twin: `meta-compact`, `meta-config`, `meta-init` — Claude Code ships built-in `/compact`, `/config` and `/init`, so a bare twin would shadow the built-in instead of redirecting. These are meta-only by design and are exempted in `tests/test-codex-parity.sh`. `sniff-test` is **skill-only** — it has NO command wrapper; the `sniff-test` skill (`skills/sniff-test/`) is invoked directly as `/sniff-test`, so there is exactly one slash entry, not a command+skill pair.
