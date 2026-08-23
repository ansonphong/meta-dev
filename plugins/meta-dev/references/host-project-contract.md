# Host Project Contract

The meta-dev plugin is project-agnostic. A host provides structured values by
the settings cascade and durable rules by this discovery order:

1. Root `AGENTS.md` is the canonical project doctrine.
2. `docs/agent-context/` contains routed durable context.
3. `.agents/skills/` is the canonical project skill source.
4. Vendor directories, including `.claude/`, are host adapters.

Root `CLAUDE.md` and `.claude/CLAUDE.md` remain compatibility inputs. Report a
migration warning when found without a canonical `AGENTS.md`; never create them
as preferred initializer output.

## Contract states

| State | Meaning | Required response |
| --- | --- | --- |
| canonical | Root `AGENTS.md` resolves normally. | Use it first. |
| adapter | A vendor file imports the canonical doctrine without repeating rules. | Use only for that host. |
| compatibility | Only a legacy Claude contract is present. | Read it, report migration warning, and create AGENTS-first output on init. |
| forbidden | A vendor adapter repeats, replaces, or contradicts canonical rules. | Report conflict; do not select a default silently. |

Resolve every discovered candidate before comparison. Classify two candidates as
`casefold_alias` only when their paths differ by case and their resolved device
and inode are equal. Classify as `duplicate_copy` only when resolved device and
inode differ but the SHA-256 bytes are equal. Classify as `conflict` when their
SHA-256 values differ, or when a non-adapter legacy contract disagrees with the
canonical doctrine. Do not use path spelling alone to infer identity.

## Project settings

Read structured values from the settings cascade: plugin defaults, project
`plans/_dashboard/settings.json`, then local overrides. Use project doctrine
and routed context for architecture, naming, security boundaries, deployment,
and policy. If a fact exists in neither source, use a safe portable default,
then ask the user.

Do not hardcode a host project's names, domains, repositories, stacks, brands,
endpoints, or platform details.

## Canonical skill ABI

`.agents/skills/<name>/` is canonical. Each skill has a regular `SKILL.md`
with YAML frontmatter and body. The frontmatter uses common identity and
argument fields; the body states accepted arguments. Optional `scripts/`,
`references/`, and `assets/` directories are resource roots. All links and
paths are relative to the skill directory. Symlinks are forbidden in canonical
or generated skills. Host-only discovery metadata stays in a generated host
adapter, never in the canonical skill.

`sync-agent-skill-adapters.py` copies complete canonical directories into
`.claude/skills/` and records SHA-256 values in
`.agent-skill-adapters.json`. It preserves file modes, has no symlink fallback,
and check mode rejects missing, unknown, or edited mirror files. Canonical
skills win on collision: a generated mirror is replaced from its source; a
hand-authored host mirror is a validation error.
