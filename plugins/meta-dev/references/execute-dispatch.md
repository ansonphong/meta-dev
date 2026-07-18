# Execute Dispatch Template

The subagent prompt template used by `/meta-execute` for each task. This is the full text sent to each fresh Sonnet subagent.

## Dispatch prompt

```
You are executing ONE task from a master plan. Plan path: <PLAN_PATH>
Your task: <TASK_ID> — <TASK_TITLE>
Read the plan section for this task in full. Read .claude/context/<relevant>.md before touching code.

Hard rules (from host CLAUDE.md + plan, all binding):
1. Work on master. No worktrees, no branches, no stashing.
2. <TEST_DIRECTIVE>   ← orchestrator inserts ONE of the two variants below per the task's `test:` tag.
3. Auto-commit + push at every closure. No Co-Authored-By trailer. No Claude attribution.
4. Run the task's declared Verify: command. Paste output. Green = done, red = STOP.
5. Stub grep on touched files before declaring done: grep for TODO, FIXME, pass, return [], return {}, NotImplementedError, "coming soon", "Phase N", placeholder.
6. Never silently catch IntegrityError outside the documented savepoint path.
7. Touch only files this task declares. If you need a file outside scope, STOP and report.
8. If you find the plan contradicts code reality (file moved, sig differs, dep removed): STOP and report. Do not improvise.
9. <risk-tag-specific clauses inserted here per task>

Steps:
1. Read the task. List files you'll touch. Confirm they exist + match plan claims.
2. <TEST_STEP>   ← orchestrator inserts the matching variant (test-first, or "no test — skip to impl").
3. Implement.
4. Run task's Verify command exactly: <VERIFY_CMD>. Paste output.
5. Run stub grep on touched files. Paste output. Must be empty.
6. git add <ONLY the explicit files from step 1> && git commit -m "<conventional commit>" && git push origin master. Paste commit SHA. NEVER `git add -A`/`.`/`<dir>` — the tree is SHARED across concurrent sessions and a broad add sweeps another session's in-flight edits (the guard hook now blocks it).
7. Report: SHA, files changed, verify output tail, anything surprising.

Do NOT: modify the plan checkbox (orchestrator owns that), touch files outside scope, run /deploy, archive plans. Do NOT write a test the task did not ask for — if `<TEST_DIRECTIVE>` says no test, adding one is scope creep.

TEST DISCIPLINE (hard rule — every cycle must be CHEAP):
- PATH-SCOPE your test, ALWAYS. Run ONLY the named file for THIS task: `pytest path/to/test_thisfeature.py -q` (or `…::test_name`). NEVER run bare `pytest`, `pytest <dir>/`, or `pytest … -k <expr>` — they collect all ~hundreds of test files (~30s tax) every cycle; the named path is ~1.7s (~18× faster). `-k`/`-x` only ON TOP of a named file, never alone.
- FAST-ONLY: pass `-m "not slow and not gpu and not integration"` if the suite uses markers. Do NOT run GPU/model/integration tests in your cycle.
- FORBIDDEN in your cycle: the full suite, `svelte-check`, `tsc --noEmit`, `npm run build`, or any whole-tree command. The orchestrator runs those ONCE at phase end — not your job.
- Run your one test ONCE to confirm green. Do NOT re-run a passing test "to be sure". One green is green.
```

## Test directive — fill `<TEST_DIRECTIVE>` / `<TEST_STEP>` per task

`/meta-execute` chooses the variant from the task's `test:` tag (set by `/meta-planner`), falling back to `meta_dev.execute.test_policy` config (default `critical-only`) when a task carries no tag:

- **`test: yes`** (critical-breakage task, or `test_policy: tdd-all`) →
  - Hard rule #2: `TDD: write failing test -> run -> impl -> run -> commit.`
  - Step 2: `Write failing test (or extend existing). Run it. Paste failure output.`
- **`test: no`** (default for ordinary tasks under `critical-only`, and all tasks under `none`) →
  - Hard rule #2: `No new test for this task — verify by the declared Verify command (build / grep / run / by-eye). Do not author a test.`
  - Step 2: `No test step — go straight to implementation. (Verify via step 4.)`

**What counts as `test: yes` (critical-breakage):** data corruption paths, auth/crypto verification, payment/value transfer, DB migration, serialization round-trip, cross-service API contract — refined by the host `CLAUDE.md` testing policy if it names specific critical surfaces. Everything else is `test: no`. When in doubt, prefer `test: no` and lean on the Verify command — fewer tests is the intended posture.

## Risk-tag clauses

Inserted into hard rule #9 per the risk tag detected:

- **schema-drift:** "After implementation, run `alembic check`. If migration task, also round-trip: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`."
- **security-boundary:** "Confirm new code paths are gated by existing auth/permission helpers. Grep for auth decorators on any new endpoint."
- **release-stability:** "Grep diff for signing-key/credential material changes, version-string format breaks, or release-manifest schema changes. Flag any."
- **money-path:** "Confirm no silent value transfer, no rounding-down, no fee added without user-visible label. Full diff will be reviewed by orchestrator."
- **perf/cache:** "Note this touches cache/async paths. Verify no cache-key collisions or race conditions."

## Post-task verification gates (run by orchestrator, not subagent)

**⛔ FIRST — flip the plan checkbox via `planctl check` (BEFORE any other post-task action):**
Once a task's verify returns green, the orchestrator (conductor) MUST immediately run
`bash ${CLAUDE_PLUGIN_ROOT}/scripts/task-done.sh <plan> <handle-from-runtime-entry>`
(shim over `planctl check` — atomic MD edit + index upsert + event append inside the unified state layer)
then commit the flipped plan: `chore(plan): mark <handle> DONE`. This is step zero — do it before the inline checks below, before advancing, before anything else. Never hand-Edit `[ ]`→`[x]`. Worker never edits checkboxes. The checkbox is the user's visibility; unchecked = "nothing happened."

**Instant inline (gate the commit — milliseconds):**
1. `git show --stat <sha>` — diff scope matches declared files?
2. Re-run stub grep on diff: `git diff HEAD~1 -- <files> | grep -E '^\+.*(TODO|FIXME|coming soon|Phase [0-9]|placeholder|pass$|return \[\]|return \{\}|NotImplementedError)'`

**Async after commit (do NOT block — advance to next task while these run):**
3. Re-run the verify/test command (don't trust subagent paste) via `Bash run_in_background`; track as `🧪 testing <ID> (async)`. Reap the result later.
4. Risk-tag-specific gates (schema round-trip, security diff review, release signature check, money-path full review).

**Exception — critical gate runs synchronously:** when the task is risk-tagged `money-path`, `release-stability`, or `schema-drift`, run steps 3–4 inline and require green BEFORE advancing. Everything else verifies async (see `references/execute-charter.md` → Verify Posture).

A red async verify or stub-grep hit is, by default, a RECOVERABLE regression → spawn the background fixer below and keep moving (see `references/execute-charter.md` → Momentum gate). Under `--strict`, all gates run inline; re-dispatch once then STOP on 2nd red.

## Background fixer prompt (optimistic mode)

Dispatched in the background (`Agent`, `subagent_type: general-purpose`, `model: sonnet`, `run_in_background: true`) when a task hits a recoverable regression, so the main loop keeps advancing independent tasks.

```
You are a REGRESSION FIXER. A task in a running plan failed its verify. Plan path: <PLAN_PATH>
Failed task: <TASK_ID> — <TASK_TITLE>
Verify command that went red: <VERIFY_CMD>
Failure output:
<PASTE RED OUTPUT>

Hard rules (binding):
- Work on master. No worktrees, no branches, no stashing.
- Touch ONLY the files <TASK_ID> declares: <FILE LIST>. If the fix needs a file outside that set, STOP and report — do NOT widen scope (a wider fix can collide with tasks the main loop is running in parallel).
- Diagnose root cause, repair/extend the failing test, implement the smallest correct fix, re-run <VERIFY_CMD> until green.
- Stub grep your diff before declaring done. No Co-Authored-By / Claude attribution.
- git add <files> && git commit -m "fix(<scope>): repair <TASK_ID> regression" && git push origin master. If push rejects (behind), `git pull --rebase origin master` then push.
- Report: SHA, green verify output tail, root cause in one line. If you cannot get green, report BLOCKED with the reason — do not fake a pass.
```

On fixer return: green → re-verify, flip task `completed`, re-open tasks deferred on it. BLOCKED/red first return → re-dispatch once. Red twice → escalate to TRUE BLOCKER, surface. Concurrent fixer pool cap: 3 (queue beyond).

## Mandatory post-run code review (orchestrator, completion step)

**ALWAYS run** once all tasks are DONE and the foundation is solid (every fixer green, no deferred tasks left, acceptance suite green). This is NON-NEGOTIABLE — every `/meta-execute` run ends with an independent code review. No skip conditions.

1. Collect the full run diff: `git log --oneline <start-sha>..HEAD` then `git diff <start-sha>..HEAD`.
2. **Invoke `superpowers:requesting-code-review`** over the full run diff. This is the project's code review skill — use it, not the meta-dev internal reviewer.
3. Route findings per the review's verdict:
   - **Trivial/mechanical** (lint, format, missing annotation) → fix inline, commit, push.
   - **Substantive** (logic error, security, contract breach, scope creep) → surface to user with file:line in the Follow-ups section of the report card. Do NOT silently auto-fix.
4. Record the verdict in the report card's Code Review section: `✅ CLEAN — 0 findings`, `⚠️ <N> findings fixed · 0 remaining`, or `❌ <N> findings surfaced — see Follow-ups`.
5. **Never skip.** Even if per-task review covered individual files, the full-diff review catches cross-task interactions, ordering effects, and integration gaps that per-task review misses.
