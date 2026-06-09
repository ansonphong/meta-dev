# Execute Dispatch Template

The subagent prompt template used by `/meta-execute` for each task. This is the full text sent to each fresh Sonnet subagent.

## Dispatch prompt

```
You are executing ONE task from a master plan. Plan path: <PLAN_PATH>
Your task: <TASK_ID> — <TASK_TITLE>
Read the plan section for this task in full. Read .claude/context/<relevant>.md before touching code.

Hard rules (from host CLAUDE.md + plan, all binding):
1. Work on master. No worktrees, no branches, no stashing.
2. TDD: write failing test -> run -> impl -> run -> commit.
3. Auto-commit + push at every closure. No Co-Authored-By trailer. No Claude attribution.
4. Run the task's declared Verify: command. Paste output. Green = done, red = STOP.
5. Stub grep on touched files before declaring done: grep for TODO, FIXME, pass, return [], return {}, NotImplementedError, "coming soon", "Phase N", placeholder.
6. Never silently catch IntegrityError outside the documented savepoint path.
7. Touch only files this task declares. If you need a file outside scope, STOP and report.
8. If you find the plan contradicts code reality (file moved, sig differs, dep removed): STOP and report. Do not improvise.
9. <risk-tag-specific clauses inserted here per task>

Steps:
1. Read the task. List files you'll touch. Confirm they exist + match plan claims.
2. Write failing test (or extend existing). Run it. Paste failure output.
3. Implement.
4. Run task's Verify command exactly: <VERIFY_CMD>. Paste output.
5. Run stub grep on touched files. Paste output. Must be empty.
6. git add <files> && git commit -m "<conventional commit>" && git push origin master. Paste commit SHA.
7. Report: SHA, files changed, verify output tail, anything surprising.

Do NOT: modify the plan checkbox (orchestrator owns that), touch files outside scope, run /deploy, archive plans.
```

## Risk-tag clauses

Inserted into hard rule #9 per the risk tag detected:

- **schema-drift:** "After implementation, run `alembic check`. If migration task, also round-trip: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`."
- **security-boundary:** "Confirm new code paths are gated by existing auth/permission helpers. Grep for auth decorators on any new endpoint."
- **release-stability:** "Grep diff for signing-key/credential material changes, version-string format breaks, or release-manifest schema changes. Flag any."
- **money-path:** "Confirm no silent value transfer, no rounding-down, no fee added without user-visible label. Full diff will be reviewed by orchestrator."
- **perf/cache:** "Note this touches cache/async paths. Verify no cache-key collisions or race conditions."

## Post-task verification gates (run by orchestrator, not subagent)

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
