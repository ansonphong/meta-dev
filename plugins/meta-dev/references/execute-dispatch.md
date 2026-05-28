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
- **release-stability:** "Grep diff for ed25519 key material changes, version string format breaks, or release.json schema changes. Flag any."
- **money-path:** "Confirm no silent value transfer, no rounding-down, no fee added without user-visible label. Full diff will be reviewed by orchestrator."
- **perf/cache:** "Note this touches cache/async paths. Verify no cache-key collisions or race conditions."

## Post-task verification gates (run by orchestrator, not subagent)

1. `git show --stat <sha>` — diff scope matches declared files?
2. Re-run verify command (don't trust subagent paste)
3. Re-run stub grep on diff: `git diff HEAD~1 -- <files> | grep -E '^\+.*(TODO|FIXME|coming soon|Phase [0-9]|placeholder|pass$|return \[\]|return \{\}|NotImplementedError)'`
4. Risk-tag-specific gates (schema round-trip, security diff review, release signature check, money-path full review)
