# Init-Check Protocol — Pre-Execution Environment Health

The full procedure behind `/meta-init-check`. Verifies the dev environment is healthy before a long `/meta-execute` run, so setup problems surface as a clean report instead of confusing mid-execution failures.

**Design principle:** check, never fix (with two narrow exceptions below). Report a status table and stop on `BLOCKED`. Budget: the entire check completes in **under 30 seconds** — no long-running tests, no service starts.

All project-specifics (repo paths, venv layout, tool names, test commands, expected services) are discovered via the **host-claude-contract fallback chain**: config cascade → host CLAUDE.md → safe defaults → ask. Nothing below hardcodes a project name, path, or platform.

---

## Step 0 — Resolve scope + config

Argument selects which checks run (`backend` | `frontend` | `full` | `auto` | `refresh-cache`).

1. `PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"`.
2. Read the env-probe config:
   - `bash scripts/config-get.sh meta_dev.init_check` → expected services, per-check timeouts, total budget.
   - `bash scripts/config-get.sh meta_dev.filesystem.git_corruption_mitigations` → the four WSL git keys (consumed by `init-check.sh`).
   - `bash scripts/config-get.sh meta_dev.paths.plans_root` → plans root (the runbook is `<plans_root>/meta-runbook.md`).
3. If `init_check` config is absent, fall back to host CLAUDE.md (repo list, test/build commands) then to the safe defaults in `host-claude-contract.md`.
4. **`auto`**: detect scope from the plan being executed. Read the plan's `Repo:`/scope field; map to the configured repos. A plan that touches both frontend and backend files → treat as `full`.
5. **`refresh-cache`**: rebuild `.claude/cache/` artifacts only, then exit.

**Mode → checks:**

| Mode | Runs |
|------|------|
| `backend` | Steps 1, 2 (backend half), 5 (test baseline), 6, 7 |
| `frontend` | Steps 1, 3, 5 (test baseline) |
| `full` | All steps (1–8), including the API contract smoke test |
| `auto` | Resolves to one of the above from plan scope |

---

## Step 1 — Git health (per in-scope repo) — HIGH

Delegate the deterministic parts to the script; it is the load-bearing WSL safety layer.

```bash
CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT" bash "$PLUGIN_ROOT/scripts/init-check.sh" <repo-dir>
```

The script performs, in order:

1. **Stale index-lock detection + the ONE safe auto-fix.** `test -f .git/index.lock` → `rm -f .git/index.lock`. This removes the *lock*, never the index. Load-bearing on WSL2/9p where a crashed process leaves a stale lock that blocks every later git op.
2. **Git corruption detection.** Runs `git status --porcelain`. Non-zero exit (signatures: `bad object`, `unable to read/write index`, `index file smaller than expected`) → `BLOCKED`. Report the error verbatim and instruct: fix from a **non-WSL (Windows) terminal** — never `rm .git/index`, `git reset`, or `git checkout .` from inside WSL with uncommitted work.
3. **Uncommitted-change probe.** `git diff --stat HEAD`. Dirty tree → `WARN` (commit recommended, never a blocker; never stash, never auto-reset).
4. **WSL git-config verify + auto-apply.** Reads the four keys from `meta_dev.filesystem.git_corruption_mitigations` config (`core_filemode`, `core_preloadindex`, `core_untrackedcache`, `core_fsmonitor`) and applies any that drift via `git config`. Always safe.

Exit code maps to status: `0=OK`, `1=WARN`, `2=BLOCKED`.

---

## Step 2 — Service & runtime probes (backend) — MED

For each in-scope repo, run the probes named in `meta_dev.init_check.services`. Each probe has a `command`, a `pass` criterion, and `required: true|false`. **Graceful degradation:** a failing `required:false` probe → `WARN`, not `BLOCKED`.

Resolve commands via the fallback chain — example shapes (discover real ones from config / host CLAUDE.md):

- **Interpreter/venv present** — `test -d <venv>` (venv path from config, default `.venv`). Missing → report `DEPS_MISSING`; do NOT auto-create.
- **App imports** — run the project's import smoke (e.g. a Flask `create_app` / FastAPI `app` import). Import error → `BLOCKED`.
- **Database** — open a connection with the framework's engine (e.g. `db.engine.connect()`). Failure → `BLOCKED` if `required`, else `WARN`.
- **Cache / broker** — a ping probe (e.g. `redis-cli ping`, or the configured probe). Down + `required:false` → `WARN`.
- **Task queue (e.g. Celery/RQ)** — import the worker module. **Broker-degradation heuristic:** if the queue is up but its broker (e.g. Redis) is DOWN, grep the codebase for broker-dependent paths lacking a try/except fallback; if found, raise `WARN` ("app will crash if broker unavailable").

Guardrail: **never start a service.** If a required service is down, report it and let the user start it.

---

## Step 3 — Frontend toolchain probes — MED

Only for `frontend`/`full`. Tool names come from config / host CLAUDE.md; example shapes:

- **Deps installed** — `test -d <frontend>/node_modules` (or the project's package dir). Missing → report, do NOT install.
- **Type/compile check** — the project's typecheck command run at `error` threshold only (e.g. `svelte-check --threshold error`, `tsc --noEmit`). Non-zero → `WARN` with the tail of output.
- **Native toolchain** (if the project ships one) — version probes only: `rustc --version`, `cargo --version`, `<bundler> --version`. Missing → `WARN`.

Keep all of these to version/collect probes; do not build.

---

## Step 4 — `.env` presence (per in-scope repo) — MED

`test -f <repo>/.env` → `ENV_OK` / `ENV_MISSING`. Missing → `WARN` (the run may still proceed if defaults exist). Never print env contents.

---

## Step 5 — Test-baseline collection — MED

A fast "tests are discoverable" gate, NOT a test run. Use the project's collect-only invocation:

- Python: `<venv>/python -m pytest <tests> --collect-only -q | tail -3`
- Node: the project's `--listTests`/`--dry-run` equivalent.

Report N collected. Collection error (import failure during discovery) → `WARN`. A genuine collection crash that proves the test tree is broken → `BLOCKED`.

---

## Step 6 — API contract smoke test (full-stack) — HIGH (MOST IMPORTANT)

**Why it leads in priority:** parallel agents building frontend and backend separately produce contract mismatches that pass every unit test yet 404 at runtime. *A runtime 404 is worse than a missing dependency.* Run whenever the plan touches both frontend and backend, or scope is `full`.

1. **Extract frontend API URLs** — grep the frontend source for HTTP-call sites (`fetch`, the project's API client, IPC `invoke`, etc.) and pull out `/api/...`-style string literals. De-duplicate.
2. **Extract backend route handlers** — grep backend source for route declarations (framework decorators such as `@app.<verb>`, `@router.<verb>`, `@bp.route`, etc.) and pull out the path strings. De-duplicate.
3. **Cross-reference** — for each frontend URL, confirm a matching backend route exists (account for path params / prefixes). Any frontend URL with **no** backend match → list it.

**If any unmatched URL exists → `BLOCKED`.** Do not proceed with execution until resolved.

(Grep patterns are project-shaped; derive call-site and route conventions from host CLAUDE.md / the codebase. Do not hardcode a framework.)

---

## Step 7 — FAILURES.md detection — MED

If a plan is being executed, check its directory for `FAILURES.md`:

```bash
test -f "$(dirname <plan-path>)/FAILURES.md"
```

Present → read it and announce: **"N documented failed approaches will be avoided during execution."** Status `INFO`. Absent → no-op.

---

## Step 8 — meta-runbook staleness — LOW

Read the `## Sequence` section of `<plans_root>/meta-runbook.md`. If the plan about to run is NOT listed there (and is not freshly created this session), flag `WARN` ("plan not in meta-runbook `## Sequence` — runbook may be stale"). Informational only.

---

## Report schema

Emit one table. One row per check actually run for the scope.

```
## /meta-init-check — Environment Health

| Check          | Status | Details                                  |
|----------------|--------|------------------------------------------|
| Git health     | OK     | clean tree, no lock                      |
| Git config     | OK     | WSL mitigations in place                 |
| Backend import | OK     | app imports                              |
| Database       | OK     | connection succeeded                     |
| Redis          | WARN   | down — degradation path present          |
| Frontend deps  | OK     | deps present                             |
| Typecheck      | OK     | 0 errors                                 |
| Test baseline  | OK     | N tests collected                        |
| API contracts  | OK     | N frontend calls, all matched            |
| .env           | OK     | present                                  |
| FAILURES.md    | INFO   | 3 documented dead ends                   |
| meta-runbook   | OK     | plan listed in Sequence                  |

Overall: READY (W warnings)
```

**Status meanings**

- `OK` / **READY** — all checks pass, safe to proceed.
- `WARN` / **WARNING** — non-blocking; proceed with caution.
- `BLOCKED` — critical; **do NOT proceed** until fixed.

**Stop-on-BLOCKED:** if any row is `BLOCKED`, list the exact fixes and stop. Do not start execution against a broken environment. If `READY`/`WARNING`, announce readiness and return (standalone) or hand back to the caller (when invoked from `/meta-dev` Stage 5).

---

## Guardrails (non-negotiable)

1. **Never start services** — this command checks; starting is the user's job.
2. **Never install dependencies** — missing venv/node_modules is reported, not fixed.
3. **The ONLY auto-fixes** are stale `.git/index.lock` removal and applying the configured WSL git-config keys. Both are always safe.
4. **Uncommitted changes are warnings, not blockers.** Never stash, never `git reset`, never `git checkout .`.
5. **Report, don't diagnose.** On failure, surface the exact error output and stop; do not chase root causes.
6. **Under 30 seconds total.** Honor per-check timeouts from config; skip anything that would block.
7. **No platform assumptions in prose** — WSL specifics are config-driven, not hardcoded.
