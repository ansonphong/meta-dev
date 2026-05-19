---
name: repair
description: Shortcut for /meta-repair — Automated repair loop, diagnose failure, propose smallest fix, iterate until passing (3-attempt cap)
argument-hint: <failure-output | plan-path>
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /repair → /meta-repair

Execute `/meta-repair $ARGUMENTS`.
