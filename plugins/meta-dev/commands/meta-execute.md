---
name: meta-execute
description: Subagent-driven plan execution — optimistic momentum (fix regressions async, keep moving), mandatory post-run code review, verify+commit+push between, auto-archive on completion (never deploys)
argument-hint: <plan-path> [--inline] [--strict] [--review each|phase|end|auto] [--budget auto|low|medium|high] [--deep] [--grok] [--codex] [--sonnet] [--glm] [--effort <level>] [--deploy] [--pause-before=<task-id>]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---

# /meta-execute

## Dashboard stage signal (waterfall — MANDATORY)

This command owns the **EXECUTE** waterfall stage (5/6). Keep `/meta-dashboard` in sync — fire-and-forget, never let a dashboard emit block execution:
- **Before the first task dispatches:** `bash ${CLAUDE_PLUGIN_ROOT}/scripts/stage-emit.sh "<plan-path>" execute in_progress`
- **After the run completes (post code-review, before archive):** `bash ${CLAUDE_PLUGIN_ROOT}/scripts/stage-emit.sh "<plan-path>" execute completed` (use `blocked` if you halt mid-run)

`<plan-path>` is the plan you were invoked on. This lights up the plan at Stage 5 (and the Active Sessions STAGE column) automatically.

**Stage 5 → 6 (DONE) is enforced by the `on-run-complete.sh` Stop hook, not by you.** When execution is complete (all execution checkboxes flipped) AND a review PASS is on record (see step 6), the gate stamps `review completed` (stage 6) and re-renders the dashboard itself. You still flip checkboxes per-task and run the review — the gate is the deterministic backstop that makes silent half-completion impossible.

**The runbook dashboard self-heals on every stop — you cannot leave it stale.** The same Stop hook re-renders EVERY campaign runbook UNCONDITIONALLY at the end of each turn, so the dashboard tracks live member frontmatter no matter how a member reached its stage — the gate's own stamp, a closeout hand-flip of the plan's `stage:`, a direct `stage-emit`, or a manual YAML edit. (The historic freeze: the re-render used to live only inside the stage-5→6 stamp branch, so a member that advanced to stage 6 by any other path dropped off the stage-5 radar and its runbook froze at `⑤ EXECUTE · EXECUTING` forever.) The per-phase render at step 4's "Runbook dashboard sync" is still worth doing for LIVE mid-run progress; the Stop-hook reconcile is the end-of-turn guarantee.

## ⛔ Conductor law — this thread does not implement (non-negotiable)

You are the conductor. You do **not** implement plan tasks on this thread.

**Farm pieces to Grok subagents.** Independent checkboxes with disjoint files run in parallel. A fat task that is really three pieces becomes three Grok workers. You keep one-line returns. **Shape each brief for that backend** (`references/execute-briefs.md`) — Grok, DeepSeek, and Codex do not get the same paragraph. Headless runners inject the backend block; you still write the task body in that voice.

`--inline` is the ONLY exception, and only when the user passed it.

For each verifiable checkbox:
1. Dispatch a **fresh subagent** native to THIS host (Host dispatch below). When unsure, spawn.
2. The worker implements, runs the focused verify once, and creates an exact-path local commit before returning, including on red verification.
3. You read a **one-line result** (SHA, canonical state, surprises). You never read the diff.
4. You flip `task-done` on a releasable outcome.

Stay on this thread only for: the slash harness, vision, a true one-liner (one known file, a few tool calls), permission/stage gates, and integrating that one-line return. Missing a Grok/`Agent` mapping is **not** permission to type the plan here. `references/workflows/protocol.md` treats missing delegation as a host-table bug, not a serial-on-conductor fallback. Grok Build, Claude Code, and Codex all have a worker primitive.

**Forbidden on this thread (unless `--inline`):** Edit/Write of source files a plan task owns; implementing "to save a round-trip"; treating the conductor as the worker because the run is "small."

### Host dispatch (unflagged)

Read host `CLAUDE.md` and `references/work-ladder.md`. If the host names a pooled worker (Claude Code on this 360-Hextile tree → Grok), use that instead of a same-family Agent. Otherwise use the table. Never fall through to this thread.

| This host | Per-checkbox worker | How |
|-----------|---------------------|-----|
| **Grok Build** | `spawn_subagent` | `subagent_type: general-purpose`, inherit model, `background: true`, `capability_mode: all`. Prompt = `references/execute-dispatch.md` with the task section inlined. Put git bans + commit-on-red in every brief (Grok has no PreToolUse). Wait for the one-line return. |
| **Claude Code** | native `Agent`/Task | Same family as the session. Do not `--inline` to "stay local." |
| **Codex** | `codex exec` | **spark / low** for mechanical (separate weekly quota). **`gpt-5.6-sol` / high** for cross-module, security, migration, ambiguous root cause. Conductor stays thin. |

Grok git brief (every spawn): no rebase / stash / `add -A` / `commit -a` / bare commit. Form: `git -C <ABS> add -- <paths> && git -C <ABS> commit --only -m "…" -- <paths>`. Never push.

### `--review` cadence

Parse `--review each|phase|end|auto`. Default **`auto`**.

| Value | Behavior |
|-------|----------|
| `each` | **One task at a time.** Host-native review-agent after each task before the next dispatch. Serial on purpose. |
| `phase` | Review at each `## Phase N` (once at end if phase-less). Independent tasks may overlap inside a phase. |
| `end` | One review after solidify. Independent tasks may overlap. |
| `auto` | `phase` if the plan has ≥2 `## Phase` headings; `end` if small. Force `each` on a `money-path` / `schema-drift` / `release-stability` task even under `auto`. |

Reviewer is host-native: Claude → configured `meta-dev:review-agent`; Grok Build → `spawn_subagent` reviewer (it computes its own diff); Codex → Sol/high. The conductor never reads the diff. A run NEVER ends unreviewed.

## ⛔ Prerequisite — visible main-thread task list (non-negotiable)

**Before starting work on ANY task (whether dispatched to a subagent or run `--inline`), the main thread MUST stand up a visible task list via `TaskCreate` — one entry per CHECKBOX in the plan (every `### Task N:` heading AND every `- [ ]` subtask checkbox nested under it) — and keep it live with `TaskUpdate` for the whole run.** Granularity is the point: the user runs `/meta-execute` to *watch* progress, so a list of fine-grained, checkbox-mapped entries is a primary deliverable — a list of 4 broad items hides progress; the same plan's 14 checkboxes as 14 entries shows it. No tracker visible = the run has not started correctly. Updates are mirrored *as each state changes* — never batched at the end.

Parse plan, dispatch one **fresh host-native subagent per checkbox** (Host dispatch above). Every editing worker creates an exact-path local commit before returning, including on red verification. No external backend is spawned unless a tier flag says so. **Optimistic momentum is the default control flow:** run only focused verification, once; release dependents from committed usable artifacts; and never let an unrelated baseline, broad omitted gate, manual gate, or ordinary failure on another branch stop forward progress. A causally proven `TASK_RED` repairs the smallest affected branch while every independent task continues. Only critical-risk tasks (`money-path` / `release-stability` / `schema-drift`) verify synchronously, and even those use a focused verifier. `--strict` serializes focused verification; it never authorizes broad checks or converts unrelated debt into task failure. `--review each` serializes **dispatch** (review hop between tasks) on top of that.

### Safe parallel waves (default — non-negotiable)

**Parallelize when it is safe. Serialize when it would collide.** Do not walk the task list one-at-a-time if two ready tasks can run together.

A task is **READY** when all of these hold:
1. Plan `depends` / TaskCreate deps are releasable (`FOCUSED_PASS` or `BASELINE_RED`).
2. Its **declared file set is disjoint** from every worker (and fixer) currently in flight from this run.
3. It is not deferred on a `TASK_RED` parent.

**Dispatch:** spawn every currently-READY task as a fresh host-native subagent, up to the in-flight cap (**8** execute workers from this run, fixers count). As each worker returns, immediately fill the empty slot with the next READY task. Do not wait for the whole wave to drain before considering new ready work.

**Serialize (do not co-dispatch) when ANY of:**
- Declared file sets overlap (same path in two tasks) — queue the later one.
- `--review each` (one task at a time by design).
- `--inline` (this thread is the worker).
- `--glm` (account cap ~3 — never two GLM workers in parallel).
- Unknown / undeclared file set — treat as overlapping; do not guess.

`--strict` serializes **verify**, not disjoint dispatch. File-disjoint READY tasks may still overlap in flight under `--strict`.

The checkbox rule does **not** serialize dispatch. Flip a task the instant **it** is releasable. Independent siblings may already be in flight.

## Charter

Read `references/execute-charter.md` before dispatching. Execution posture (optimistic momentum), anti-paranoia, CLAIMED protocol, failure posture matrix, resume logic, pause gates — all there.

## Flow

### Worker tier (`--deep`/`--grok`/`--codex`/`--sonnet`/`--glm`)

When a tier flag is present, run the **agentic-exec-loop** (skill: agentic-exec-loop, references/loop-protocol.md) instead of the native executor:

- Execute each task via a fresh headless worker — `${CLAUDE_PLUGIN_ROOT}/scripts/claude-headless-exec --backend deep|glm|sonnet [--budget <level>] [--effort <level>] --repo <plan-repo> -- <task spec incl. its Verify: command>`, or `${CLAUDE_PLUGIN_ROOT}/scripts/codex-headless-exec` for `--codex` / `${CLAUDE_PLUGIN_ROOT}/scripts/grok-headless-exec` for `--grok` (neither takes `--backend`; both emit the identical `OUTPUT_FILE` contract). **`--budget`** is the depth cap (default `auto`): classify each task (`low` mechanical, `medium` ordinary, `high` hard). A concrete campaign `--budget low|medium|high` is a **ceiling** — no task may exceed it. Resolve with `scripts/classify-execute-budget.sh --campaign <level> -- "<task title>"` and forward `--budget low|medium|high` (never `auto`) to the worker. Host-native spawn: fill the Budget block in `references/execute-dispatch.md`. Doctrine: `references/execute-budget.md`. If `--effort <level>` was passed to `/meta-execute`, forward it to every `claude-headless-exec` dispatch; otherwise the script's per-backend default applies (sonnet/opus/glm/fable = `high`). **`deep` has no effort knob** — the runner warns and drops the level rather than forwarding it, so don't bother passing `--effort` with `--deep`. The worker self-verifies. **`--sonnet` runs each task on a SEPARATE `claude -p` pinned to `claude-sonnet-5` via the ambient login**, so each task's context churn stays in its own process instead of the conductor's window. (Sonnet 5 is 1M at standard rates either way — this is context economy, not a billing tier.)
- KEEP the per-task checkbox flip + per-task commit (unchanged).
- Review cadence is `--review` (default `auto` → `phase` on this path, because a tier-flag run is already a playbook). Honor an explicit `--review each|end`. Dispatch the host-native review-agent over `git diff <phase_pre_sha>..HEAD` (or per-task under `each`); branch on PASS/CONDITIONAL_PASS/FAIL per the protocol; run the fix-ladder on FAIL (next rung of `meta_dev.ladder.pool`).
- The conductor holds only the task list + per-phase verdict; it never reads diffs.
- **Context watchdog (every execute path, not only this one):** at each review seam (after the verdict, work committed) and every 8 completed tasks on a phase-less `end` run, run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context-gauge.py`; on `CONTEXT_VERDICT=OVER` (default 300000) pause and `/meta-compact` forward before advancing — per loop-protocol → "Context watchdog". Keeps long playbooks ahead of the harness's hard auto-compact.
- **Runbook dashboard sync:** at the SAME phase seam, if the executing plan is a member of a campaign runbook, re-render it so the live dashboard tracks the phase that just landed. Resolve `REPO_ROOT` to the absolute root before this step, then run: `RB=$(grep -rlF --include='_runbook-*.md' "<plan-path>" plans/); [ -n "$RB" ] && python3 ${CLAUDE_PLUGIN_ROOT}/scripts/runbook-render.py "$RB" && { git diff --cached --quiet "$RB" 2>/dev/null || { git -C <ABS_REPO_ROOT> add -- "$RB" && git -C <ABS_REPO_ROOT> commit --only -q -m "chore(runbook): refresh dashboard" -- "$RB"; }; }`. Heed its stderr `⚠ stage-drift`; on final-phase pass bump the plan's `stage:`→6. Per loop-protocol → "Runbook dashboard sync". Without this the dashboard freezes mid-run on long-horizon executions.

If you (the orchestrating session) dispatch a worker expected to idle past ~4 min, keep your prompt cache warm per loop-protocol's cache-keepalive (270s) — session practice, not command automation.

**Bare invocation (no tier flag) = host-native subagents, never this thread** — steps 1–8 below. Use the Host dispatch table. No external process is spawned unless a tier flag or the host's pooled-worker overlay says so. `--deep`/`--grok`/`--codex`/`--sonnet`/`--glm` are **explicit opt-ins** that force a specific *foreign* backend — none of them is the default, and none of them is an excuse to implement here. `--inline` is the only "this thread types the code" flag.

### 1. Resolve plan path + parse task inventory

Read the plan. Extract every **checkbox**: every `### Task N:` heading AND every `- [ ]` subtask checkbox nested under a task. Count them all — this checkbox count is the inventory the task list must match. Sub-tasks with `### Task N.M:` are separate. Phase headings are NOT tasks (they have no checkbox).

### 2. Mirror EVERY checkbox into the visible task list (MANDATORY — see Prerequisite)

Call `TaskCreate` once per **checkbox** from the step-1 inventory (every task heading AND every subtask checkbox), **descriptive, well-named** (`<ID> — what it builds/fixes`, not bare IDs). **Each entry carries a `[Backend]` tag naming the backend that task will ACTUALLY be dispatched to at step 4.3** — under bare invocation `[Grok]` / `[Claude]` / `[spark]` / `[sol]` per Host dispatch (or the host pooled-worker overlay); else `[DeepSeek]`/`[GLM]`/`[Sonnet]`/`[Codex]` matching a tier flag. Never tag `[native]` to mean "this conductor thread." The tag is a promise, not a label: if you dispatch a task to a different backend than its tag, retag it via `TaskUpdate` in the same breath. Example: `◻ 17·P2b — multipass-promote (persist effective_config.json) [native]`. **When the master is stamped**, each entry **also stores its `` `T…` `` handle** (from the checkbox line) — that handle is what the conductor passes to `task-done` after green verify. Set dependencies. **The tracker item count MUST equal the step-1 checkbox count — 1 runtime task ↔ 1 plan checkbox ↔ 1 handle, always; do not dispatch before the list is visible and complete.** Surface every state through the run via `TaskUpdate`: `in_progress` → `🔧 repairing (async)` / `deferred — waiting on <ID>` / `blocked` → `completed`, plus one entry per background fixer and a final `📋 code review` entry. **Each completed runtime task flips exactly its own matching plan checkbox via `task-done` (see ⛔ CHECKBOX RULE) — the two never drift apart.**

### 3. Pre-flight gates

- Read branch policy from host `CLAUDE.md` per `references/host-claude-contract.md`
- Working tree: if dirty files overlap plan file set → commit immediately, keep moving
- Confirm on the host's declared main branch
- `git fetch origin`, review the ahead commits, then `git merge --ff-only` if
  behind. Never rebase. Divergence is a genuine conflict and must surface.
- If `filesystem.git_corruption_mitigations` config is true → apply host-specific git mitigations
- Read `references/execute-charter.md` for full pre-flight details

### 4. Per task: claim → risk-tag → dispatch → local commit → verify → accept/repair

Walk READY work as **waves** (Safe parallel waves above), not a forced serial list. For each task you dispatch (several may be in flight):

1. Mark `in_progress` via `TaskUpdate`. CLAIM in plan file (per execute-charter.md). Commit claim.
2. Run `echo "<task body>" | bash scripts/risk-tag.sh` → get risk tags
3. Dispatch a **fresh host-native subagent** (Host dispatch table — Grok Build → `spawn_subagent`; Claude Code → `Agent`; Codex → spark or sol) with the task spec from `references/execute-dispatch.md` + risk-tag clauses. Do **not** implement the task on this thread. Under `--deep` this becomes a headless DeepSeek worker instead (`${CLAUDE_PLUGIN_ROOT}/scripts/claude-headless-exec --backend deep`), and `--glm`/`--sonnet`/`--codex`/`--grok` force their own backends per the Worker-tier section — an external backend is used **only** when its flag was passed. Default: fill every READY slot up to the cap — do not wait on in-flight fixers, in-flight tests, or an unrelated sibling. `--strict`: wait for that task's focused verify before *its* dependents; disjoint READY siblings still dispatch. `--review each`: wait for that task's review hop before the next dispatch (serial).
4. Before dispatch, classify the task's Verify command with `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify-scope.py --command "$VERIFY_CMD" --allowed-path <each-declared-source-or-test-path>`. Pass only `focused` or `scoped_check` commands to the worker. `manual`, `broad`, and `unscoped` commands are NOT run and must not be replaced with a wider command; record `BROAD_VERIFY_OMITTED`/`UNSCOPED_VERIFY_OMITTED` or the human punch-list item. A broad command written in a plan is stale plan prose, not authorization to burn the repository-wide gate.
5. The subagent returns only after any scoped edits are in an exact-path **local commit**, even if its focused Verify was red. Run **instant inline checks only** (stub grep on the committed diff + declared-file existence — milliseconds). The worker owns its focused verifier and runs it ONCE after its commit. Trust a structured result containing command, exit code, and output tail; the conductor MUST NOT rerun a passing verifier. Only if trustworthy execution evidence is absent may the conductor run that same focused command once. Non-critical focused verification may run async; critical-risk tasks verify synchronously. Never run `npm run check`, `svelte-check`, project-wide `tsc`, a build, package-wide tests, or a full suite anywhere in `/meta-execute`, including solidify.
6. **Advance immediately** according to causal state: `FOCUSED_PASS` → mark `completed`, run `task-done`, and release dependents; `BASELINE_RED` (unchanged or wholly outside declared source/test paths) → record once, mark `completed`, run `task-done`, and release dependents; `BROAD_VERIFY_OMITTED`/manual → do not run or repair, complete the code task, release code dependents, and report separately; `TASK_RED` requires causal evidence and launches a focused fixer (same Host dispatch table as the task — never a hardcoded Sonnet Agent) while only direct dependents defer; `INFRA_RED` retries infrastructure once and never blames code without causal evidence. Ordinary repair exhaustion parks that branch while every independent task continues. Whole-run STOP is reserved for guard/safety denial, a global plan↔code contradiction, genuine schema divergence, or an unusable critical contract.
7. **Review hop** when `--review each` (or `auto` forced `each` on a critical-risk task): dispatch the host-native review-agent over this task's commit before the next dispatch. PASS/CONDITIONAL_PASS → continue. FAIL → fixer on the causal findings, then re-review that task. Do not start the next task until the hop returns.
8. **Context watchdog** every 8 completed tasks and at every review seam: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context-gauge.py`. `CONTEXT_VERDICT=OVER` → `/meta-compact` forward before the next dispatch. This runs on the **bare path too**, not only `--deep/--grok/--codex`.

### ⛔ MANDATORY CHECKBOX RULE — NEVER SKIP, NEVER DEFER

**Every time a task completes (green verify), the conductor flips its checkbox via `task-done` immediately — never batch flips to the end, never defer, never hand-`Edit` the mark.** Unchecked boxes read as "nothing happened"; the checkbox is the user's primary visibility into progress and the single source of truth. This flip is per-task. It does **not** mean "wait to dispatch independent siblings." Fill READY parallel slots as soon as they are file-disjoint.

**Conductor-owned handle (Invariant 2):** when the runtime task list was built from stamped master checkboxes, **each TaskCreate entry already stores its `` `T…` `` handle**. After green Verify-After the conductor runs:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/task-done.sh <plan-path> <handle-from-the-runtime-entry>
# ^-- shim over `planctl check` (the unified state layer's single write door).
git -C <ABS_REPO_ROOT> add -- <plan-path> && git -C <ABS_REPO_ROOT> commit --only -m "chore(plan): mark <handle> DONE" -- <plan-path>
```

- **Not** "parse handles from the worker result." Worker never `Edit`s a checkbox; worker may echo the handle for audit only.
- A bold task unit `- **Task N.M**` with several sub-step boxes becomes several runtime tasks — each flips the instant its own step is green via its own handle.
- `task-done` is scope-locked (no git). The **conductor commits** the flipped plan file after a successful flip.
- Unstamped legacy plans: run `task-stamp.py` on the master first, or fall back to binding handles from the freshly stamped lines before any flip.

**Self-check before the report card (step 8):** `grep -cE '^[[:space:]]*[-*][[:space:]]+\[[[:space:]]\]' <plan-file>`. If the count is not zero for completed tasks, you missed `task-done` calls — go back and flip them NOW, before rendering the report card.

### 5. Solidify focused foundation

Drain every in-flight **focused** verifier. Finish or park causally red branches, execute any one explicitly declared path-scoped cross-task integration test, then proceed to review. Do not replay already-green task tests. Do not run a full acceptance suite, project type-check, build, or package-wide test command. Broad/manual gates are report-card evidence only and cannot undo accepted tasks, block unrelated branches, or prevent code review. A run may finish its implementable work with a parked causal branch or human gate clearly reported; it may not call that parked branch DONE.

### 6. Mandatory code review (`--review`)

A run NEVER ends unreviewed. Honor `--review` (default `auto` — see cadence table). Do **not** use `superpowers:requesting-code-review`; it is superseded (see the host `CLAUDE.md` → Superpowers & Plan Mode).

- **`each`:** already satisfied by the per-task hop in step 4.7. The last task's hop is the closing review (no extra end-of-run pass).
- **`phase`:** host-native review-agent at each `## Phase N` (once at end if phase-less). The final phase review IS the closing review.
- **`end`:** one host-native review-agent over `git diff <start>..HEAD` after solidify (it computes its own diff — the conductor never reads it).
- **Tier-flag path** defaults to `phase` unless the user passed `--review each|end`.

Reviewer is host-native (Claude → `meta-dev:review-agent`; Grok Build → `spawn_subagent` reviewer; Codex → Sol/high). Route findings:

- **Trivial/mechanical** (lint, format, missing annotation) → fix inline and
  exact-path local commit; re-run the affected verification and code review;
  push only after both are green
- **Substantive** (logic, security, contract, scope creep) → surface to user with file:line in the Follow-ups section of the report card, do NOT silently auto-fix

Record verdict in the report card. If the review returns substantive findings, fix them before proceeding to housekeeping.

**Persist the review verdict — the end-of-run DONE-gate reads it (MANDATORY).** The `on-run-complete.sh` Stop hook stamps this plan DONE (stage 6) automatically once execution is complete AND a `review_verdict(pass)` is on record; without that event the gate leaves the plan at stage 5 and flags "review missing." Once the run's review resolves to a pass (default path: no substantive findings left; tier path: the final phase PASS), emit it:

```bash
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
bash ${CLAUDE_PLUGIN_ROOT}/scripts/planctl.sh review "<plan-path>" pass --by "conductor"
```

On a substantive FAIL that halts the run, emit `\"verdict\":\"fail\"` (or omit). Either way the run NEVER silently ends half-stamped: the gate either advances it to DONE or surfaces what's outstanding to the inbox.

### 7. Housekeeping

Archive the plan (unless manual gates remain — e.g., GPU acceptance, in-app verification), commit + push both repos. The stage already propagated to the plan's YAML via the `stage-emit.sh` call above; cross-plan ordering lives in `plans/meta-runbook.md` — touch it only if execution priority changed.

### 8. Render execution report card

ALWAYS end with this structured dashboard. The report MUST include every section listed in the reference — no sprawl, no stream-of-consciousness narration.

**Layout:** `references/execute-report-card.md` (sections + content) → `references/status-cards.md` (the card chassis, glyphs, and `CARD_W`). The template is deliberately NOT repeated here: this command used to carry its own copy, which drifted to a 68-col border and a header glyph its own spec forbade. One definition, referenced.

**Rules for the report card:**
- Every section is mandatory. If a section has no content, write "(none)" — never omit.
- Commit table: one row per commit, short SHA, one-line description, verify result (e.g., "6/6 pass", "check clean", "sync-verified ✓")
- Plan location: state where the plan lives NOW. If archived, show the archive path. If still active, say WHY (e.g., "manual GPU acceptance pending", "awaiting user verification of X")
- Follow-ups: structured list. Each item = what needs doing + what action + who owns it. Include: manual gates, unarchived plans, findings surfaced from code review, deploy prompts
- No narrative. No conversational wrap-up. The report card IS the wrap-up.
- Do NOT repeat the entire plan description. The report card is a summary of execution results, not a re-cap of the design doc.

## Flags

| Flag | Effect |
|------|--------|
| *(no tier flag)* | **Default — host-native subagent per checkbox, never this thread.** Grok Build → `spawn_subagent`; Claude Code → `Agent` (or pooled Grok if host `CLAUDE.md` / work-ladder says so); Codex → spark mechanical / sol hard. See Host dispatch. Every tier flag below is an explicit *foreign* opt-in; which backends are auto-selectable is `meta_dev.ladder.pool` (`references/work-ladder.md`) |
| `--inline` | Main-thread execution, no subagents. **Only when the user passed it.** Never infer it. |
| `--review each\|phase\|end\|auto` | Review cadence. Default `auto` (`phase` if ≥2 phases, else `end`; `each` on critical-risk tasks). `each` = one task at a time + review hop (no parallel dispatch). |
| `--strict` | Serialize focused verification and repair. It never authorizes broad tests, never reruns green, and never turns BASELINE_RED/broad/manual evidence into a task or whole-run blocker. Disjoint READY tasks may still run in parallel. |
| `--deep` | Per-task headless DeepSeek worker + phase-gated review-agent (`deepseek-v4-pro` default, V4-Pro-0813; `--flash` for mechanical; `--vision` for screenshots/images → `deepseek-v4-flash-vision-exp`; fix-escalation goes one rung up `meta_dev.ladder.pool`) |
| `--glm` | Per-task headless GLM worker + phase-gated review-agent. **Available, not pooled** — never auto-selected; see `references/work-ladder.md` |
| `--grok` | Per-task headless Grok worker (`scripts/grok-headless-exec`) + phase-gated review-agent. Independent frontier reasoning and the third review family (xAI) |
| `--sonnet` | Per-task headless **Anthropic Sonnet 5** worker (`--backend sonnet`: a separate `claude -p` pinned to `claude-sonnet-5`, ambient login) → **Opus** `review-agent` at each phase gate → fixes via another headless sonnet worker (ladder sonnet→next pooled rung). Use when you want Anthropic-grade Sonnet off the main thread at the **200K** price — NEVER a Sonnet `Agent` subagent, which an `opus[1m]` session bills at the 1M rate |
| `--codex` | Per-task headless Codex worker (`${CLAUDE_PLUGIN_ROOT}/scripts/codex-headless-exec`, no `--backend`) + phase-gated **Opus** review-agent. Codex is a full executor AND the cross-family CODE-REVIEW lens — a GPT-class second opinion at phase gates / Stage 6. Reach for it when you want the GPT family doing the typing, not just the reviewing |
| `--budget auto\|low\|medium\|high` | **Depth cap** for the run (default `auto`). `auto` = classify each task. A concrete level is a **ceiling** — mechanical tasks may still drop to `low`. Forward the resolved word to every worker. See `references/execute-budget.md`. |
| `--effort <level>` | Thinking/reasoning effort forwarded to the headless worker: `low\|medium\|high\|xhigh\|max`. Applies to `--sonnet`/`--glm`/`--grok` (Anthropic + GLM default `high`); no-op for `--deep`. Drop to `medium`/`low` to conserve the Max Sonnet cap on bulk work; `xhigh` for the hardest tasks. Omit to use the per-backend default. Explicit `--effort` wins over `--budget`. |
| `--no-deploy` | Skip deploy prompt after archive |
| `--pause-before=<id>` | Hard stop before that task |
| `--no-pause` | Disable auto-pause on money-path/release-stability |
| `--stop-on-drift` | Halt on new origin/master commits |
| `--dry-run` | Parse + risk-tag + print, don't dispatch |
| `--autonomous` | **Run to the end unattended — the user is asleep.** Implies `--no-pause` and every pause gate off; judgment calls route to `fable-consult` instead of to the user; human-eyes gates defer to an end-of-run punch list. Does NOT relax the hard floor (guard denies, git bans, no deploy/publish/real migration, veto list, human-verify boxes stay unchecked, TRUE BLOCKERs still park the subject). Close with the Autonomous Run Report. See `references/autonomous-mode.md` |

Config: `bash scripts/config-get.sh` for models/filesystem sections.
