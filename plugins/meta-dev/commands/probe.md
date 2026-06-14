---
name: probe
description: Shortcut for /meta-probe — exhaustive deep-investigation probe with LLM bias-loop breaking
argument-hint: <issue | file:line | "question"> [--budget low|medium|high|insane] [--background]
allowed-tools: [Read, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---

# /probe → /meta-probe

Execute `/meta-probe $ARGUMENTS`.
