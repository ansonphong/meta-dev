# Clearing Strategies

Strategies for auto-clearing inbox items. Configured per source in `dispatch-table.md`.

## Strategies

### manual
Items stay open until explicitly resolved by user via `/meta-inbox resolve <id>`.
Default for advisory items and structural concerns. Never auto-close.

### auto-resolve
Items auto-close after fix-agent commits the resolution. Default for trivial and
low-severity auto_clearable items. Commit per standing auth (#1 RULE).

### age-based
Auto-archive items older than configured `max_age_days`. Purges stale context.
Used for sweep_anomaly and low-priority items that have not been updated.

### tag-based
Items routed by source tag to specific handlers in `dispatch-table.md`. Each
handler defines its own clearing strategy per source type.

## Selection Priority

| Strategy | When | Item Types |
|----------|------|------------|
| auto-resolve | fix-agent completed, all checks pass | trivial/low auto_clearable issues |
| manual | needs human green-light | advisories, structural fixes, money/auth items |
| age-based | item > N days old with no updates | sweep anomalies, stale repair dossiers |
| tag-based | dispatch-table has handler for source | overlord_finding, review_failure |

## Failure Fallback

If auto-resolve fails on an issue item: keep item open, stamp `clear_attempted`
timestamp. On item seeing 3 consecutive failures across >=3 attempts: convert to
advisory, surface to user (per repair-loop exhaustion protocol).
