---
name: meta-headless
description: Invoke headless worker skill — run a task in a dedicated subagent, report results
argument-hint: <task-description> [--model haiku|sonnet|opus]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: haiku
---

# /meta-headless

Dispatch a task to a headless worker subagent. Runs autonomously and reports results.

## Usage

- Accepts a task description as argument
- Optionally specify model tier: `--model haiku|sonnet|opus` (default: haiku for mechanical tasks)
- Worker gets full tool access and operates within standard constraints
- Reports: task summary, files touched, outcome, any issues found

Detail: skill `headless-worker` in `plugins/meta-dev/skills/headless-worker/`.
