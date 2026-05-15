---
name: headless-worker
description: Patterns for headless Claude execution via claude -p --output-format json. Tool allowlist tiers, env inheritance, model override for Sonnet routing.
---

# Headless Worker

Execute structured tasks via `claude -p` in headless mode. Useful for batch processing, CI/CD, and cron-driven automation.

## Patterns

```bash
# Single prompt, JSON output
claude -p "analyze this diff: $(git diff)" --output-format json

# With tool access (read-only by default)
claude -p "check test results in /tmp/test-output.log" \
  --allowedTools Bash --output-format json

# Model override for Sonnet
claude -p "complex architectural review" --model claude-sonnet-4-6
```

## Tool Allowlist Tiers

See `references/tool-allowlists.md` for tier definitions.

| Tier | Bash | Read, Write, Edit | Git |
|------|------|-------------------|-----|
| 1 — read-only | yes (safe commands) | Read only | no |
| 2 — read+write | yes | Read + Write + Edit | no |
| 3 — full | yes | all | yes |

Default: Tier 1.

## Environment

See `references/backend-env.md` for routing matrix.

- Child `claude -p` inherits `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` from parent
- Do NOT use `env -i` — it strips inherited vars
- For systemd/CI: export both vars explicitly
