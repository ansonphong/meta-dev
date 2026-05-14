---
name: meta-canary
description: Post-deploy health monitor — runs continuous checks after deployment, alerts on failures, patches meta-ship with recurring issues
argument-hint: [<duration>] [--verbose]
allowed-tools: [Read, Write, Bash, Grep]
model: haiku
---

# /meta-canary

Post-deploy monitoring loop. Checks health endpoints, error rates, latency, SSL, key user flows.

## Checks (every 60s)

1. Health endpoints (backend API + frontend) — 200 within 5s
2. Error rates — 0 per minute threshold, >5 = FAIL
3. Response latency — API < 200ms, frontend < 2s
4. SSL/DNS — HSTS header, cert not expiring within 7 days
5. Key user flows — auth + feed endpoints

**3-strike rule:** any check fails 3 consecutive times → alert with remediation guidance.

Default duration: 10m. Custom: `/meta-canary 30m`.

Output: monitoring report with pass/warn/fail per check.
