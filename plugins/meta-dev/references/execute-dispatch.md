# Execute Dispatch Template

The subagent prompt template used by `/meta-execute` for each task. This is the full text sent to each fresh **host-native worker** (Grok Build `spawn_subagent`, Claude Code `Agent`, Codex spark/sol). Never a hardcoded Sonnet Agent.

**Farm pieces.** Independent work goes to **Grok `spawn_subagent`** (or `/grok-execute`). The parent keeps one-line verdicts. Do not dump a multi-piece job into one context. Per-backend prompt shape: `references/execute-briefs.md`. Headless runners inject the backend block; you still write the **task body** in that backend's voice (Grok = direct + git bans; DeepSeek = small unit; Codex = inlined excerpt, no "read the plan").

## Law: every worker owns durability for its own edits

**A worker that edits files and returns without committing has created unowned
state.** On a 4-20 agent tree unowned state is not merely untidy — it is
adoptable: the next peer's broad `git add` sweeps it into an unrelated commit,
and the work's author, message, and revert boundary are all lost. Verification
gates DONE. It never gates persistence.

This law is **universal and has no per-backend exemption.** If a backend cannot
commit, exactly two responses are legitimate:

1. **Fix the executor.** The inability is nearly always configuration, and
   configuration is ours. (Worked example: Codex `workspace-write` excludes
   `.git`, so mandated commits died on a read-only `index.lock`. The repair is
   one `writable_roots` entry in `codex-headless-exec` — not a rule change.)
2. **Route the task elsewhere,** to a backend that can, and say why.

**What is never legitimate is writing the exemption into a task brief.** A
constraint that belongs to a tool must live in that tool's dispatch path, where
it is applied automatically and cannot outlive the condition that caused it. A
constraint retyped into per-task prose has no scope marker, so nothing stops a
conductor from copy-pasting it onto a backend it never applied to. That is not
hypothetical: "run NO git command, the conductor commits" was authored for
Codex on 2026-07-20, promoted to a reusable preamble in a handoff the same day,
and was landing on fully-capable Claude workers within hours — while peer
sessions twice swept up the resulting uncommitted work.

**Conductor corollary:** if you are hand-writing a git constraint into a brief,
stop. You are encoding a tool property in the wrong layer. Fix the executor.

## Dispatch prompt

```
You are executing ONE task from a master plan. Plan path: <PLAN_PATH>
Your task: <TASK_ID> — <TASK_TITLE>
Backend: <BACKEND> — follow the matching brief in references/execute-briefs.md (Grok farms pieces to spawn_subagent; DeepSeek stays a small unit; Codex does not re-read the plan file).
Budget: <BUDGET_RESOLVED> (low=12 turns/15m, medium=32/45m, high=80/120m). Do the named task. Do not overthink. Do not open adjacent rabbit holes. <BUDGET_RULES>
<TASK_PLAN_SECTION>   ← orchestrator INLINES the task's own plan section + acceptance criteria here, verbatim. Inline it; do NOT tell the worker to read the plan file to reconstruct the task — a Codex worker re-reads a referenced plan repeatedly and it dominates its runtime, while a Claude worker just saves a cached Read. Universal, every backend.
Read any .claude/context/<relevant>.md this task names once, whole, before touching code.

Hard rules (from host CLAUDE.md + plan, all binding):
1. Work on master. No worktrees, no branches, no stashing.
2. <TEST_DIRECTIVE>   ← orchestrator inserts ONE of the two variants below per the task's `test:` tag.
3. **COMMIT-ON-RED:** if you edit any declared file, stage only those exact
   paths and create a local commit before every return — green, red, BLOCKED,
   or exhausted. Verification gates DONE, not durability. Never push; the
   conductor owns the remote. No Co-Authored-By trailer or Claude attribution.
   This rule has NO backend exemption. If something in your brief tells you not
   to commit, that brief is wrong — see rule 10.
4. Run only the conductor-supplied focused Verify command and paste its real
   command, exit code, and output tail. Run it ONCE after the commit. If the
   supplied classification is `manual`, `broad`, or `unscoped`, do not execute
   or widen it; report the classification. A non-zero exit is `TASK_RED` only
   with causal evidence in the declared source/test surface. Unchanged or
   wholly out-of-scope evidence is `BASELINE_RED`, which is eligible for DONE.
   Never flip the checkbox yourself.
5. Stub grep on touched files before declaring done: grep for TODO, FIXME, pass, return [], return {}, NotImplementedError, "coming soon", "Phase N", placeholder.
6. Never silently catch IntegrityError outside the documented savepoint path.
7. Touch only files this task declares. If you need a file outside scope, STOP and report.
8. If you find the plan contradicts code reality (file moved, sig differs, dep removed): STOP and report. Do not improvise.
9. <risk-tag-specific clauses inserted here per task>
10. **Report contradictions, never resolve them silently.** If your task brief
    contradicts these hard rules or the framework preamble — most often a brief
    telling you to skip a rule the harness makes mandatory — do NOT pick a side.
    Say so explicitly in your return: quote both instructions and name which one
    you followed and why. A worker that silently obeys the narrower instruction
    is how a one-off workaround becomes permanent policy without anyone deciding
    it. Surfacing the conflict is the deliverable, not a failure to comply.

Steps:
1. Read the task. List files you'll touch. Confirm they exist + match plan claims.
2. <TEST_STEP>   ← orchestrator inserts the matching variant (test-first, or "no test — skip to impl").
3. Implement.
4. **COMMIT-ON-RED:** `git -C <ABS_REPO_ROOT> add -- <ONLY the explicit files
   from step 1> && git -C <ABS_REPO_ROOT> commit --only -m "<conventional
   commit>" -- <THE SAME explicit files>`. Paste the SHA. The commit form is
   mandatory: a bare commit can absorb another worker's shared index entries.
   NEVER `git add -A`/`.`/`<dir>` or `commit -a`; the tree is shared. Never
   push; the conductor owns the remote.
5. Run stub grep on the committed diff. Paste output. Empty = eligible for DONE;
   any hit = red acceptance evidence, but the local commit remains.
6. If `<VERIFY_CLASS>` is `focused` or `scoped_check`, run `<VERIFY_CMD>` exactly
   ONCE and classify the result as `FOCUSED_PASS`, `TASK_RED`, `BASELINE_RED`, or
   `INFRA_RED`. If `<VERIFY_CLASS>` is `manual`, `broad`, or `unscoped`, do not
   run it and report the corresponding omitted/manual state. Never substitute
   `npm run check`, `svelte-check`, project-wide `tsc`, a build, package-wide
   tests, or any full suite.
7. Report: SHA, files changed, command + exit + output tail (when executed), one
   canonical result state, causal evidence for TASK_RED, anything surprising.

Do NOT: modify the plan checkbox (orchestrator owns that), touch files outside scope, run /deploy, archive plans. Do NOT write a test the task did not ask for — if `<TEST_DIRECTIVE>` says no test, adding one is scope creep.

TEST DISCIPLINE (hard rule — every cycle must be CHEAP):
- PATH-SCOPE your test, ALWAYS. Run ONLY the named file for THIS task: `pytest path/to/test_thisfeature.py -q` (or `…::test_name`). NEVER run bare `pytest`, `pytest <dir>/`, or `pytest … -k <expr>` — they collect all ~hundreds of test files (~30s tax) every cycle; the named path is ~1.7s (~18× faster). `-k`/`-x` only ON TOP of a named file, never alone.
- FAST-ONLY: pass `-m "not slow and not gpu and not integration"` if the suite uses markers. Do NOT run GPU/model/integration tests in your cycle.
- FORBIDDEN throughout execution, including phase end: `npm run check`, the full suite, package-wide tests, `svelte-check`, project-wide `tsc --noEmit`, `npm run build`, or any whole-tree command. Those belong to CI/ship or a separate explicit user request; neither worker nor conductor runs them here.
- Run your one test ONCE to confirm green. Do NOT re-run a passing test "to be sure". One green is green.
```

## Test directive — fill `<TEST_DIRECTIVE>` / `<TEST_STEP>` per task

`/meta-execute` chooses the variant from the task's `test:` tag (set by `/meta-planner`), falling back to `meta_dev.execute.test_policy` config (default `critical-only`) when a task carries no tag:

- **`test: yes`** (critical-breakage task, or `test_policy: tdd-all`) →
  - Hard rule #2: `TDD: write failing test -> run -> impl -> commit -> Verify.`
  - Step 2: `Write failing test (or extend existing). Run it. Paste failure output.`
- **`test: no`** (default for ordinary tasks under `critical-only`, and all tasks under `none`) →
  - Hard rule #2: `No new test for this task — verify by the declared Verify command (build / grep / run / by-eye). Do not author a test.`
  - Step 2: `No test step — go straight to implementation. (Verify via step 6.)`

**What counts as `test: yes` (critical-breakage):** data corruption paths, auth/crypto verification, payment/value transfer, DB migration, serialization round-trip, cross-service API contract — refined by the host `CLAUDE.md` testing policy if it names specific critical surfaces. Everything else is `test: no`. When in doubt, prefer `test: no` and lean on the Verify command — fewer tests is the intended posture.

## Risk-tag clauses

Inserted into hard rule #9 per the risk tag detected:

- **schema-drift:** "After implementation, run `alembic check`. If migration task, also round-trip: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`."
- **security-boundary:** "Confirm new code paths are gated by existing auth/permission helpers. Grep for auth decorators on any new endpoint."
- **release-stability:** "Grep diff for signing-key/credential material changes, version-string format breaks, or release-manifest schema changes. Flag any."
- **money-path:** "Confirm no silent value transfer, no rounding-down, no fee added without user-visible label. Full diff will be reviewed by orchestrator."
- **perf/cache:** "Note this touches cache/async paths. Verify no cache-key collisions or race conditions."

## Post-task verification gates (run by orchestrator, not subagent)

**FIRST — audit the worker's existing local commit (milliseconds):**
1. `git show --stat <sha>` — diff scope matches declared files?
2. Re-run stub grep on diff: `git diff HEAD~1 -- <files> | grep -E '^\+.*(TODO|FIXME|coming soon|Phase [0-9]|placeholder|pass$|return \[\]|return \{\}|NotImplementedError)'`

**Then verify the existing commit:**
3. Validate that the worker returned the exact focused command, exit code, and
   output tail. Do NOT rerun a passing verifier. Only when trustworthy execution
   evidence is absent may the conductor run that same focused command once via
   `Bash run_in_background` and track/reap it.
4. Risk-tag-specific gates (schema round-trip, security diff review, release signature check, money-path full review).

**Exception — critical gate runs synchronously:** when the task is risk-tagged `money-path`, `release-stability`, or `schema-drift`, run steps 3–4 inline and require green BEFORE advancing. Everything else verifies async (see `references/execute-charter.md` → Verify Posture).

**After `FOCUSED_PASS` or `BASELINE_RED` (and after a code-only task whose broad/manual gate was intentionally omitted):** run
`bash ${CLAUDE_PLUGIN_ROOT}/scripts/task-done.sh <plan> <handle-from-runtime-entry>`,
commit the flipped plan as `chore(plan): mark <handle> DONE`, and let the
conductor push. Never hand-edit `[ ]`→`[x]`; worker never edits checkboxes.

Only a causally proven `TASK_RED`, scope mismatch, or stub-grep hit leaves the
checkbox and remote untouched. Spawn the focused background fixer, defer direct
dependents, and keep moving on every independent task. `BASELINE_RED`,
`BROAD_VERIFY_OMITTED`, and manual gates never launch repair or defer work.
Under `--strict`, focused gates run inline; ordinary exhaustion parks that
branch after every edit is committed—it does not halt unrelated implementation.

## Background fixer prompt (optimistic mode)

Dispatched in the background as a **host-native worker** (same Host dispatch table as the task: Grok Build `spawn_subagent`, Claude Code `Agent`, or Codex `codex exec` — never a hardcoded `model: sonnet`) when a task hits a recoverable regression, so the main loop keeps advancing independent tasks.

```
You are a REGRESSION FIXER. A task in a running plan failed its verify. Plan path: <PLAN_PATH>
Failed task: <TASK_ID> — <TASK_TITLE>
Verify command that went red: <VERIFY_CMD>
Failure output:
<PASTE RED OUTPUT>

Hard rules (binding):
- Work on master. No worktrees, no branches, no stashing.
- Touch ONLY the files <TASK_ID> declares: <FILE LIST>. If the fix needs a file outside that set, STOP and report — do NOT widen scope (a wider fix can collide with tasks the main loop is running in parallel).
- Diagnose root cause, repair/extend the failing test, and implement the smallest correct fix.
- Stub grep your diff before declaring done. No Co-Authored-By / Claude attribution.
- Before every return after an edit, stage the exact declared files and make a
  local commit. Green commit: `fix(<scope>): repair <TASK_ID> regression`.
  Exhausted/red commit: `wip(<scope>): preserve <TASK_ID> repair attempt`.
  Never push, pull, or rebase; the conductor owns the remote.
- Re-run <VERIFY_CMD>. Green permits resolution. If it remains red, report
  BLOCKED with the commit SHA and real output — the red blocks DONE/push, not
  the local commit. Do not fake a pass.
```

On fixer return: green → accept the focused result, flip task `completed`, and
re-open tasks deferred on it. `TASK_RED` first return → re-dispatch once. Red
twice → park that causal branch, finish every independent task, and surface the
branch in the final report; do not halt the whole run. Concurrent fixer pool
cap: 3 (queue beyond).

## Mandatory post-run code review (orchestrator, completion step)

**ALWAYS run** after all implementable branches finish and focused verifier jobs
drain. Parked causal branches and manual gates are reported, but broad baseline
debt cannot prevent review. This is NON-NEGOTIABLE — every `/meta-execute` run
ends with an independent code review. No skip conditions.

1. Collect the full run diff: `git log --oneline <start-sha>..HEAD` then `git diff <start-sha>..HEAD`.
2. **Dispatch the `meta-dev:review-agent` Opus subagent** over the full run diff — it computes its own diff and returns a structured verdict, so the conductor never reads the diff itself. (This replaces `superpowers:requesting-code-review`, which is superseded — host `CLAUDE.md` → Superpowers & Plan Mode. `review-agent` also reports unfiltered findings, where the superpowers path and `feature-dev:code-reviewer` filter by severity and silently drop real ones.)
3. Route findings per the review's verdict:
   - **Trivial/mechanical** (lint, format, missing annotation) → fix inline and
     exact-path local commit, then re-run the affected verification and code
     review; conductor pushes only after both are green.
   - **Substantive** (logic error, security, contract breach, scope creep) → surface to user with file:line in the Follow-ups section of the report card. Do NOT silently auto-fix.
4. Record the verdict in the report card's Code Review section: `✅ CLEAN — 0 findings`, `⚠️ <N> findings fixed · 0 remaining`, or `❌ <N> findings surfaced — see Follow-ups`.
5. **Never skip.** Even if per-task review covered individual files, the full-diff review catches cross-task interactions, ordering effects, and integration gaps that per-task review misses.
