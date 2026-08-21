---
name: task-agent
description: "Alias of /meta-task-agent — identical command (pure redirect: `Execute /meta-task-agent $ARGUMENTS`). /task-agent and /meta-task-agent are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: [<task> | --status | --end | --cancel TA-n] [--batch] [--readonly] [--serial]
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---
Execute /meta-task-agent $ARGUMENTS
