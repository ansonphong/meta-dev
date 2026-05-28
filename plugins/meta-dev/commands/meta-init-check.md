---
name: meta-init-check
description: Environment health check — verifies services, tests, and dependencies before meta-execute starts
argument-hint: [backend | frontend | full | auto | refresh-cache]
allowed-tools: [Read, Write, Bash, Grep]
model: haiku
---

# /meta-init-check

Pre-execution environment health check. Verifies git health, runtime/service probes, test discoverability, and frontend/backend API contracts before a long `/meta-execute` run, so setup problems surface as a clean report instead of confusing mid-run failures.

Full procedure: `references/init-check-protocol.md`. All project-specifics (repo paths, venv layout, tool names, expected services) are resolved via the host-claude-contract fallback chain — nothing is hardcoded.

## Modes

- `backend` — git health + runtime/service probes (interpreter, app import, DB, Redis/queue) + test baseline + `.env` + FAILURES.md + STATUS.md
- `frontend` — git health + frontend toolchain (deps, typecheck, native toolchain) + test baseline
- `full` — all checks + **API contract smoke test** (frontend `/api/` URLs vs backend routes)
- `auto` (default) — detect scope from the plan being executed (`Repo:`/scope field); a plan touching both frontend and backend resolves to `full`
- `refresh-cache` — rebuild `.claude/cache/` artifacts only, then exit

## Flow

1. **Resolve scope + config.** Read the env-probe set from `bash scripts/config-get.sh meta_dev.init_check` (expected services, per-check timeouts, <30s budget) and the WSL git keys from `bash scripts/config-get.sh meta_dev.filesystem.git_corruption_mitigations`. Fall back to host CLAUDE.md, then safe defaults.
2. **Git health (per in-scope repo).** Run `CLAUDE_PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT" bash scripts/init-check.sh <repo-dir>` — does stale `.git/index.lock` removal (the one safe auto-fix), corruption detection via `git status`, dirty-tree warning, and WSL git-config verify+apply (keys from config).
3. **Service & runtime probes** (backend modes) — the probe set comes from `meta_dev.init_check.services` config; the host project supplies the actual probes. Examples: import smoke, a DB connection check (e.g. `db.engine.connect()`), a cache/broker ping (e.g. `redis-cli ping`), a task-queue import (e.g. Celery/RQ) + broker-degradation heuristic. `required:false` failures → WARN, not BLOCKED.
4. **Frontend toolchain** (frontend/full) — deps present, typecheck at error threshold, native toolchain `--version`.
5. **`.env` presence**, **test-baseline collection** (`--collect-only`), **FAILURES.md detection**, **STATUS.md staleness**.
6. **API contract smoke test** (full / both-stack plans) — grep frontend `/api/` call URLs and backend route handlers, cross-reference, report any unmatched frontend URL as **BLOCKED**. This is the most important check: a runtime 404 is worse than a missing dependency.

See the reference for the exact procedure, grep shapes, and graceful-degradation logic.

## Report

Emit the OK / WARN / BLOCKED status table from `references/init-check-protocol.md` (one row per check run), ending with `Overall: READY (W warnings)`.

**Stop-on-BLOCKED:** if any row is `BLOCKED`, list the exact fixes and stop — do NOT proceed to execution. If `READY`/`WARNING`, announce readiness and return (standalone) or hand back to `/meta-dev` Stage 5.

## Guardrails

- **Never start services. Never install dependencies.** Check, don't fix.
- The **only** auto-fixes are stale `.git/index.lock` removal and applying the configured WSL git-config keys — both always safe. Never stash, `git reset`, or `git checkout .`.
- Uncommitted changes are **warnings, not blockers**.
- **Report, don't diagnose** — surface exact error output and stop.
- **Under 30 seconds total** — honor per-check timeouts from config; no long-running tests, no builds.

Config: `bash scripts/config-get.sh meta_dev.init_check` (env-probe set, timeouts, budget) and `meta_dev.filesystem.git_corruption_mitigations` (WSL git keys). The proposed `init_check` schema block ships in `templates/settings.json` / `schemas/settings.schema.json`.
