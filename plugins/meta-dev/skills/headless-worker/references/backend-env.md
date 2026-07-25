# Backend Environment Routing

How Claude Code resolves the API backend for headless worker subprocesses.

## Routing Matrix

| Backend | `ANTHROPIC_BASE_URL` | `ANTHROPIC_AUTH_TOKEN` | How Resolved |
|---------|---------------------|----------------------|--------------|
| Anthropic direct | `https://api.anthropic.com` | `sk-ant-...` | Default |
| Sonnet (Anthropic-compat) | Provider-specific | Provider-specific | Set in profile / .env |

## Inheritance

`claude -p` inherits parent env by default. No extra work for Bash tool launches.

**Beware:**
- `env -i` strips ALL inherited vars including ANTHROPIC_BASE_URL — never use
- `sudo -E` preserves env; plain `sudo` resets it
- systemd: set `Environment=ANTHROPIC_BASE_URL=...` in unit file
- CI: export both vars in workflow yaml `env:` block

## Sonnet Hardening

When routing through a Sonnet-class Anthropic-compatible backend:

1. **Env vars must be complete.** Missing ANTHROPIC_AUTH_TOKEN → 401. Wrong ANTHROPIC_BASE_URL → model not found error.
2. **Tool call format.** Some shims translate OpenAI tool format to Anthropic format. If headless worker gets "unexpected field" errors, the shim translation might have changed — check shim version.
3. **Model routing.** In a typical project env:
   - `claude-opus-5` → maps to Opus-tier reasoning
   - `claude-sonnet-5` → maps to Sonnet (default)
   - `claude-haiku-4-5` → maps to Haiku-tier (lightweight)
4. **No vision.** Some Sonnet-class backends do not support image inputs. Avoid `Read` on images in headless workers unless confirmed.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 401 Unauthorized | Missing or wrong ANTHROPIC_AUTH_TOKEN | Check .env / CI secrets |
| "model not found" | ANTHROPIC_BASE_URL points to wrong endpoint | Verify URL matches provider |
| Empty tool response | shim format translation issue | Check backend shim version |
| Timeout on long input | Context limit hit | Truncate input or increase timeout |
