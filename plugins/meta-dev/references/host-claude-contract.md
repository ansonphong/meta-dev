# Host Claude Contract — Conventions Every Ported Command Can Assume

The meta-dev plugin is deployed into diverse projects. To avoid hardcoding project-specific facts (paths, tools, naming conventions), every plugin command reads the host project's CLAUDE.md and/or the project settings cascade to discover:

1. **Repository structure** — monorepo vs single-repo, child repo paths
2. **Test framework and commands** — pytest, vitest, npm test, svelte-check, etc.
3. **Build/run commands** — how to start services, run migrations
4. **Branching and git conventions** — master vs main, commit style, push rules
5. **Code conventions** — naming (PascalCase, snake_case, camelCase), file naming
6. **Security boundaries** — license validation, auth patterns, API keys
7. **Deploy paths** — how each repo is deployed (auto-deploy on push, manual, CI/CD)
8. **Path conventions** — where plans, config, tests, and source live

## fallback chain

When a command needs a project-specific value, it follows this chain:

1. **Project settings cascade** — `bash scripts/config-get.sh meta_dev.<path>` (reads templates → project settings.json → settings.local.json)
2. **Host CLAUDE.md** — extract relevant conventions from the host project's CLAUDE.md
3. **Hardcoded defaults** — safe, portable defaults defined in this contract
4. **Ask the user** — if all else fails, surface the ambiguity

## Safe Defaults

| Convention | Default | Notes |
|-----------|---------|-------|
| Test runner | `pytest` (Python), `npm test` (Node), `svelte-check` (Svelte) | Detect from filesystem |
| Branch | `master` | Check git |
| Commit style | Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`) | Universal |
| Plans root | `plans/` | Configurable via config cascade |
| Archive subdir | `_archive/` | Configurable |
| Learned patterns | None | Configurable per-project |

## Reading the Host Project

At startup, each command SHOULD:

1. Read `CLAUDE_PLUGIN_ROOT` env var to locate plugin files
2. Resolve project root from caller's context (current directory or explicit path)
3. Call `bash scripts/config-get.sh` for any configured path
4. Scan host CLAUDE.md for test/build/deploy conventions

## Contract Boundaries

- **DO** read conventions from host CLAUDE.md
- **DO** use config cascade for paths and model preferences
- **DO NOT** hardcode project names, domains, or repo names
- **DO NOT** assume specific tool versions or platform (WSL, macOS, Linux)
- **DO NOT** hardcode API endpoints or URLs
