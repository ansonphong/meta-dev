---
name: meta-init-check
description: Environment health check — verifies services, tests, and dependencies before meta-execute starts
argument-hint: [backend | frontend | full | auto | refresh-cache]
allowed-tools: [Read, Write, Bash, Grep]
model: haiku
---

# /meta-init-check

Pre-execution environment health check. Verifies git, Python venv, PostgreSQL, Redis, Bun, SvelteKit, .env.

## Modes

- `backend` — git health + Python venv + DB + Redis + env vars
- `frontend` — Bun + node_modules + Svelte check + lint
- `full` — all checks + E2E readiness + API contract smoke test + cache write
- `auto` (default) — detect from plan scope
- `refresh-cache` — rebuild `.claude/cache/` artifacts only

Output: status table (OK/WARN/BLOCKED) with details.

Config: `plans/_dashboard/settings.json` (expected services, timeouts).
