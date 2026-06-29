---
name: codex-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--model <model>] [--sandbox <mode>]  # --repo names from .claude/meta-dev-repos.json
description: Run a cross-family CODE REVIEW via headless OpenAI Codex (GPT). Codex is used ONLY for code review — the cross-family review lens at phase gates / Stage 6. Not a general execution, hardening, or verification worker. Used sparingly (Codex Plus quota).
---

# /codex-execute — Codex Headless Execution

Spawn a headless **OpenAI Codex** worker (`codex exec`) to run a task, then report the result back. You stay on your current backend (Opus) for orchestration while Codex does a bounded, focused job.

Uses `scripts/codex-headless-exec` under the hood, which emits the **same clean result contract** as `claude-headless-exec` (`OUTPUT_FILE` = `{is_error, subtype, num_turns, duration_ms, session_id, result, usage}`), so it plugs into `/auto-execute` exactly like `/glm-execute` and `/deep-execute`.

## ⚠️ Codex is a DIFFERENT harness — not Claude Code

This is the one structural difference from `/glm-execute` and `/deep-execute`. Those spawn a full **Claude Code** instance on another model's Anthropic endpoint, so the worker has our whole harness and can **run our slash commands internally** (`/meta-execute`, `/loop-gap`, etc.). **Codex does NOT.** A codex worker is OpenAI's own agent — it has no `/meta-execute`, no `/loop-gap`, no project skills.

Consequence: **give Codex a direct task, never a "run `/command`" instruction.** Say *"Audit X for gap class Y and report findings"* or *"Fix the failing test in Z"* — not *"run `/loop-gap` on this plan"* (it can't). The conductor (Opus) or a claude-harness worker applies anything that needs our harness.

## When to Use — CODE REVIEW ONLY (cross-family review lens)

**Codex has exactly one job here: code review.** It is the cross-family (GPT-vs-Claude) second opinion at a **phase gate or Stage 6** — point it (read-only) at a diff, the changed files, or a specific finding and have it review for correctness/bugs/regressions. A GPT-class reasoner reviewing Claude/GLM/DeepSeek output catches what same-family review misses; that independent-family lens is the entire value.

**Cost reality: Codex runs on a $20/mo Plus quota** — far lighter headroom than our GLM / DeepSeek / Claude usage. So Codex is **not a farm.** Reserve it for **a smaller number of high-value review calls** where the cross-family lens earns its keep.

**Do NOT route execution, hardening, or gap-fixing *work* to Codex.** Codex is OFF the execution ladder. Mechanical/bounded work → DeepSeek; complex/stateful/long-horizon work and plan-writing → GLM. Hardening and gap-checking are delegated to DeepSeek→GLM, not Codex. Codex reviews the code those backends produce; it does not produce or harden code itself. When in doubt, it's NOT Codex — spend the quota deliberately on review.

## Test discipline — keep every test cycle cheap

When the task runs tests, **path-scope, always.** Run only the named test file — `pytest path/to/test_x.py -q` (add `-m "not slow and not gpu and not integration"` if the suite marks them) — and NEVER bare `pytest`, `pytest <dir>/`, or `pytest … -k <expr>`: those collect the whole test tree first (~30s vs ~1.7s for a named file — **~18× slower every cycle**). NEVER run `svelte-check`, `tsc --noEmit`, `npm run build`, or the full suite in an inner cycle. Confirm green once; don't re-run a passing test. (Codex is its own harness, so it can't read the meta-dev charter internally — this clause IS the rule for codex runs.)

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect from cwd; names from .claude/meta-dev-repos.json)
- `--readonly` — sandbox = `read-only` (audits / gap-checks / reviews — the common case)
- `--model <model>` — override codex model (default: codex's configured default for the account)
- `--sandbox <mode>` — `read-only` | `workspace-write` | `danger-full-access` (default `workspace-write`; `--readonly` forces `read-only`)
- `--timeout <ms>` — wall-clock timeout (default `600000` = 10 min)

Everything else is the task description. If none is given, ask what task to run.

## Step 2: Confirm the Plan

Summarize before running:
- **Backend:** Codex (`codex exec`)
- **Repo / Work dir:** (detected or specified)
- **Task:** (the task description)
- **Mode:** read-only (audit) or workspace-write (fixes)

If the task is destructive or writes outside the repo, confirm with the user first. For gap-checking/hardening, **default to `--readonly`** — Codex reports, you decide.

## Step 3: Execute

Run the headless worker. For tasks expected to take >30s, use `run_in_background: true` so the session stays responsive.

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/codex-headless-exec \
  ${REPO:+--repo "$REPO"} \
  ${MODEL:+--model "$MODEL"} \
  ${READONLY:+--readonly} \
  ${SANDBOX:+--sandbox "$SANDBOX"} \
  ${TIMEOUT:+--timeout "$TIMEOUT"} \
  -- <task description>
```

**Repo detection:** `--repo` wins; else infer from `pwd`; if ambiguous (in parent repo), ask which repo to target.

## Step 4: Report Results

The script distills the worker's output — three files per run:
- **`OUTPUT_FILE`** (printed as `OUTPUT_FILE=<path>`) — clean JSON: `{is_error, subtype, num_turns, duration_ms, session_id, result, usage, backend}`. `result` is Codex's final message. `json.load()` it directly.
- **`<OUTPUT_FILE>.raw`** — the full `codex exec --json` JSONL event stream (deep debugging).
- **`<OUTPUT_FILE>.stderr`** — the worker's stderr.

The script also prints the distilled `result` between `RESULT` rules, so for a foreground run you can read it straight from the command output.

When execution completes:
1. **Read `OUTPUT_FILE`** (or the printed `RESULT` block) — already clean JSON.
2. **Check `is_error`** and the `Exit code` line — exit `3` = distill failed (inspect `.raw`), exit `4` = worker reported error, exit `124` = timed out.
3. **Summarize** — what Codex found/did, files touched (if workspace-write), any issues.
4. **Apply / next steps** — for gap-checks, the value is the findings: triage them and apply fixes yourself or via a claude-harness worker. Remind the user Codex's changes (if any) are **not** auto-committed.

## Safety Notes

- Codex must be authenticated (`~/.codex/auth.json` — Codex Plus/Pro login or `OPENAI_API_KEY`). The script warns if auth is missing.
- `--readonly` runs Codex in its `read-only` sandbox — it can read + run read-only commands but cannot edit files. Use it for all audits/reviews.
- `workspace-write` lets Codex edit files in the work dir but not commit — review and commit yourself.
- Codex's changes are NOT automatically committed.
- **Mind the quota** — Codex Plus is a limited monthly budget. Prefer one well-scoped call over many; don't fan Codex out the way you'd fan out DeepSeek.
