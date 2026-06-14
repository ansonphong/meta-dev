---
name: meta-overlord
description: Event-driven execution overseer for plan phases — polls state, renders dashboard, dispatches review agent per completed task, auto-fixes drift within threshold
argument-hint: [--event-driven|--tick <seconds>]
allowed-tools: [Read, Bash(bash:*), Bash(python3:*), Agent]
model: opus
---

# /meta-overlord

Overlord watches plan execution, renders dashboard, dispatches review-agent per completed task, auto-fixes drift within configurable threshold.

## Modes

- **`--event-driven` (default):** Reads latest `plan_edit` events from state (`events.jsonl` tail). On match against `overlord.watching`, triggers review cycle. No loop.
- **`--tick <seconds>`:** Polls git log + state on interval (min 30s, max 3600s). Rearms via `ScheduleWakeup`. For headless / CI.

## Per-Tick Procedure

1. Detect delta — `state-read.sh` events, `git log` since last tick
2. Map commits to tasks — match messages to master-plan.md task IDs
3. Request review — dispatch review-agent per completed task (model: sonnet)
4. Classify gaps — diff task checkboxes between plan and git state
5. Auto-fix within threshold — drift ≤ `auto_fix_threshold` (default 2) → auto-repair; > threshold → flag findings
6. Render dashboard — pipe state JSON through `overlord-render.py`
7. Persist — `state-append.sh overlord.last_tick`
8. Findings to inbox — via `inbox-add.sh` with tag `overlord`

State keys: `overlord.watching`, `overlord.last_tick`, `overlord.auto_fix_threshold`, `overlord.max_ticks`

## Exit Conditions

Stops when: all phases done + no findings, `--stop` passed, max ticks exceeded (100), or SIGINT/SIGTERM.

Integration: Hook → State (`on-edit.sh` → `state-append.sh` `plan_edit`), Overlord → Inbox (`inbox-add.sh`), Overlord → Dashboard (`overlord-render.py`), ScheduleWakeup rearm (tick mode only).
