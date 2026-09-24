# Changelog

## 1.5.10

- Spell out `/cursor-execute` Grok 4.7 500k contract on the skill card: no `--list-models` row, `reasoning_effort` parameterized id, `--fast` is speed, `--budget` fills effort when `--effort` is omitted, worker self-report is 524288.

## 1.5.9

- Cursor Grok 4.7 `--context 500k` now sends `reasoning_effort` in the parameterized id, which `cursor-agent` accepts. Informal `--grok 4.7 500K` and `--context 500K` resolve the same way.

## 1.5.8

- Add chooser notes to `/codex-execute`, `/grok-execute`, and `/opus-execute` for GPT-6 Astra, Sol, the terra role, Luna, Grok 4.7/4.6/4.5, and Opus 5.5.
- Accept Cursor `--grok 4.7` as `grok-4.7-<effort>`. Unspecified defaults stay Composer 2.5 and `cursor-grok-4.6-high`.
- Add `--context 500k` for Cursor Grok 4.7. Omit it and the run stays the 256k id.
- Release matching Claude and Codex plugin manifests at version 1.5.8.

## 1.5.7

- Point `/codex-execute` at published GPT-6 ids: astra `gpt-6-astra` high, sol `gpt-6-sol` high, terra and the no-tier fallback `gpt-6-sol` medium, luna `gpt-6-luna` low. The Codex catalog has no `gpt-6-terra`. Spark stays `gpt-5.3-codex-spark`.
- Point `/opus-execute` default and its nested Opus pin at `claude-opus-5-5`. An explicit `--model` is forwarded unchanged.
- Point `/grok-execute` default at `grok-4.7`. `--model` accepts `grok-4.7`, `grok-4.6`, and `grok-4.5`. `grok-4.7` uses the `grok-4.6` effort menu.
- Release matching Claude and Codex plugin manifests at version 1.5.7.

## 1.5.6

- Add a Jev System One decide client and `/jev-execute`. Missing key fails open. Risk tags still force a high budget.
- Release matching Claude and Codex plugin manifests at version 1.5.6.

## 1.5.5

- Require a feature folder for v1.1 plans: `plans/<repo>/<feature>/YYYY-MM-DD-<slug>.md`.
- Keep plan-attached artifacts inside that folder; do not dump dated files at the repo-bucket root.
- Release matching Claude and Codex plugin manifests at version 1.5.5.

## 1.5.4

- Harden `/cursor-execute` output-contract handling, including valid failure JSON.
- Write Cursor prompt, raw, stderr, and result artifacts owner-only (`0600`).
- Enforce true Cursor read-only execution with `--mode ask`; release manifests match 1.5.4.

## 1.5.3

- Add `/cursor-execute` — headless Cursor Agent worker (`cursor-agent --print --output-format json`).
- Named-only. Default stays on the Cursor Models pool (Composer 2.5 200k, Cursor Grok 4.6/4.5 256k). `--grok 4.6 xhigh` routes to `cursor-grok-4.6-xhigh`.
- Other Models (`--opus` / `--sol` / `--sonnet` / `--luna` / `--fable` / `--codex` / `--model`) stay opt-in.
- Release matching Claude and Codex plugin manifests at version 1.5.3.

## 1.5.2

- Raise headless worker walls to low 30 min / medium 90 min / high 180 min so 30+ minute DeepSeek, Codex, Grok, Opus, and Fable jobs are not cut off.
- Parse `--timeout` as `30m` / `2h` / `1800s` / ms; bare numbers under 1000 are seconds, not milliseconds.
- Ignore host bash/spawn timeouts (5s–5min in ms) accidentally forwarded as `--timeout`.
- Stall watchdog default is max(20 min, wall/4) instead of 5 minutes of silence.
- Claude-family runners now wrap `timeout(1)` and raise `BASH_DEFAULT_TIMEOUT_MS` to the worker wall.
- Execute skills require `background: true` and host `timeout: 0` (Grok) so the wrapper does not SIGKILL a healthy worker.
- Release matching Claude and Codex plugin manifests at version 1.5.2.

## 1.5.1

- Default `/deep-execute` / `claude-headless-exec --backend deep` to `deepseek-v4-flash` (V4.1 Flash as of 2026-09-10); `--pro` upgrades; `--vision` unchanged.
- Do not pin the preview ID `deepseek-v4.1-flash-expires-on-0910`.
- Release matching Claude and Codex plugin manifests at version 1.5.1.

## 1.5.0

- Release adaptive project-neutral workflows.
- Release matching Claude and Codex plugin manifests at version 1.5.0.

## 1.4.33

- Keep successful Stop-hook reconciliation silent so Codex does not append the full plan-decision list to every response.
- Preserve the concise warning when reconciliation fails.
- Release matching Claude and Codex plugin manifests at version 1.4.33.

## 1.4.32

- Scan the project initializer as live doctrine instead of a whole-script exemption; its migration-detection constructs stay permitted compatibility logic.
- Release matching Claude and Codex plugin manifests at version 1.4.32.

## 1.4.31

- Stop native Codex commands from recursively selecting sibling workflows from stage names or section headings.
- Keep ordinary Codex Stage 6 completion to one native review unless the user explicitly requests cross-family review or full evaluation.
- Release matching Claude and Codex plugin manifests at version 1.4.31.

## 1.4.30

- Make live harness instructions portable through the AGENTS-first host project contract.
- Release matching Claude and Codex plugin manifests at version 1.4.30.
