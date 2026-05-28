#!/usr/bin/env bash
set -euo pipefail
# risk-tag.sh — Deterministic risk classification from task text
# Usage: echo "$task_body" | bash scripts/risk-tag.sh
# Output: one or more tags (comma-separated), or "none"

TEXT=$(cat)
TAGS=""

# Word-boundary helper: \b plus underscore (common in code identifiers like validate_license)
B='(\b|_)'

# schema-drift: migrations, schema changes, alembic, postgres DDL
if echo "$TEXT" | grep -qiE "${B}(migration|alembic|schema|postgres|ALTER TABLE|CREATE TABLE|DROP TABLE|ddl)${B}"; then
  TAGS="${TAGS}schema-drift,"
fi

# security-boundary: auth, license, permission, ed25519, tokens
if echo "$TEXT" | grep -qiE "${B}(permission|license|ed25519|gallery-token|auth|jwt|api\.key|secret|private\.key)${B}"; then
  TAGS="${TAGS}security-boundary,"
fi

# release-stability: release manifest, version strings, signatures
if echo "$TEXT" | grep -qiE "${B}(release\.json|version\.manifest|ed25519\.signature|version\.string|release\.channel)${B}"; then
  TAGS="${TAGS}release-stability,"
fi

# money-path: payments, stripe, refunds, subscriptions
if echo "$TEXT" | grep -qiE "${B}(webhook|payment|stripe|refund|subscription|invoice|billing|checkout)${B}"; then
  TAGS="${TAGS}money-path,"
fi

# perf/cache: redis, celery, cache, pipeline
if echo "$TEXT" | grep -qiE "${B}(cache|redis|celery|pipeline|image\.processing|async\.queue)${B}"; then
  TAGS="${TAGS}perf/cache,"
fi

# Output
if [ -z "$TAGS" ]; then
  echo "none"
else
  echo "${TAGS%,}"
fi
