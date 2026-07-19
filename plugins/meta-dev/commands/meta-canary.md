---
name: meta-canary
description: Post-deploy health monitor — runs continuous checks after deployment, alerts on failures, patches meta-ship with recurring issues
argument-hint: "[<target>] [<duration>] [--verbose]"
allowed-tools: [Read, Edit, Bash, Grep]
model: opus
---

# /meta-canary

Post-deploy health monitoring loop. Watches a deployed (or live) service for errors,
latency regressions, and failed flows — observes and reports, never fixes mid-run.

Full runbook: `references/canary-protocol.md`. All endpoints, hosts, services, and
thresholds are config-driven — read from `bash scripts/config-get.sh meta_dev.canary`.

## Arguments

- **`<target>`** — name of a target profile (`meta_dev.canary.targets.<name>`). Defaults
  to `meta_dev.canary.default_target`. Unknown name → list profiles and exit.
- **`<duration>`** — `10m`, `30m`, `1h` (default: `meta_dev.canary.default_duration`).
- **`--verbose`** — show every check each cycle, not just WARNING/FAIL.

```
/meta-canary                 # default target, default duration
/meta-canary www             # named target profile
/meta-canary www 30m         # target + duration
/meta-canary 5m              # default target, 5 minutes
/meta-canary www --verbose   # show all check results
```

## Flow (see `references/canary-protocol.md`)

0. **Parse args** (Step 0) + **read own Learned Patterns** (Step 0.5).
1. **Initialize** — resolve target profile; interval = `duration / interval.divisor`,
   clamped to `[interval.min_seconds, interval.max_seconds]`.
2. **Baseline** — sample every endpoint once (if `baseline.enabled`). Regressions are
   measured **relative** to baseline (`latency > baseline × baseline.latency_multiplier`).
3. **Loop** every interval: health+latency, key flows, SSH error-log inspection
   (graceful "SSH unavailable" fallback), SSL/DNS bookend (first+last cycle only).
4. **Escalate** — `escalation.strike_count` consecutive failures (default 3) →
   `1=warn · 2=elevated · 3=ALERT+stop` with a structured CANARY ALERT report.
5. **Final report** — HEALTHY / DEGRADED / UNHEALTHY verdict with results, timeline,
   and avg/max/P95 latency.
6. **Pattern detection** — recurring failures (3+ sessions) patch `commands/meta-ship.md`
   Learned Patterns. Makes the "patches meta-ship" frontmatter claim real.

## Rules

Never fix during monitoring · min 30s interval · `curl --max-time 10` (hang = failure) ·
SSL/DNS bookend-only · baseline-relative regressions. See protocol Operational Rules.

When chained by a deploy pipeline, fold the report into the ship summary; standalone,
output to conversation.
