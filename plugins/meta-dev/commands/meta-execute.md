---
name: meta-execute
description: Subagent-driven plan execution — optimistic momentum (fix regressions async, keep moving), mandatory post-run code review, verify+commit+push between, auto-archive on completion (never deploys)
argument-hint: <plan-path> [--inline] [--strict] [--deep] [--glm] [--sonnet] [--codex] [--effort <level>] [--deploy] [--pause-before=<task-id>]
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

## ⛔ Prerequisite — visible main-thread task list (non-negotiable)

**Before starting work on ANY task (whether dispatched to a subagent or run `--inline`), the main thread MUST stand up a visible task list via `TaskCreate` — one entry per CHECKBOX in the plan (every `### Task N:` heading AND every `- [ ]` subtask checkbox nested under it) — and keep it live with `TaskUpdate` for the whole run.** Granularity is the point: the user runs `/meta-execute` to *watch* progress, so a list of fine-grained, checkbox-mapped entries is a primary deliverable — a list of 4 broad items hides progress; the same plan's 14 checkboxes as 14 entries shows it. No tracker visible = the run has not started correctly. Updates are mirrored *as each state changes* — never batched at the end.

Parse plan, dispatch one Sonnet subagent per task, commit + push between. **Optimistic by default:** never block forward progress on tests. After each task, run only the instant inline checks, then launch the task's test/verify suite **async in the background** and advance to the next task immediately — tests run in parallel while the run keeps moving. When an async verify comes back red, spawn a background fixer scoped to it, defer dependents, advance independent work, then solidify the foundation before completion. Only critical-risk tasks (`money-path` / `release-stability` / `schema-drift`) verify synchronously. `--strict` = old serial gate (every test runs inline and blocks).

## Charter

Read `references/execute-charter.md` before dispatching. Execution posture (optimistic momentum), anti-paranoia, CLAIMED protocol, failure posture matrix, resume logic, pause gates — all there.

## Flow

### Worker tier (`--deep`/`--glm`/`--sonnet`/`--codex`)

When a tier flag is present, run the **agentic-exec-loop** (skill: agentic-exec-loop, references/loop-protocol.md) instead of the Sonnet-subagent executor:

- Execute each task via a fresh headless worker — `${CLAUDE_PLUGIN_ROOT}/scripts/claude-headless-exec --backend deep|glm|sonnet [--effort <level>] --repo <plan-repo> -- <task spec incl. its Verify: command>`, or `${CLAUDE_PLUGIN_ROOT}/scripts/codex-headless-exec` for `--codex` (no `--backend`). If `--effort <level>` was passed to `/meta-execute`, forward it to every `claude-headless-exec` dispatch (sonnet/glm; no-op for deep); otherwise the script's per-backend default applies (sonnet=high, glm=high). The worker self-verifies. **`--sonnet` runs each task on a SEPARATE `claude -p` pinned to `claude-sonnet-5` (200K, no `[1m]`) via the ambient login — NEVER an Anthropic-model `Agent` subagent, which an `opus[1m]` conductor would bill at the 1M rate.**
- KEEP the per-task checkbox flip + per-task commit (unchanged).
- At each `## Phase N` boundary (or once at end for phase-less plans), dispatch `meta-dev:review-agent` over `git diff <phase_pre_sha>..HEAD`; branch on PASS/CONDITIONAL_PASS/FAIL per the protocol; run the deep→glm fix-ladder on FAIL.
- The conductor holds only the task list + per-phase verdict; it never reads diffs.
- **Context watchdog:** at each phase seam (after the verdict, phase committed) run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context-gauge.py`; on `CONTEXT_VERDICT=OVER` (default 300000) pause and `/meta-compact` forward before advancing — per loop-protocol → "Context watchdog". Keeps long playbooks ahead of the harness's hard auto-compact.
- **Runbook dashboard sync:** at the SAME phase seam, if the executing plan is a member of a campaign runbook, re-render it so the live dashboard tracks the phase that just landed — `RB=$(grep -rlF --include='_runbook-*.md' "<plan-path>" plans/); [ -n "$RB" ] && python3 ${CLAUDE_PLUGIN_ROOT}/scripts/runbook-render.py "$RB" && { git diff --cached --quiet "$RB" 2>/dev/null || { git add "$RB" && git commit -q -m "chore(runbook): refresh dashboard"; }; }`. Heed its stderr `⚠ stage-drift`; on final-phase pass bump the plan's `stage:`→6. Per loop-protocol → "Runbook dashboard sync". Without this the dashboard freezes mid-run on long-horizon executions.

If you (the orchestrating session) dispatch a worker expected to idle past ~4 min, keep your prompt cache warm per loop-protocol's cache-keepalive (270s) — session practice, not command automation.

Bare invocation (no tier flag) keeps the existing Sonnet path + Step 6 unchanged.

### 1. Resolve plan path + parse task inventory

Read the plan. Extract every **checkbox**: every `### Task N:` heading AND every `- [ ]` subtask checkbox nested under a task. Count them all — this checkbox count is the inventory the task list must match. Sub-tasks with `### Task N.M:` are separate. Phase headings are NOT tasks (they have no checkbox).

### 2. Mirror EVERY checkbox into the visible task list (MANDATORY — see Prerequisite)

Call `TaskCreate` once per **checkbox** from the step-1 inventory (every task heading AND every subtask checkbox), **descriptive, well-named** (`<ID> — what it builds/fixes`, not bare IDs). **Each entry carries a `[Backend]` tag** — `[DeepSeek]` (default/mechanical), `[GLM]` (stateful/complex), or `[Codex]` (cross-family code review only, not execution) — so the delegation ladder is visible in the list. Example: `◻ 17·P2b — multipass-promote (persist effective_config.json) [DeepSeek]`. Set dependencies. **The tracker item count MUST equal the step-1 checkbox count — 1 runtime task ↔ 1 plan checkbox, always; do not dispatch before the list is visible and complete.** Surface every state through the run via `TaskUpdate`: `in_progress` → `🔧 repairing (async)` / `deferred — waiting on <ID>` / `blocked` → `completed`, plus one entry per background fixer and a final `📋 code review` entry. **Each completed runtime task flips exactly its own matching plan checkbox (see ⛔ CHECKBOX RULE) — the two never drift apart.**

### 3. Pre-flight gates

- Read branch policy from host `CLAUDE.md` per `references/host-claude-contract.md`
- Working tree: if dirty files overlap plan file set → commit immediately, keep moving
- Confirm on the host's declared main branch
- `git fetch origin`: rebase silently if behind; only surface on conflict
- If `filesystem.git_corruption_mitigations` config is true → apply host-specific git mitigations
- Read `references/execute-charter.md` for full pre-flight details

### 4. Per task: claim → risk-tag → dispatch → verify → commit

For EACH task-list item:

1. Mark `in_progress` via `TaskUpdate`. CLAIM in plan file (per execute-charter.md). Commit claim.
2. Run `echo "<task body>" | bash scripts/risk-tag.sh` → get risk tags
3. Dispatch a **headless DeepSeek worker** (`${CLAUDE_PLUGIN_ROOT}/scripts/claude-headless-exec --backend deep`) with the task spec from `references/execute-dispatch.md` + risk-tag clauses — DeepSeek is the default per-task executor, not a Sonnet subagent. Escalate the task to a GLM worker (`--backend glm`) when it is stateful/complex/long-horizon; reserve an Anthropic-model subagent (Sonnet/Opus via `Agent`) only for tasks that genuinely need Anthropic judgment (subtle frontend consistency, cross-file stateful reasoning). Default: dispatch the next dep-satisfied, non-deferred task without waiting on in-flight fixers or in-flight tests (momentum). `--strict`: wait for the prior task to go green first.
4. Subagent returns → **instant inline checks only** (stub grep on the diff + declared-file existence — milliseconds). Commit + push. Then **launch the task's `Verify:`/test suite async in the background** (`Bash run_in_background`, tracked as its own tracker entry `🧪 testing <ID> (async)`) and DO NOT block on it. **Exception — critical gate:** if the task is risk-tagged `money-path`, `release-stability`, or `schema-drift`, run its verify synchronously and require green before advancing. **Never run the full baseline suite per task** — that's the slow part; it runs once at solidify (step 5). **The async test MUST be path-scoped** — run the task's named test file (`pytest path/test_x.py -q`, `-m "not slow and not gpu"`), NEVER `pytest <dir>/` or `pytest … -k <expr>` (both collect the whole tree = ~18× slower every cycle), and NEVER `svelte-check`/`tsc`/`build` per task. Full doctrine: `references/execute-charter.md` → Fast Test Doctrine.
5. **Advance immediately** to the next dep-satisfied task while tests run. Mark the task `✅ code done, tests pending`. When its async verify returns: **green** → mark `completed`, **IMMEDIATELY flip the plan checkbox to `[x] DONE`** (see ⛔ CHECKBOX RULE below). **Recoverable red** → spawn background fixer (execute-dispatch.md), mark task `blocked`, defer dependents, keep dispatching independents. **TRUE BLOCKER** → STOP, surface (see charter momentum gate).

### ⛔ MANDATORY CHECKBOX RULE — NEVER SKIP, NEVER DEFER

**Every time a task completes (green verify), edit the plan file and flip its checkbox BEFORE dispatching the next task — never batch, never defer to the end.** Unchecked boxes read as "nothing happened"; the checkbox is the user's primary visibility into progress and the single source of truth.

**The exact Edit operation (do this for EVERY completed task):**

```
Find in plan file:    - [ ] CLAIMED `Task N: <title>`
Replace with:         - [x] DONE `Task N: <title>`
```

If the task was never CLAIMED (resume or --inline):
```
Find in plan file:    - [ ] Task N: <title>
Replace with:         - [x] DONE Task N: <title>
```

**After each flip, commit immediately:** `chore(plan): mark <Task ID> DONE`. Then advance to the next task.

**Subtask checkboxes flip the same way.** A `- [ ]` nested under a task is its own checkbox — flip it `- [x]` the instant that sub-step is green, exactly like a top-level task. Nothing is "done" until its specific box is checked.

**Self-check before the report card (step 8):** `grep -cE '^[[:space:]]*[-*][[:space:]]+\[[[:space:]]\]' <plan-file>`. If the count is not zero for completed tasks, you missed checkboxes — go back and flip them NOW, before rendering the report card.

### 5. Solidify foundation

**Drain all in-flight async test/verify jobs** (wait for every backgrounded suite to report), all fixers green, no deferred/blocked tasks left → run the **full acceptance suite once** (the clustered test pass deferred from per-task). Gate: all green before proceeding. The run is NOT done while any async test job is still pending or red.

### 6. Mandatory post-run code review

**Default path:** end-of-run `superpowers:requesting-code-review` over `git diff <start>..HEAD`. **Tier-flag path (`--deep`/`--glm`/`--sonnet`/`--codex`):** the closing review is satisfied by the per-phase `meta-dev:review-agent` passes (always the **Opus** reviewer, regardless of which backend executed the tasks) — the final phase review IS the closing review (no separate end-of-run review). Either way, a run NEVER ends unreviewed. Route findings:

- **Trivial/mechanical** (lint, format, missing annotation) → fix inline, commit, push
- **Substantive** (logic, security, contract, scope creep) → surface to user with file:line in the Follow-ups section of the report card, do NOT silently auto-fix

Record verdict in the report card. If the review returns substantive findings, fix them before proceeding to housekeeping.

**Persist the review verdict — the end-of-run DONE-gate reads it (MANDATORY).** The `on-run-complete.sh` Stop hook stamps this plan DONE (stage 6) automatically once execution is complete AND a `review_verdict(pass)` is on record; without that event the gate leaves the plan at stage 5 and flags "review missing." Once the run's review resolves to a pass (default path: no substantive findings left; tier path: the final phase PASS), emit it:

```bash
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
bash ${CLAUDE_PLUGIN_ROOT}/scripts/state-append.sh "{\"event\":\"review_verdict\",\"plan\":\"<plan-path>\",\"verdict\":\"pass\",\"time\":\"$NOW\"}"
```

On a substantive FAIL that halts the run, emit `\"verdict\":\"fail\"` (or omit). Either way the run NEVER silently ends half-stamped: the gate either advances it to DONE or surfaces what's outstanding to the inbox.

### 7. Housekeeping

Archive the plan (unless manual gates remain — e.g., GPU acceptance, in-app verification), commit + push both repos. The stage already propagated to the plan's YAML via the `stage-emit.sh` call above; cross-plan ordering lives in `plans/meta-runbook.md` — touch it only if execution priority changed.

### 8. Render execution report card

ALWAYS end with this structured dashboard. Use `references/execute-report-card.md` for the exact layout. The report MUST include every section below — no sprawl, no stream-of-consciousness narration.

```
╔══════════════════════════════════════════════════════════════════╗
║         📋 /meta-execute — EXECUTION REPORT CARD               ║
╚══════════════════════════════════════════════════════════════════╝

  Plan:         <plan-title>
  Path:         <plan-path>
  Status:       EXECUTED + REVIEWED (or EXECUTED · awaiting manual gate)
  Duration:     <elapsed>

  ── Tasks ──
  ✅ <done>/<total> completed · <failed> failed · <deferred> deferred

  ── Commits (on <repo> master) ──
  <short-sha>  <description>                    <verify-result>

  ── Code Review ──
  ✅ CLEAN — 0 findings (or)
  ⚠️  <N> findings fixed · 0 remaining (or)
  ❌ <N> findings surfaced — see Follow-ups

  ── Acceptance ──
  <test-suite> <pass>/<total> · <other-gates>

  ── Plan Location ──
  ✅ Archived: plans/<repo>/_archive/<name>/  (or)
  📍 Active:   plans/<repo>/<name>/  (reason: <manual gate pending>)

  ── Follow-ups ──
  • <item> — <action needed> — <who>
  • (empty if none)
```

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
| `--inline` | Main-thread execution, no subagents |
| `--strict` | Disable optimistic momentum — every verify/test runs inline and blocks, serial gate, every red is a hard STOP, no background fixers, no async tests |
| `--deep` | Per-task headless DeepSeek worker + phase-gated review-agent (**default execution tier**; GLM only on fix-escalation) |
| `--glm` | Per-task headless GLM worker + phase-gated review-agent (stateful/complex/long-horizon) |
| `--sonnet` | Per-task headless **Anthropic Sonnet-200K** worker (`--backend sonnet`: a separate `claude -p` pinned to `claude-sonnet-5`, no `[1m]`, ambient login) → **Opus** `review-agent` at each phase gate → fixes via another headless sonnet worker (ladder sonnet→glm). Use when you want Anthropic-grade Sonnet off the main thread at the **200K** price — NEVER a Sonnet `Agent` subagent, which an `opus[1m]` session bills at the 1M rate |
| `--codex` | NOT a per-task execution worker. Codex is the cross-family CODE-REVIEW lens — a GPT-class second opinion used at phase gates / Stage 6, not for per-task execution. Execution stays on DeepSeek (default) → GLM (stateful) |
| `--effort <level>` | Thinking/reasoning effort forwarded to the headless worker: `low\|medium\|high\|xhigh\|max`. Applies to `--sonnet` (default `high`) and `--glm` (default `high`); no-op for `--deep`. Drop to `medium`/`low` to conserve the Max Sonnet cap on bulk work; `xhigh` for the hardest tasks. Omit to use the per-backend default |
| `--no-deploy` | Skip deploy prompt after archive |
| `--pause-before=<id>` | Hard stop before that task |
| `--no-pause` | Disable auto-pause on money-path/release-stability |
| `--stop-on-drift` | Halt on new origin/master commits |
| `--dry-run` | Parse + risk-tag + print, don't dispatch |

Config: `bash scripts/config-get.sh` for models/filesystem sections.
