# Canary Protocol — Post-Deploy Health Monitoring Loop

Observe a freshly deployed (or live) service for regressions, errors, and performance
degradation. Canary **observes and reports** — it never fixes during a run.

All project specifics (URLs, hostnames, service names, thresholds) are config-driven.
Read everything from `bash scripts/config-get.sh meta_dev.canary`.

---

## Config Surface

| Key | Meaning |
|-----|---------|
| `meta_dev.canary.default_target` | Target profile selected when no `<target>` arg is given |
| `meta_dev.canary.targets.<name>` | A named target profile (endpoints + ssh + ssl/dns) |
| `meta_dev.canary.targets.<name>.endpoints[]` | List of `{name, url, method, expected_status, latency_threshold_ms}` |
| `meta_dev.canary.targets.<name>.ssh` | `{host, services[]}` for log inspection (null = SSH disabled for this target) |
| `meta_dev.canary.targets.<name>.domains[]` | Domains for the SSL/DNS bookend check (empty = skip) |
| `meta_dev.canary.interval.divisor` | Interval = duration / divisor (default 10) |
| `meta_dev.canary.interval.min_seconds` | Floor on interval (default 30) |
| `meta_dev.canary.interval.max_seconds` | Ceiling on interval (default 120) |
| `meta_dev.canary.default_duration` | Duration used when no `<duration>` arg given |
| `meta_dev.canary.baseline.enabled` | Capture a baseline before the loop |
| `meta_dev.canary.baseline.latency_multiplier` | Regression trip point = baseline × this (default 2.0) |
| `meta_dev.canary.escalation.strike_count` | Consecutive failures before ALERT+stop (default 3) |
| `meta_dev.canary.errors.warn_threshold` / `fail_threshold` | Error-log counts per interval |
| `meta_dev.canary.ssl_dns.enabled` | Run the SSL/DNS bookend check |
| `meta_dev.canary.ssl_dns.cert_expiry_warn_days` | Cert-expiry warning window (default 7) |

Resolve the active target: use `<target>` arg if present, else `default_target`.

---

## Step 0: Parse Arguments

Argument string: `$ARGUMENTS`

- **`<target>`** — name of a target profile (e.g. a repo or environment). Defaults to
  `meta_dev.canary.default_target`. If the name is not a known profile, report the
  available profiles and exit.
- **`<duration>`** — `10m`, `30m`, `1h`, etc. Defaults to `meta_dev.canary.default_duration`.
- **`--verbose`** — show every check result each cycle, not just failures.

Order-independent: the duration token is the one matching `^\d+[smh]$`; the remaining
non-flag token is the target.

## Step 0.5: Read Learned Patterns

Read the `## Learned Patterns` section at the bottom of THIS file. Each pattern is a
generalized rule discovered from past monitoring sessions. Apply them as additional
checks or failure signatures to watch for. Honor each pattern's `Applies to:` field.
Record which patterns were active in the final report.

## Step 1: Initialize Monitoring

1. **Resolve target profile** from config (`meta_dev.canary.targets.<active>`).
2. **Compute interval:** `duration / interval.divisor`, clamped to
   `[interval.min_seconds, interval.max_seconds]`.
3. **Total cycles:** `floor(duration_seconds / interval_seconds)`.
4. **Emit initialization summary:**

```
Canary monitoring started
Target: {target}
Duration: {duration}
Interval: {interval} seconds  ({cycles} cycles)
Checks: health, key flows, errors, latency, ssl/dns
Started: {timestamp}   Ends: {timestamp}
Verbose: {yes/no}
```

## Step 2: Capture Baseline

Skip if `baseline.enabled` is false. Otherwise, before the loop, sample every endpoint
once and record `{http_code, latency}`. These become the reference for **relative**
regression detection — regressions are measured against baseline, not fixed thresholds.

```bash
# Per endpoint
curl -s -o /dev/null -w "%{http_code} %{time_total}" --max-time 10 {URL}
```

Also snapshot the error-log baseline if SSH is configured (see Step 3, Check 3).
Record `baseline_latency[endpoint]` and `baseline_errors`.

## Step 3: Monitoring Loop

At each interval, run all checks (in parallel where possible).

### Check 1 — Health & Latency (per endpoint)
```bash
RESULT=$(curl -s -o /dev/null -w "%{http_code} %{time_total}" --max-time 10 {URL})
```
- **Status check:** HTTP code must equal the endpoint's `expected_status`.
- **Latency check (relative):** FAIL if `latency > baseline_latency × baseline.latency_multiplier`.
  When no baseline (disabled), fall back to the endpoint's absolute `latency_threshold_ms`.
- A `curl --max-time 10` timeout (no response) is a **failure**, never "still loading."

### Check 2 — Key Flows
Endpoints whose `name` denotes a flow (auth/feed/page) are validated against their
declared `method` + `expected_status` (e.g. `200` for pages, `4xx` for auth endpoints
hit without credentials).

### Check 3 — Error Rates (SSH log inspection)
Only if `targets.<active>.ssh` is non-null. For each service:
```bash
ssh root@{ssh.host} "journalctl -u {service} --since '{INTERVAL} seconds ago' --no-pager 2>/dev/null \
  | grep -c '500\|ERROR\|Traceback'" 2>/dev/null || echo "SSH unavailable"
```
- `SSH unavailable` → record as a non-fatal skip (not a failure); note it in the report.
- Errors in interval: `> errors.warn_threshold` → WARNING; `> errors.fail_threshold` → FAIL.

### Check 4 — SSL / DNS (bookend: first and last cycle ONLY)
Skip if `ssl_dns.enabled` is false or the target has no `domains[]`. For each domain:
```bash
echo | openssl s_client -connect {domain}:443 -servername {domain} 2>/dev/null \
  | openssl x509 -noout -dates 2>/dev/null
dig +short {domain}
```
- FAIL if cert expires within `ssl_dns.cert_expiry_warn_days`.
- FAIL if DNS returns no record.
- (Optional) the deploying command may also assert an HSTS response header on the
  health endpoint as part of this check.

## Step 4: Real-Time Status & Escalation

### Normal mode
Emit only WARNING/FAIL checks. If all pass:
```
[HH:MM:SS] Canary {N}/{TOTAL} — {TARGET} — ALL CLEAR
```

### Verbose mode (`--verbose`)
```
[HH:MM:SS] Canary check {N}/{TOTAL} — {TARGET}

| Check    | Result | Value      | Threshold        | Status |
|----------|--------|------------|------------------|--------|
| Health   | 200    | 45ms       | 2×baseline (90ms)| PASS   |
| Key flow | 200    | —          | 200              | PASS   |
| Errors   | 0      | 0/interval | <{fail}          | PASS   |
| Latency  | 45ms   | —          | <2×baseline      | PASS   |
| SSL      | valid  | 83 days    | >7 days          | PASS   |

Overall: ALL CLEAR
```

### Escalation Ladder (strike count from config, default 3)

| Consecutive failures | Action |
|----------------------|--------|
| 1 | Log WARNING, continue |
| 2 | Log ELEVATED warning, continue |
| `strike_count` (3) | **ALERT** — stop monitoring, emit alert report |

A passing cycle resets the strike counter to 0. Track `last_success` and `first_failure`
timestamps across cycles.

**On ALERT:**
```markdown
## CANARY ALERT — {TARGET}

{strike_count} consecutive check failures detected.

| Check    | Status | Details                |
|----------|--------|------------------------|
| Health   | FAIL   | {HTTP code, latency}   |
| Key flow | FAIL   | {HTTP code}            |
| Errors   | FAIL   | {error count}          |

Last successful check: {timestamp}
First failure:         {timestamp}

Recommended actions:
1. Inspect logs: ssh root@{ssh.host} "journalctl -u {service} -n 50 --no-pager"
2. Verify database / dependency connectivity
3. Review the most recent deploy for breaking changes
4. Roll back if the issue persists
```

## Step 5: Final Monitoring Report

At end of duration (or on ALERT / early termination):

````markdown
# /meta-canary Report — {TARGET}

**Date:** {YYYY-MM-DD}
**Duration:** {actual monitoring time}
**Checks:** {N} total, {pass} passed, {fail} failed
**Patterns active:** {LP-NNN... or "none"}
**Verdict:** HEALTHY / DEGRADED / UNHEALTHY

## Results
| Check            | Passes | Warnings | Failures | Status      |
|------------------|--------|----------|----------|-------------|
| Health endpoints | N      | N        | N        | OK/WARN/FAIL|
| Key flows        | N      | N        | N        | OK/WARN/FAIL|
| Error rates      | N      | N        | N        | OK/WARN/FAIL|
| Latency          | N      | N        | N        | OK/WARN/FAIL|
| SSL/DNS          | N      | N        | N        | OK/WARN/FAIL|

## Timeline
| Time  | Health     | Key Flow | Errors | Latency | Status |
|-------|------------|----------|--------|---------|--------|
| HH:MM | 200 (45ms) | 200      | 0      | 45ms    | OK     |
| ...   | ...        | ...      | ...    | ...     | ...    |

## Performance
- Avg latency: {X}ms (baseline: {Y}ms)
- Max latency: {X}ms
- P95 latency: {X}ms
- Error count: {N} total

## Alerts Triggered
{3-strike alerts with timestamps, or "No alerts triggered"}

## Verdict
- HEALTHY: All checks passed, no regressions vs baseline.
- DEGRADED: Some checks failed but recovered. Monitor closely.
- UNHEALTHY: Persistent failures detected. Action required.
````

**If invoked by a deploy/ship pipeline:** fold the report into the ship completion
summary rather than writing a separate file. **If standalone:** output to conversation.

## Step 6: Pattern Detection & Upstream Improvement (patches meta-ship)

Skip if first canary run (no past data) or all checks passed.

1. **Classify failures** from this run and compare against past canary alerts/reports.
2. **Pattern matching** — if the same failure type appears in **3+ separate** monitoring
   sessions, derive an upstream rule. Examples:
   - "Health endpoint timeout after migration" → meta-ship: "Pre-deploy must run a migration health check."
   - "SSL cert warning" → meta-ship: "Pre-deploy must verify cert has >30 days validity."
   - "Error spike in first 2 minutes then recovery" → meta-ship: "Post-deploy must wait 2 minutes before marking healthy."
3. **Patch meta-ship:**
   a. Open `commands/meta-ship.md`.
   b. Find its `## Learned Patterns` section.
   c. Check for semantic duplicates.
   d. Append a new `LP-NNN` entry with **Source:** `meta-canary`.
   (Commit per the host command's discipline — this reference does not run git itself.)

**Constraints:** 3+ separate sessions; generalized only; max 1 pattern added per session.

## Operational Rules

1. **Never fix during monitoring.** Canary observes and reports; fixing is a separate action.
2. **Escalation is non-negotiable.** `strike_count` consecutive failures = immediate ALERT + stop.
3. **Baseline-relative.** When a baseline exists, regressions are relative to it, not absolute.
4. **Don't spam endpoints.** Honor `interval.min_seconds` (≥30s) — these may be production systems.
5. **SSL/DNS is bookend-only.** First and last cycle; it doesn't change between cycles.
6. **Timeout everything.** `curl --max-time 10` on every request; a hang is a failure.
7. **SSH is best-effort.** "SSH unavailable" degrades gracefully — note it, don't fail the run.

---

## Learned Patterns

<!-- Auto-maintained by the improvement loop. Generalized only — no project-specific entries. -->
<!-- Max 20 patterns. meta-audit enforces the cap via consolidation. -->
<!-- meta-canary detects recurring post-deploy failures and patches meta-ship (Step 6). -->
<!-- Only meta-audit may remove patterns; all other commands are append-only. -->
