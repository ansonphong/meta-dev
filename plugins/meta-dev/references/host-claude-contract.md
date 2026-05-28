# Host Claude Contract — How the Project Informs the Plugin

The meta-dev plugin ships **100% project-agnostic**: no project names, domains, repo names, stacks, brand colors, or endpoints are hardcoded anywhere in commands, references, scripts, or templates. Everything project-specific is supplied by the **host project** through two channels:

1. **Settings cascade (JSON)** — `templates/settings.json` (plugin defaults) → `<project>/plans/_dashboard/settings.json` (project) → `settings.local.json` (local overrides), merged by `config-merge.py` and read with `bash scripts/config-get.sh meta_dev.<dot.path>`.
2. **Host `CLAUDE.md`** — for prose conventions the JSON doesn't capture (architecture, naming, security boundaries, deploy mechanics, ethical/policy gates).

If a fact lives in neither, the command falls back to a safe portable default, then asks the user.

## What the project informs (and where)

| Concern | Settings JSON path | Host CLAUDE.md role |
|---------|--------------------|---------------------|
| Plan layout / repo areas | `meta_dev.paths.plan_subdirs` (ships `[]`) | Describe the repo/monorepo structure |
| Plans root / archive | `meta_dev.paths.plans_root`, `archive_subdir` | — |
| Design source of truth | `meta_dev.paths.design_doc`, `meta_dev.review_design.*`, `meta_dev.ux.design_system_rules` | Point to the design system; state visual rules |
| Per-stage models | `meta_dev.models.stage_overrides`, `default_model` | — |
| Git corruption mitigations | `meta_dev.filesystem.git_corruption_mitigations` | Note platform quirks (e.g. WSL/9p) |
| Destructive-command policy | `meta_dev.guard.*` | State which operations are forbidden |
| Risk keywords (execute) | `meta_dev.execute.risk_keywords.<category>` | Name domain risk areas |
| Security invariants | `meta_dev.security.always_checked_invariants` | Enumerate the always-checked critical checks |
| Canary targets | `meta_dev.canary.targets` | Note which services exist + how to reach them |
| Init-check probes | `meta_dev.init_check.services` | Note required services / runtimes |
| Ship targets / deploy | `meta_dev.ship.targets` | Deploy mechanics, migration policy |
| Eval health checks | `meta_dev.eval.health_checks` | — |
| Test / build / branch / commit style | (detected) | Test runner, build/run cmds, branch name, commit conventions |

**Rule of thumb:** structured enumerable values → JSON; prose conventions and policy → CLAUDE.md. Commands read JSON first, then enrich from CLAUDE.md.

## Fallback chain

When a command needs a project-specific value:

1. **Settings cascade** — `bash scripts/config-get.sh meta_dev.<path>`
2. **Host CLAUDE.md** — extract the relevant convention
3. **Safe default** — portable default from the table below
4. **Ask the user** — surface the ambiguity if all else fails

## Safe Defaults

| Convention | Default | Notes |
|-----------|---------|-------|
| Test runner | Detect from filesystem (e.g. `pytest`, `npm test`, `go test`) | Examples only — never assume a stack |
| Branch | Detect from `git` (`main` or `master`) | Never assume |
| Commit style | Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`) | Universal |
| Plans root | `plans/` | Configurable |
| Plan subdirs | `[]` (flat) | Project defines its own |
| Archive subdir | `_archive/` | Configurable |
| Learned patterns | none | Configurable per-project |
| Risk keywords | generic baseline in `risk-tag.sh` | Project augments via config |

## Reading the Host Project

At startup each command SHOULD:

1. Read `CLAUDE_PLUGIN_ROOT` to locate plugin files.
2. Resolve the project root from the caller's context.
3. Call `bash scripts/config-get.sh` for any configured value.
4. Scan the host `CLAUDE.md` for conventions and policy the JSON doesn't carry.

## Contract Boundaries

- **DO** read conventions from the host CLAUDE.md and the settings cascade.
- **DO** treat any stack/tool/service named in references as an *example*, not a requirement.
- **DO NOT** hardcode project names, domains, repo names, brand values, or endpoints.
- **DO NOT** assume a specific tool version, framework, or platform.
- **DO NOT** bake project-specific keywords into scripts — expose a config knob instead.
