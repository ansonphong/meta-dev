---
name: headless-dispatch
description: "Dispatch a Claude Code headless worker from a non-Claude harness such as Codex or Grok. Covers backend selection across fable, opus, sonnet, deep and glm, the ambient-login versus API-key split, and the sandbox network precondition. Use when asked to run fable-execute, opus-execute, deep-execute, glm-execute or sonnet-execute, or to hand a task to a Claude model from Codex."
allowed-tools: [Read, Bash, Glob, Grep]
---

# headless-dispatch — spawn a Claude worker from Codex

`claude-headless-exec` is a plain bash script. You have a shell, so you can run
it. The worker is a full Claude Code instance, so unlike you it CAN run our
slash commands internally.

## Precondition — check this first, once per session

    curl -s -o /dev/null -w "%{http_code}" --max-time 10 https://api.anthropic.com/v1/models

`000` means your sandbox blocks DNS and every worker will die at `rc=6`. Fix:
`[sandbox_workspace_write] network_access = true` in `~/.codex/config.toml`,
then restart Codex. Do not attempt to work around it.

## Pick a backend

| Backend | Model | Auth | Reach for it when |
|---|---|---|---|
| `fable` | Fable 5 | ambient `~/.claude` — **no key** | hardest tasks, extreme reasoning, long-horizon coherence |
| `opus` | Opus 4.8 (200K) | ambient — **no key** | top-tier judgment: architecture, security, review verdicts |
| `sonnet` | Sonnet 5 (200K) | ambient — **no key** | solid Anthropic judgment, cheaper than Opus |
| `deep` | DeepSeek V4-Pro | `DEEPSEEK_API_KEY` | cheap bulk mechanical work |
| `glm` | GLM 5.2 | `GLM_API_KEY` | stateful / long-horizon / plan-writing |

The three ambient backends are pinned to the 200K tier with no `[1m]` suffix, so
they are never billed at the 1M rate.

## Invoke

    bash <plugin-root>/scripts/claude-headless-exec \
      --backend opus \
      --repo app \
      --effort high \
      '<complete, self-contained task spec with acceptance criteria>'

`--backend` is REQUIRED — the script refuses to guess. Run with `--help` for the
full flag list. The worker shares no context with you: give it a complete spec
and demand a distilled return.

## Rules

1. **Verify what comes back.** You remain accountable for the result.
2. **One backend per task.** Do not fan the same task across tiers hoping one sticks.
3. **A worker can run our slash commands; you cannot.** "Run `/loop-gap` on X" is a
   valid task for it and an invalid one for you.
4. **Never hand a worker conductor duties** — checkbox flips, phase-gate review,
   dashboards. Those are yours, via planctl.
