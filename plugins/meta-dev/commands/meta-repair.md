---
name: meta-repair
description: Invoke repair-loop skill — diagnose a failure, propose smallest fix, iterate until passing
argument-hint: <failure-description-or-path-to-failure-log>
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-repair

Diagnose + fix loop. Invokes `repair-loop` skill which:

1. Reads failure output (test trace, compile error, runtime stack)
2. Delegates to `failure-analyst` agent for root cause + smallest fix
3. Applies fix
4. Runs verification
5. If still failing → re-analyze, iterate (max 3 cycles)

Uses `failure-analyst` agent (`agents/failure-analyst.md`) for root-cause analysis.

Detail: skill `repair-loop` in `plugins/meta-dev/skills/repair-loop/`.
