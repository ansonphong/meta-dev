# Execution model discovery

Snapshot verified 2026-10-09 against the providers' public model catalogs:

| Provider | Current published ID | Runner behavior |
| --- | --- | --- |
| Anthropic Sonnet | `claude-sonnet-5-5` | `/sonnet-execute` default |
| Anthropic Opus | `claude-opus-5-5` | `/opus-execute` default |
| Anthropic Fable | `claude-fable-5-1` | Select with `--model`; `/fable-execute` still defaults to `claude-fable-5` |
| OpenAI Sol | `gpt-6.1-sol` | Select with `--model`; `/codex-execute` Sol/Terra still use `gpt-6-sol` |
| OpenAI Astra | `gpt-6-astra` | `/codex-execute` Astra tier |
| OpenAI Luna | `gpt-6-luna` | `/codex-execute` Luna tier |

Sources: [Anthropic models](https://platform.claude.com/docs/en/models/overview), [Anthropic list API](https://platform.claude.com/docs/en/api/models/list), [OpenAI models](https://developers.openai.com/api/docs/models/all), [OpenAI list API](https://developers.openai.com/api/reference/resources/models/methods/list).

When the caller asks for the latest models or access is unclear, optionally list models through the provider API using a separately supplied API key. These are read-only requests; neither runner calls them automatically. Run only in an environment with the relevant key. Do not print keys, pass them in a worker brief, or use a subscription OAuth token as an API key.

```bash
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  curl --fail --silent --show-error --max-time 30 \
    -H "x-api-key: ${ANTHROPIC_API_KEY}" \
    -H 'anthropic-version: 2023-06-01' \
    'https://api.anthropic.com/v1/models?limit=1000'
else
  echo 'ANTHROPIC_API_KEY is unset; Anthropic API models unverified' >&2
fi
```

Anthropic responses include `has_more` and `last_id`. If `has_more` is true, repeat the same request with `&after_id=<last_id>` until it is false; a single page is not the full list. Keep the key in the header, never in the URL or logs.

```bash
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  curl --fail --silent --show-error --max-time 30 \
    -H "Authorization: Bearer ${OPENAI_API_KEY}" \
    'https://api.openai.com/v1/models'
else
  echo 'OPENAI_API_KEY is unset; OpenAI API models unverified' >&2
fi
```

An API listing describes API visibility for that key, not access through the ambient Claude login or a Codex subscription. A read-only worker with no shell/API access should request caller-supplied listing evidence. If an API call fails or no key is available, report availability as unverified. Preserve any explicit `--model` exactly; do not upgrade a runner default from this dated snapshot or a live listing.
