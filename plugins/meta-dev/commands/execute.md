---
name: execute
description: Shortcut for /meta-execute — Subagent-driven plan execution, one fresh Sonnet per task, verify+commit+push
argument-hint: <plan-path> [--inline] [--deploy] [--pause-before=<task-id>]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /execute → /meta-execute

Execute `/meta-execute $ARGUMENTS`.
