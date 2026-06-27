# Secret Storage — leak-tight, least-privilege at rest

## Where keys live

All backend API keys are stored in `~/.config/meta-dev/secrets.env` (chmod 600,
parent directory chmod 700), OUTSIDE every repository. This file is sourced by
the user's shell profile and is never committed to any git repo.

```
~/.config/meta-dev/             # 0700
└── secrets.env                 # 0600 — export VAR=val lines, one per key
```

## How the plugin reads them

The plugin **reads by environment-variable name only** — it never opens,
parses, or reads the secrets file directly. Keys are passed to headless
workers via `env VAR=val command` (set for the child process only), never as a
CLI `--arg` (visible in `ps`) and never embedded in a prompt (which would land
in transcripts and OUTPUT_FILE.raw).

## Threat model

- **Same-user `/proc/<pid>/environ`:** the `env VAR=val` mechanism means the
  key is visible to the same user via `/proc/<pid>/environ` while the worker
  process is running. This is the accepted trade-off for env-var passing and
  matches the threat model of every CI/CD secret-injection system.
- **Transcripts and raw traces:** the `OUTPUT_FILE.raw` file records the full
  worker transcript. The distillers (`distill-headless-result.py`,
  `distill-codex-result.py`) redact known key shapes from the distilled
  `result` before writing. Defense-in-depth: the dashboard emit
  (`state.events.jsonl`) writes only verdict/metadata — never the raw worker
  `result`.
- **Git leaks:** every repo's `.gitignore` blocks `*.env`, `secrets.env`,
  `*.key`, `*.pem`, and `.secrets/`. The parent project's whitelist-aware
  `.gitignore` re-denies these patterns inside otherwise-whitelisted trees.
  An authoritative history scan confirmed no real key values in any repo's
  commit history, stash, or reflog.

## Key rotation

1. Edit `~/.config/meta-dev/secrets.env` with the new key value.
2. Re-source in any new shell: `. "$HOME/.config/meta-dev/secrets.env"`.
3. Already-running long workers hold the old key in their process environment
   until they exit — kill and restart any worker that should pick up the new
   key immediately.

## Adding a new backend

1. Add the `export NEW_BACKEND_API_KEY="..."` line to `~/.config/meta-dev/secrets.env`.
2. Add the env-var name to the runner script's backend map (key-env name
   only — never the value).
3. Ensure the distiller's redaction regex covers the new key shape if it
   differs from the existing patterns.
