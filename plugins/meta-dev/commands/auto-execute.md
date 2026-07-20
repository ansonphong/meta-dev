---
name: auto-execute
argument-hint: <any task, prompt, plan, or meta-dev op> [--deep|--glm|--sonnet|--codex] [--effort <level>] [--repo <name>] [--readonly] [--max-turns <n>] [--autonomous]  # --repo names from .claude/meta-dev-repos.json
description: "Opus-conducted headless work router for ANY task — brainstorm, design, plan, harden, execute, review/audit, or any arbitrary prompt/plan. Decomposes a job into chunks and farms each NATIVELY to the host harness by default (Claude Code → an Agent subagent; Codex → gpt-5.3-codex-spark on its own weekly quota), with --deep (DeepSeek, cheapest external), --glm (long-horizon), --sonnet, and --codex (first-class executor AND the cross-family review lens) as explicit opt-ins; reviews every round-trip, escalates native→DeepSeek→GLM on failure."
---

# /auto-execute — Conducted Headless Work (any task)

**You (Opus) stay the main thread — the conductor.** This skill spins up headless workers on the cheapest backend that can do the job, reviews what comes back, and only escalates when it must. It's the single, general entry point: point **anything** at it — a one-line prompt, a research question, a plan, a whole multi-phase initiative, or any specific meta-dev stage — and it routes, chunks, dispatches, and verifies.

## What you can route through it (it is fully general)

`/auto-execute` is **not execute-only** — it conducts **any kind of work**, because a worker is a full headless Claude Code instance that can invoke **any skill/command internally** (the same way it runs `/meta-execute` on a phase). So it can drive:

- **Any of the 6 waterfall stages** — BRAINSTORM, DESIGN, PLAN (`/meta-planner`), HARDEN (`/loop-gap`), EXECUTE (`/meta-execute`), REVIEW (`/meta-eval`, code review). See "Use it for any meta-dev work" below.
- **Any standalone meta-dev op** — `/sniff`, `/meta-security`, `/meta-ux`, `/meta-audit`, `/meta-probe`, changelog, version bump, etc.
- **Any arbitrary task** — "research X and write a summary", "refactor module Y", "draft a design doc", "investigate this bug", "review this diff". No plan required; a bare prompt is a valid job.

The conductor loop, routing bias, review gate, and gating rules below are **identical regardless of what the job is** — only the chunk *content* and the *worker's internal command* change.

**Purpose.** Delegate **as much work as possible, automatically**, off the main thread. Opus is the **top-level planner + reviewer**; the workers run what Opus plans. If a chunk *can* be farmed out, farm it — main-thread Opus does the thinking (decompose, route, review, integrate), not the typing. This protects Opus's context while keeping spend low.

Unflagged, it delegates **natively to whatever harness you are running in**. Wraps `/deep-execute`, `/glm-execute` (`scripts/claude-headless-exec`), and `/codex-execute` (`scripts/codex-headless-exec`) when an external backend is explicitly requested. Read their docs for backend specifics; this skill is the **orchestration layer** on top.

## The Core Bias — native by default, escalate only when needed

**The unflagged tier is native delegation — no external backend at all.** External backends are **explicit opt-ins** (`--deep`, `--glm`, `--sonnet`, `--codex`). When you do go external, DeepSeek is still the cheapest one and still the right first step; the way to make it viable even for big work is to **break the job into bounded chunks DeepSeek can hold, do one chunk, check it, then the next.** Reserve GLM for what genuinely needs it.

```
DEFAULT  → NATIVE     host-harness native delegation, no flag: in Claude Code a
                      native Agent subagent; in Codex `codex exec -m
                      gpt-5.3-codex-spark` (SEPARATE weekly quota from the
                      gpt-5.6 family → cheapest tier there is)
ROUTE    → DeepSeek   `--deep` — cheapest EXTERNAL tier; small / bounded /
                      mechanical / self-contained chunks
ESCALATE → GLM        ONLY when a chunk truly requires it:
                        • long-horizon / multi-phase that can't be chunked
                        • cross-file STATEFUL refactor needing a held thread
                        • frontend / Svelte design consistency across components
                        • DeepSeek returned the chunk but it FAILED your review
OPT-IN   → Codex      `--codex` — a first-class EXECUTOR (GPT family) as well as
                      the cross-family REVIEW lens; see below
OPT-IN   → Sonnet     `--sonnet` — Anthropic-grade judgment at the 200K tier
```

When unsure, **try the native tier first** (no flag) — escalation native→DeepSeek→GLM is cheap, GLM-by-default is not (full heuristic: CLAUDE.md → Multi-Model Execution).

**Codex is a first-class EXECUTOR *and* the cross-family review lens.** `--codex` can take real execution, hardening, and gap-fixing chunks — dispatch it with `--sandbox workspace-write` when the worker must edit files, `--sandbox read-only` when it only reads and reports findings back for you to apply. Route it **spark-first** (`gpt-5.3-codex-spark`, a separate weekly quota from the gpt-5.6 family → effectively free capacity); reserve the heavier Codex tiers, which run on a limited Codex Plus quota, for work that earns them.

It remains **also** the cross-family code-review lens — a GPT-class second opinion reviewing a diff at a phase gate / Stage 6, where independent-family review catches what Claude / GLM / DeepSeek share blind spots on. That role is unchanged; it is simply no longer Codex's *only* role.

⚠️ **A Codex worker is OpenAI's own agent, NOT Claude Code** — it canNOT run our slash commands internally (`/meta-execute`, `/loop-gap`, etc.) the way GLM/DeepSeek workers can. Hand it a **direct task** ("apply X to files A/B", or "review this diff for correctness/regressions and report findings"), never a "run `/command`" instruction — though it *can* be pointed at a procedure file to follow (`/codex-execute --skill|--command`). Anything that genuinely needs our slash-command harness goes to the conductor (you) or a claude-harness worker.

## The Conductor Loop

You run this loop on the main thread. **Never just fire one giant task at a backend** — decompose, dispatch, verify, repeat.

1. **Decompose** — split the job into the smallest chunks that still make sense as a unit (one file, one phase, one well-scoped transform). Hold the chunk list in a task tracker (you own it). This is what protects your context and keeps DeepSeek on-thread. **If the job is a multi-phase meta-planner plan, the chunk unit is the phase/wave file — see "Multi-phase plans" below; that mode overrides the default chunking.**
2. **Route** — per chunk, pick the backend with the bias above. Default native (no flag); mark any chunk that needs an external backend and why.
3. **Dispatch** — run the chosen backend. For >30s work use `run_in_background: true`; a single self-contained spec per chunk (paths, constraints, exact deliverable, verify hook). Independent chunks → dispatch in parallel. The spec can be a raw task, a file/plan to act on, or an explicit *"run `/<command> <target>`"* instruction (e.g. `/meta-planner`, `/loop-gap`, `/meta-execute`, `/meta-eval`, `/sniff`) — the worker has the full harness. **For any code-writing chunk, include the test-minimalism policy AND the test discipline in the spec** — DeepSeek/GLM/Codex default to over-testing AND to running the whole suite. Tell every worker explicitly: *critical-breakage tests only, do not retrofit existing tests; and PATH-SCOPE every test — run only the named test file (`pytest path/test_x.py -q`), NEVER `pytest <dir>/` or `pytest … -k <expr>` (~18× slower per cycle), NEVER svelte-check/tsc/build/full-suite per task — those run once at phase end* (CLAUDE.md → Testing; meta-dev `execute-charter.md` → Fast Test Doctrine). (Read-only chunks — research, audit, review — don't need it.)
4. **Round-trip review** — when a chunk returns, read the worker's distilled result (`OUTPUT_FILE`) to confirm `is_error: false`. Then **delegate the review — dispatch `meta-dev:review-agent`** for the chunk (per the agentic-exec-loop protocol: `skills/agentic-exec-loop/references/loop-protocol.md`). Read ONLY its verdict; do NOT read the diff into this context. The verdict is the quality gate, not the worker's self-report.
5. **Pass / fail — branch on the review-agent verdict:**
   - **PASS** → integrate, mark the chunk done, go to the next.
   - **CONDITIONAL_PASS** → apply the suggested fixes via one deep Fixer, then advance (no re-review).
   - **FAIL** → fix inline if trivial, else **re-dispatch — escalating DeepSeek→GLM** (a chunk DeepSeek fumbled is exactly an escalation signal). Fix ladder: deep → glm fixer, max 2 attempts, then **consult Fable before surfacing** (`scripts/fable-consult.sh` — two failures on the same thing is a hard challenge, and surfacing costs the user a round-trip). Don't loop the same backend on the same failure twice.
   - **Judgment call, any point in the loop** → before you stop to ask the user anything — a design trade-off, an under-specified chunk, which of two structures to build — run `scripts/fable-consult.sh --question "<the decision>"`. Adopt at exit `0`; on any other exit escalate **carrying Fable's recommendation as the lead option** with its confidence reported exactly as returned. Safety-class decisions (destructive/deploy/security/money/schema/cross-repo) skip the consult and always reach the user. Skill: `fable-consult`.
6. **Context watchdog — compact at a wave seam when OVER.** Between chunk batches (a committed seam), run the gauge and read only `CONTEXT_VERDICT`:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context-gauge.py   # default threshold 300000
   ```

   `OK`/`UNKNOWN` → continue to the next wave. `OVER` → don't start the next wave: invoke `/meta-compact` (forward handoff whose ▶ NEXT ACTION is "resume at the next wave/chunk"), surface the `/compact read …` trigger, and STOP for the user to compact. Resume continues the loop. Threshold: `--threshold N` or env `META_DEV_CONTEXT_THRESHOLD`. This is the same watchdog the per-phase loop uses (agentic-exec-loop → "Context watchdog"); it keeps long jobs ahead of the harness's blunt hard auto-compact.
7. **Integrate & report** — once all chunks pass, summarize what landed, what was reviewed, residual risk. Close with the Next Steps Dashboard.

## Multi-phase plans — one phase/wave per round (meta-planner plans)

When the job is a **meta-planner plan with multiple phases/waves**, do NOT chunk by task or by arbitrary file — **chunk by phase file**, and execute the plan **one phase at a time, in dependency order**.

**Detect this mode** when the target is a meta-planner plan directory: a `00-master-plan.md` (the master/index that lists the phases) alongside `phase-N-<slug>.md` (a.k.a. "wave") files, e.g.:

```
plans/<repo>/<plan-dir>/
├── 00-master-plan.md                      ← master/index (lists the phases, dep order)
├── phase-1-<slug>.md                      ← wave 1
├── phase-2-<slug>.md                      ← wave 2
├── phase-3-<slug>.md                      ← wave 3 (Task 3.1, 3.2, … inside)
├── phase-4-<slug>.md                      ← wave 4
└── …                                       ← phase-5, 6, 7 …
```

**The per-phase loop (you, the conductor, run this):**

1. **Read `00-master-plan.md`** — get the ordered phase list and any cross-phase dependencies. Each `phase-N-*.md` is one round.
2. **One worker per phase.** For phase N, dispatch **one** worker (`/deep-execute` or `/glm-execute`) whose entire job is **that one phase file**. **Never split a phase across workers; never bundle two phases into one worker.**
3. **The worker runs `/meta-execute <phase-file>` internally.** The chunk spec you hand the worker is: *"Run `/meta-execute plans/.../phase-N-<slug>.md`. Read `00-master-plan.md` first for context. Execute every task in that ONE phase file in order; do not touch other phase files. Follow the project test policy (critical-breakage tests only)."* `/meta-execute` is the per-task executor (claim → dispatch → verify → commit → checkbox flip) — it keeps the worker on-thread within the phase. Do **not** ask the worker to freelance task-by-task.
4. **Code-review the phase** when the worker returns — read the worker's distilled result (`OUTPUT_FILE`) to confirm `is_error: false`. Then dispatch `meta-dev:review-agent` for the phase (per the agentic-exec-loop protocol). Read ONLY its verdict; do NOT read the diff into this context. The verdict is your quality gate, per the Round-trip review step.
5. **Advance — branch on the review-agent verdict.** PASS → move to phase N+1. CONDITIONAL_PASS → apply fixes via one deep Fixer, then advance. FAIL → fix inline if trivial, else re-dispatch escalating DeepSeek→GLM (fix ladder: deep → glm, max 2 attempts, then surface). Respect dependencies: never start phase N+1 if it depends on a phase that hasn't landed green.
6. **Context watchdog between phases.** After phase N lands green and is committed, run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context-gauge.py` (default 300000). On `CONTEXT_VERDICT=OVER`, pause at this seam: `/meta-compact` (handoff ▶ NEXT ACTION = "resume at phase N+1"), surface the trigger, STOP for the user to compact, then resume. On `OK`, advance to phase N+1. (Same watchdog as agentic-exec-loop → "Context watchdog".)

**Routing per phase:** a phase is a cohesive, stateful, multi-task unit (Task N.1 → N.2 → …), so it usually leans **GLM** (keep-it-whole). Use **DeepSeek** for a phase whose tasks are small and disjoint/mechanical. Default per the core bias; escalate DeepSeek→GLM on a failed phase review.

**Fat-phase fan-out (split the phase across backends).** If a phase is large (more than ~3 tasks, or a stateful core + many mechanical leaves — e.g. one resolver rewrite + 20 identical call-site swaps), don't make one worker swallow it. As conductor, **decompose before dispatch:** GLM holds the **stateful core** (the judgment-heavy, cross-file change), and **DeepSeek takes the mechanical leaves in parallel** (the repetitive find-replace-verify units — its cost edge). Then you review each diff. That's typically 1 GLM dispatch + 1–2 background DeepSeek dispatches per heavy phase. (Better still: such a phase should have been split at authoring — see `/meta-planner` phase-size cap — but fan-out handles the ones that slip through.)

## Dashboard stage signal — conductor-emit (keep the dashboard honest)

When you run a **waterfall stage on a plan** through this skill — above all when you dispatch a headless worker for a stage (executing a meta-planner plan, a harden pass, a plan/review pass) — **you (the conductor) emit the stage transition yourself.** Do NOT rely on the worker: a headless DeepSeek/GLM/Codex worker may skip the emit instruction, and a Codex worker can't run our commands at all. You are reliable Opus, so emit here for a guaranteed signal.

- **Before dispatching** the stage's worker → emit `in_progress`.
- **After the round-trip review passes** (stage landed green) → emit `completed` (or `blocked` if it failed and you're halting).

Emit by appending one event to the project's dashboard log — self-contained, no dependency on the worker or the plugin path:

> **⛔ NEVER emit the raw worker `result` text to the dashboard.** The emit writes ONLY verdict/metadata fields below. Defense-in-depth: the distillers (`distill-headless-result.py`, `distill-codex-result.py`) redact known key shapes before writing `result`.

```bash
python3 - "<plan-path>" "<stage>" "<status>" <<'PY'
import json, sys, os, datetime
plan, stage, status = sys.argv[1:4]
num = {"brainstorm":1,"design":2,"plan":3,"harden":4,"execute":5,"review":6}.get(stage, 0)
os.makedirs("plans/_dashboard", exist_ok=True)
ev = {"event":"stage_transition","plan":plan,"stage":stage,"stage_num":num,
      "status":status,"time":datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
with open("plans/_dashboard/state.events.jsonl","a") as f:
    f.write(json.dumps(ev)+"\n")
PY
```

`<stage>` ∈ `plan|harden|execute|review` (what the worker is doing). Idempotent with the start-hook and the command's own emit — the reducer keeps the latest, so double-emits are harmless. For a **multi-phase plan**, emit `execute in_progress` when the phase loop begins and `execute completed` once all phases land green. (Run from the project root so `plans/_dashboard/` resolves; `/meta-dashboard` reduces the log on render.) The stage 5→6 (DONE) advance is then enforced by `on-run-complete.sh` — it stamps DONE once all execution checkboxes are flipped and a `review_verdict(pass)` is on record, or FAILS LOUD to the inbox otherwise.

## Gating — code-writing executes stay gated

`/auto-execute` inherits the project's hard rule: **design / plan / harden / review / audit chunks flow freely**, but **code-writing plan execution requires Phong's explicit "go"** (see CLAUDE.md → Action Discernment + the Development Waterfall). Routing through a cheaper backend never relaxes the gate — a DeepSeek worker writing app code is still a plan execution. Read-write chunks outside a gated plan (ad-hoc fixes, refactors you'd normally just do) follow the same >90%-confident / in-scope / reversible discernment as any direct edit.

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

- `--deep` / `--glm` / `--sonnet` / `--codex` — force a backend, skip routing (still chunk + review). `--sonnet` pins each chunk to a separate headless Anthropic Sonnet-200K worker (`claude-headless-exec --backend sonnet`, `claude-sonnet-5`, no `[1m]`) — Anthropic-grade judgment at the 200K price, never a Sonnet `Agent` subagent (an `opus[1m]` session bills those at 1M). `--codex` is a first-class executor **and** the cross-family review lens (see Core Bias) — route it spark-first and dispatch through `scripts/codex-headless-exec` (`--sandbox workspace-write` when it edits, `--sandbox read-only` when it only reports back).
- `--effort <level>` — thinking/reasoning effort forwarded to each headless worker: `low|medium|high|xhigh|max`. Applies to `--sonnet`/`--glm` (both default `high`); no-op for `--deep`. Drop to `medium`/`low` to conserve the Max Sonnet cap on bulk chunks; `xhigh` for the hardest work. Omit to use the per-backend default
- `--repo <name>` — target repo (default: auto-detect from cwd; names from .claude/meta-dev-repos.json)
- `--readonly` — restrict workers to read-only tools (audits/reviews — route freely, either backend)
- `--max-turns <n>` — cap worker turns
Everything else is the job description. If none is given, ask what to execute.

## Step 2: Plan the Run

State briefly, before dispatching:
- **Job** and its **chunk breakdown** (the ordered list).
- **Per-chunk backend** (default native; name any flagged external backend + reason).
- **Whether any chunk is a gated code-write** — if so, get "go" first.

## Step 3: Run the Conductor Loop

Execute the loop above. Track chunks live. Dispatch via the underlying script:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/claude-headless-exec \
  --backend <deep|glm> \
  ${EFFORT:+--effort "$EFFORT"} \
  ${REPO:+--repo "$REPO"} \
  ${READONLY:+--readonly} \
  ${MAX_TURNS:+--max-turns "$MAX_TURNS"} \
  -- <self-contained chunk spec>
```

`OUTPUT_FILE` is clean JSON (`{is_error,result,num_turns,duration_ms,…}`); `.raw` = full trace, `.stderr` = worker stderr. Check `is_error` and exit code (3 = distill failed, 4 = worker error) on every return.

**Codex backend:** dispatch via `scripts/codex-headless-exec` instead (same flags **minus** `--max-turns`; add `--readonly` for audits, `--sandbox workspace-write` for fixes). It emits the **identical `OUTPUT_FILE` contract**, so review it the same way (exit 124 = timed out). Remember: a codex worker can't run our slash commands — give it the task directly, not a `/command`.

## Step 4: Report

Per the Conductor Loop step 7 — what each backend did, what you reviewed, escalations taken, and next steps. Remind: worker changes are **not** auto-committed.

## Use it for any meta-dev work — all 6 waterfall stages

This is the intended substrate for the **entire Development Waterfall**, not just execution — farm the heavy lifting to workers, native-first, you reviewing each round-trip. Each stage is just a different worker command / chunk content; the conductor loop is the same.

- **BRAINSTORM** — farm research/exploration chunks (read-only, either backend) — "survey how X works", "list options for Y with tradeoffs". You synthesize the intent.
- **DESIGN** — farm design-doc drafting (a section per chunk for a big doc; GLM for a cohesive whole). You own the architecture call; workers draft + you review.
- **PLAN** (`/meta-planner`) — worker runs `/meta-planner <plan>` to restructure into phase files, or farm bounded research/drafting chunks; you assemble + review.
- **HARDEN** (`/loop-gap`) — farm per-file / per-gap scans to DeepSeek chunks; escalate a subtle whole-plan consistency pass to GLM. Worker can run `/loop-gap <dir>` directly. Hardening is mechanical→complex work — native-first, then DeepSeek→GLM; `--codex` is also available here as an executor (spark-first), not just for REVIEW below.
- **EXECUTE** (`/meta-execute`) — for a **multi-phase meta-planner plan, farm one phase/wave file per round** (see "Multi-phase plans" above): one worker per phase, the worker runs `/meta-execute` on that phase, you code-review, then advance. For a flat single-file plan, farm per-task chunks native-first (DeepSeek on `--deep`), GLM for the stateful ones. Either way — **only once the plan execution is authorized** (the gate holds).
- **REVIEW & VALIDATE** (`/meta-eval`, code review) — worker runs `/meta-eval <plan>` or a read-only code review over a diff; route freely (read-only, not gated). Cross-backend verification is a feature: have GLM review what DeepSeek built, or vice versa. **This is Codex's highest-leverage job (though no longer its only one):** use `--codex` for a **true cross-family CODE REVIEW** (a different model family — GPT — reviewing the diff), the highest-signal verification when correctness really matters.

**Beyond the waterfall:** any standalone op (`/sniff`, `/meta-security`, `/meta-ux`, `/meta-audit`, `/meta-probe`, changelog, version) and any **arbitrary task or bare prompt** routes the same way. If you can describe it as a self-contained chunk with a deliverable, `/auto-execute` can farm it.

See CLAUDE.md → Development Waterfall + Multi-Model Execution for how this wires in.
