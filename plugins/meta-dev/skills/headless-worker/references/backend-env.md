# Backend Environment Routing

How Claude Code resolves the API backend for headless worker subprocesses.

## Routing Matrix

| Backend | `ANTHROPIC_BASE_URL` | `ANTHROPIC_AUTH_TOKEN` | How Resolved |
|---------|---------------------|----------------------|--------------|
| Anthropic direct | `https://api.anthropic.com` | `sk-ant-...` | Default |
| DeepSeek V4 shim | `https://api.deepseek.com/anthropic` | `sk-...` (DeepSeek key) | Set in profile / .env |
| Other Anthropic-compat | Varies | Varies | Provider-specific |

## Inheritance

`claude -p` inherits parent env by default. No extra work for Bash tool launches.

**Beware:**
- `env -i` strips ALL inherited vars including ANTHROPIC_BASE_URL — never use
- `sudo -E` preserves env; plain `sudo` resets it
- systemd: set `Environment=ANTHROPIC_BASE_URL=...` in unit file
- CI: export both vars in workflow yaml `env:` block

## DeepSeek V4 Hardening

When routing through DeepSeek shim:

1. **Env vars must be complete.** Missing ANTHROPIC_AUTH_TOKEN → 401. Wrong ANTHROPIC_BASE_URL → model not found error.
2. **Tool call format.** DeepSeek shim translates OpenAI tool format to Anthropic format. If headless worker gets "unexpected field" errors, the shim translation might have changed — check shim version.
3. **Model routing.** In a typical project env:
   - `claude-opus-4-7` → maps to V4-Pro
   - `claude-sonnet-4-6` → maps to V4-Pro (same)
   - `claude-haiku-4-5` → maps to V4-Flash
4. **No vision.** DeepSeek V4 does not support image inputs. Avoid `Read` on images in headless workers.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 401 Unauthorized | Missing or wrong ANTHROPIC_AUTH_TOKEN | Check .env / CI secrets |
| "model not found" | ANTHROPIC_BASE_URL points to wrong endpoint | Verify URL matches provider |
| Empty tool response | shim format translation issue | Check DeepSeek shim version |
| Timeout on long input | Context limit hit | Truncate input or increase timeout |
