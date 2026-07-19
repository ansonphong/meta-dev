---
name: probe
description: "Alias of /meta-probe — identical command (pure redirect: `Execute /meta-probe $ARGUMENTS`). /probe and /meta-probe are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: <issue | file:line | "question"> [--budget low|medium|high|insane] [--background]
allowed-tools: [Skill, Read, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---
Execute /meta-probe $ARGUMENTS
