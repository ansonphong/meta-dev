---
name: grok-execute
argument-hint: "<task description> [--repo <name>] [--readonly] [--model <model>] [--effort <level>] [--max-turns <n>]  # --repo names from .claude/meta-dev-repos.json"
description: "Execute a task via headless xAI Grok (Grok Build CLI). Grok is its OWN harness (like Codex) — it cannot run our slash commands, so give it a DIRECT task. Like Codex, Grok can read AND write, so it serves double duty: a full general-purpose execution worker (sibling of /deep-execute and /glm-execute) AND a third cross-family review lens (xAI family, alongside Anthropic and OpenAI). Default model grok-4.5."
---

# /grok-execute — Grok Headless Execution

Spawn a headless **xAI Grok** worker (`grok --prompt-file … --output-format json`) to run a task, then report the result back. You stay on your current backend (Opus) for orchestration while Grok does a bounded, focused job.

Uses `scripts/grok-headless-exec` under the hood, which emits the **same clean result contract** as `claude-headless-exec` and `codex-headless-exec` (`OUTPUT_FILE` = `{is_error, subtype, num_turns, duration_ms, session_id, result, usage, backend, stop_reason}`), so it plugs into `/auto-execute` exactly like `/deep-execute`, `/glm-execute`, and `/codex-execute`.

## ⚠️ Grok is a DIFFERENT harness — not Claude Code

Same structural caveat as `/codex-execute`. `/deep-execute`, `/glm-execute`, and `/sonnet-execute` spawn a full **Claude Code** instance on another model's Anthropic endpoint, so the worker has our whole harness and can **run our slash commands internally** (`/meta-execute`, `/loop-gap`, etc.). **Grok does NOT.** A grok worker is xAI's own agent (the "Grok Build" CLI) — it has no `/meta-execute`, no `/loop-gap`, no project skills.

Consequence: **give Grok a direct task, never a "run `/command`" instruction.** Say *"Fix the failing test in Z"* or *"Audit X for gap class Y and report findings"* — not *"run `/loop-gap` on this plan"* (it can't). The conductor (Opus) or a claude-harness worker applies anything that needs our harness.

## When to Use — full execution worker AND cross-family review

Grok occupies a unique slot: it is **both** a general execution tier **and** a cross-family reviewer.

- **As an executor:** Grok 4.5 is a frontier-tier model that **can write files** (like Codex under `--sandbox workspace-write`) — so it can do real bounded implementation work (fixes, refactors, scaffolding), not just read-and-report. Use it like `/deep-execute` or `/glm-execute` for a self-contained task where an independent strong model is wanted.
- **As a reviewer:** Point it (read-only via `--readonly`) at a diff, the changed files, or a specific finding. An xAI-family model reviewing Claude/GLM/DeepSeek/OpenAI output is a **third independent family** — it catches failure modes that same-family review (and even the OpenAI/Codex lens) miss. That independent-family lens is the entire value of Grok-as-reviewer.

**Where it sits on the work ladder:** DeepSeek (cheap/mechanical) → GLM (complex/stateful) remain the execution farm; Grok is a **higher-cost frontier option** for tasks that earn it (hard reasoning, a wanted second family) — not a bulk farm. Treat its quota/budget with the same deliberation as Codex, not the fan-out freedom of DeepSeek.

## Test discipline — keep every test cycle cheap

When the task runs tests, **path-scope, always.** Run only the named test file — `pytest path/to/test_x.py -q` (add `-m "not slow and not gpu and not integration"` if the suite marks them). NEVER bare `pytest`, `pytest <dir>/`, or `pytest … -k <expr>` (they collect the whole tree first). NEVER `svelte-check`, `tsc --noEmit`, `npm run build`, or the full suite in an inner cycle. Confirm green once; don't re-run a passing test. (Grok is its own harness, so it can't read the meta-dev charter internally — this clause IS the rule for grok runs.)

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect from cwd; names from .claude/meta-dev-repos.json)
- `--readonly` — enforced read-only (deny Write/Edit). Use for all audits/reviews. Grok's deny-rule sandbox blocks every write path (write tool, shell redirection, search_replace) — verified empirically.
- `--model <model>` — override grok model (default: `grok-4.5`, pinned)
- `--effort <level>` — reasoning effort for the model
- `--max-turns <n>` — cap agent turns (default: uncapped; bounded by the 120-min timeout)
- `--timeout <ms>` — wall-clock timeout (default `7200000` = 120 min)

Everything else is the task description. If none is given, ask what task to run.

## Step 2: Confirm the Plan

Summarize before running:
- **Backend:** Grok (`grok --output-format json`)
- **Model:** grok-4.5 (or override)
- **Repo / Work dir:** (detected or specified)
- **Task:** (the task description)
- **Mode:** read-only (audit/review) or execute (writes allowed)

If the task is destructive or writes outside the repo, confirm with the user first. For gap-checking/hardening/review, **default to `--readonly`** — Grok reports, you decide.

## Step 3: Execute

Run the headless worker. For tasks expected to take >30s, use `run_in_background: true` so the session stays responsive.

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/grok-headless-exec \
  ${REPO:+--repo "$REPO"} \
  ${MODEL:+--model "$MODEL"} \
  ${EFFORT:+--effort "$EFFORT"} \
  ${MAX_TURNS:+--max-turns "$MAX_TURNS"} \
  ${READONLY:+--readonly} \
  ${TIMEOUT:+--timeout "$TIMEOUT"} \
  -- <task description>
```

**Repo detection:** `--repo` wins; else infer from `pwd`; if ambiguous (in parent repo), ask which repo to target.

**Note on progress:** Grok's `--output-format json` writes the entire result object at completion (it does not stream), so a long run will appear silent until it returns. The wall-clock timeout is the safety net — be patient on deep tasks.

## Step 4: Report Results

The script distills the worker's output — three files per run:
- **`OUTPUT_FILE`** (printed as `OUTPUT_FILE=<path>`) — clean JSON: `{is_error, subtype, num_turns, duration_ms, session_id, result, usage, backend, stop_reason}`. `result` is Grok's final message. `json.load()` it directly.
- **`<OUTPUT_FILE>.raw`** — the full `grok --output-format json` object incl. the `thought` trace (deep debugging).
- **`<OUTPUT_FILE>.stderr`** — the worker's stderr.

The script also prints the distilled `result` between `RESULT` rules, so for a foreground run you can read it straight from the command output.

When execution completes:
1. **Read `OUTPUT_FILE`** (or the printed `RESULT` block) — already clean JSON.
2. **Check `is_error`** and the `Exit code` line — exit `3` = distill failed (inspect `.raw`), exit `4` = worker reported error, exit `124` = timed out. A non-`EndTurn` `stop_reason` (e.g. `MaxTurns`) is surfaced as a note appended to the result but does not by itself mark error.
3. **Summarize** — what Grok found/did, files touched (if execute mode), any issues.
4. **Apply / next steps** — for reviews, the value is the findings: triage them and apply fixes yourself or via a claude-harness worker. Remind the user Grok's changes (if any) are **not** auto-committed.

## Safety Notes

- Grok must be authenticated (`~/.grok/auth.json` — via `grok login`, OAuth to grok.com / xAI). The script warns if auth is missing.
- `--readonly` enforces read-only via Grok's deny rules (`--deny Write --deny Edit`), which block every write path including shell redirections. It is NOT paired with `bypassPermissions` (that would defeat it).
- Execute mode uses `--permission-mode bypassPermissions --always-approve` — full autonomy to edit files in the work dir, but **cannot commit** (review and commit yourself).
- Grok's changes are NOT automatically committed.
- **Mind the budget** — Grok 4.5 is a frontier model on your grok.com account. Prefer one well-scoped call over many; don't fan Grok out the way you'd fan out DeepSeek. Reserve it for hard reasoning or the independent-family review lens.
