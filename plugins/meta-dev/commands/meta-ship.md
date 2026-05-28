---
name: meta-ship
description: Unified release pipeline — chains version bump, build, test, deploy, and verify with non-negotiable gates between each stage
argument-hint: <target> [--dry-run] [--resume] [--abort] [--reset <version>] [--hotfix]
allowed-tools: [Read, Write, Edit, Bash, Grep, Agent]
model: sonnet
---

# /meta-ship

Release pipeline for one target: **pre-flight → version → build/deploy → verify → canary**, with a gate between every stage (a failing step halts the pipeline). The deploy step is real — it delegates to Skill `deploy-pipeline`.

Full runbook: `references/ship-pipeline.md`. Everything project-specific (targets, hosts, restart commands, health URLs, smoke tests, build/test commands, prerelease channels) is config-driven via `bash scripts/config-get.sh meta_dev.ship`.

## Arguments

- **`<target>`** — a named target profile (`meta_dev.ship.targets.<name>`). Defaults to `meta_dev.ship.default_target`. Unknown name → list profiles and exit.

| Flag | Effect |
|------|--------|
| `--dry-run` | Pre-flight checks only, then stop. No bump, build, deploy, push, or API calls. |
| `--resume` | Continue an interrupted run from its recorded `last_step`. |
| `--abort` | Cancel a run with no tag/deploy yet (clears state + draft + lock). Tag exists → use `--reset`. |
| `--reset <version>` | Confirmation-gated teardown: delete local tag, artifacts, draft, state, lock. |
| `--hotfix` | Bypass channel sequencing — patch-bump latest production tag, ship straight to production. |

```
/meta-ship www              # default flow      /meta-ship www --resume   # continue
/meta-ship app --dry-run    # pre-flight only   /meta-ship app --hotfix   # emergency patch
```

## Flow

Execute Steps 0–6 of `references/ship-pipeline.md`: parse + read Learned Patterns + acquire lock (0) → pre-flight gate, `--dry-run` stops here (1) → version/channel bump via Skill `version-manager` (2) → build/deploy; server targets gate on migrations then delegate to Skill `deploy-pipeline` (3) → post-deploy verification gate: health + smoke (4) → canary chain if `canary_target` set (5) → ship log + step-keyed rollback on failure (6).

## Gates & exit codes

Gates are non-negotiable; a failing step halts the pipeline. Exit tiers: `1` recoverable → `--resume` · `2` unrecoverable → `--reset <version>` · `3` pre-flight → fix & re-run.

## Rules

Never skip pre-flight · gates non-negotiable · one release at a time (lockfile) · commit before release · rollback guidance mandatory on failure · channels sequenced unless `--hotfix`.

## Integration

After meta-dev Stage 6 passes (grade ≥ B), meta-dev offers "Ship to production? (invokes /meta-ship)". Recurring post-deploy failures patch `## Learned Patterns` in `references/ship-pipeline.md` via canary Step 6.
