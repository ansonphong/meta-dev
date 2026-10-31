# Changelog

## 1.5.28

- Remove the meta-goal 1000-character budget. Goal prompts include every
  sharpened item in full. Do not shorten or drop items to fit a length.
- Align both plugin manifests at version 1.5.28.

## 1.5.27

- Give DeepSeek workers a concise task contract covering objective, context,
  ownership, constraints, focused acceptance and evidence, with a short example.
- Preserve coherent task ownership and independent review; adapt assignment scope
  from observed results rather than fixed model-specific limits.
- Align both plugin manifests at version 1.5.27.

## 1.5.26

- Default DeepSeek workers to `deepseek-flash` (V4.1 Flash 1017) with explicit
  Max reasoning and thinking enabled; preserve Max under every execution budget.
- Honor explicit effort overrides and clear inherited thinking-token limits so
  `MAX_THINKING_TOKENS=0` cannot disable DeepSeek thinking.
- Refresh deep-execute guidance with official effort mappings, canonical and
  legacy model IDs, multimodal Flash support, dated benchmark evidence and
  verification limits. Keep `--vision` as a Flash compatibility flag.
- Verify launch environment/settings with a local stub and align both plugin
  manifests at version 1.5.26.

## 1.5.25

- Label the main Codex workflow `meta-dev` so `$me` matches its display name
  directly and `$meta-dev` matches exactly, ahead of namespace-only matches.
- Drop redundant Meta prefixes from other menu labels so the main workflow is
  the sole display-name prefix match for `$me`; keep Execute Plan distinct.
- Keep other command labels distinct and align manifests at version 1.5.25.

## 1.5.24

- Disable automatic legacy command migration in the Codex manifest; native
  skills already cover the commands, so generated `source-command-*` duplicates
  no longer pollute discovery. Preserve the Claude command surface.
- Reject migrated duplicates in the real Codex package ingestion check.
- Align both plugin manifests at version 1.5.24.

## 1.5.23

- Allow supporting research during brainstorming and every other stage in the
  subject directory's shared `research/` subfolder, linked from stage artifacts.
- Keep required stage deliverables and ceilings; hardening checks supporting
  research for stale or contradictory findings.
- Align both plugin manifests at version 1.5.23.

## 1.5.22

- Require Stage 1 `brainstorm.md`, Stage 2 `design.md` (plus optional supporting
  files), and Stage 3 `00-master-plan.md`; invoke meta-planner when applicable,
  otherwise use a one-page master plan. Honor explicit user overrides.
- Stop brainstorm/design requests at their named stages, with no early master
  plan for bookkeeping. Stage 4 edits and hardens all preceding artifacts.
- Align both plugin manifests at version 1.5.22.

## 1.5.19

- Keep six stage outcomes in one shared contract; let native harnesses choose
  methods and share one short record for bounded work.
- Remove automatic specialist skill/command chains, forced plan artifacts,
  context-watchdog calls and execution ceremony from the normal path.
- Shorten the actual worker preamble while preserving completion ownership,
  whole-task acceptance, configured budgets, permissions and independent review.
- Keep both plugin manifests aligned at version 1.5.19.

## 1.5.18

- Keep one implementation owner through ordinary repairs, whole-task acceptance,
  focused verification and exact-path commits under the existing scoped go.
- Replace conflicting repair-pass/parking rules with shared bounded diagnosis
  and escalation; retain real resource, permission and independent review gates.
- Shorten injected worker instructions and reject narrow green completion claims
  when declared callers, fixtures or other requirements remain unfinished.
- Keep Claude and Codex plugin manifests aligned at version 1.5.18.

## 1.5.15

- Make OVERLORD supervise truthful, efficient delivery, while retaining plan reconciliation, completed-task reviews, authorized repairs, dashboard, and inbox duties.
- Default to a task-aware 10-minute cadence with configurable intervals and host-native reviewers; require a real scheduler or session-bound native monitor, bounded reviews, and no overlap.
- Retain review evidence and corrections, escalate repeated drift/stalls, and ignore callbacks from replaced or stopped watches.
- Keep Claude and Codex plugin manifests aligned at version 1.5.15.

## 1.5.13

- Trace bounded integration joins before edits; verify valid and relevant refusal behavior while preserving per-task acceptance, causal repair limits, and independent ready work.
- Require complete, evidence-backed review findings and validate structured results before routing; retain unaffected evidence and explain any expansion after repairs.
- Report critical paths and repeated overhead, batch bookkeeping at useful seams, and stop reprobes of unchanged unavailable delegates.
- Keep Claude and Codex plugin manifests aligned at version 1.5.13.

## 1.5.12

- Complete the declared review scope and report all evidence-backed findings before remediation; collect and deduplicate commissioned reviewers' findings before edits.
- Batch accepted fixes, carry unresolved findings forward, and limit follow-up review to repairs and affected integration seams unless changes invalidate broader coverage.
- Keep Claude and Codex plugin manifests aligned at version 1.5.12.

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
