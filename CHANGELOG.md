# Changelog

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
