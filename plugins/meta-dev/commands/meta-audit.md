---
name: meta-audit
description: Harness simplification audit — tests whether pipeline components are still load-bearing or have become overhead
argument-hint: [full | component:<name>] [--compare] [--force-full]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-audit

Pipeline health audit. Periodically tests whether pipeline components are still load-bearing or have become overhead.

## Flow

1. **Component inventory** — per `references/audit-protocol.md`
2. **Assumption extraction** — what does each component assume?
3. **Evidence collection** — read code, run components, check git log, check callers
4. **Classification** — load-bearing / insurance / overhead / migrating
5. **Pattern Ecosystem Review** — the ONLY command that can prune learned patterns (cap 20, check contradictions, staleness, overlap)
6. **Report** — per audit-protocol.md template

Config: `bash scripts/config-get.sh` for paths section.
