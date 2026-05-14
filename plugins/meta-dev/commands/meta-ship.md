---
name: meta-ship
description: Unified release pipeline — chains build, test, deploy, and verify steps with gates between each stage
argument-hint: [--dry-run] [--skip-canary]
allowed-tools: [Read, Write, Bash, Grep, Agent]
model: sonnet
---

# /meta-ship

Release pipeline: pre-flight → deploy → health check → canary monitoring.

## Steps

1. Pre-flight: git health, backend tests, frontend tests, build test
2. Deploy: push to remote, rsync build, restart services (delegates to deploy skill)
3. Post-deploy verification: health endpoints, SSL, key user flows
4. Canary: invokes `/meta-canary` for 10-min monitoring (unless `--skip-canary`)
5. Ship log: invoke Skill `changelog-engine` (cut period) + Skill `version-manager` (bump version), then commit deploy record

Config: `plans/_dashboard/settings.json` + `plans/_dashboard/versioning.json`.
