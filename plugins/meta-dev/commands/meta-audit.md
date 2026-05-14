---
name: meta-audit
description: Harness simplification audit — tests whether pipeline components are still load-bearing or have become overhead
argument-hint: [full | component:<name>] [--compare] [--force-full]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-audit

Harness component audit. Tests assumptions, classifies components as load-bearing/insurance/overhead/migrating.

## Pipeline

1. Component inventory — list every pipeline component and its assumption
2. Evidence collection — read recent execution artifacts, quantify value
3. Classification — load-bearing / insurance / overhead / migrating
4. Recommendations — keep, simplify, or remove each component
5. Pattern ecosystem review — read all commands' Learned Patterns, detect stale/contradictory/over-cap patterns. meta-audit is the ONLY command authorized to remove patterns.
6. Apply changes (with confirmation)

Output: `plans/meta/audit-{date}.md`.

Lazy-load via `.claude/cache/learned-patterns-index.json` + `.claude/cache/last-audit.json`.
