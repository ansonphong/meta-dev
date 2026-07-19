---
name: execute
description: "Alias of /meta-execute — identical command (pure redirect: `Execute /meta-execute $ARGUMENTS`). /execute and /meta-execute are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: <plan-path> [--inline] [--strict] [--deploy] [--pause-before=<task-id>]
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---
Execute /meta-execute $ARGUMENTS
