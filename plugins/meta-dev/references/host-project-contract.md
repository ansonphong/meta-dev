# Host Project Contract

The meta-dev plugin is project-agnostic. A host provides structured values by
the settings cascade and durable rules by this discovery order:

1. Root `AGENTS.md` is the canonical project doctrine.
2. `docs/agent-context/` contains routed durable context.
3. `.agents/skills/` is the canonical project skill source.
4. Vendor directories, including `.claude/`, are host adapters.

Root `CLAUDE.md` and `.claude/CLAUDE.md` remain compatibility inputs. Report a
migration warning when found without a canonical `AGENTS.md`. Initializers
never create root `CLAUDE.md`. Their required generated output is the thin
adapter `.claude/CLAUDE.md` with exactly `@../AGENTS.md` followed by a newline.

## Contract states

| State | Meaning | Required response |
| --- | --- | --- |
| canonical | Root `AGENTS.md` resolves normally and no Claude adapter exists yet. | Use it first; init adds the thin adapter. |
| adapter | Root `AGENTS.md` resolves normally and `.claude/CLAUDE.md` is exactly `@../AGENTS.md`. | Use the root doctrine first and the adapter only for that host. |
| compatibility | No canonical doctrine exists and one or more regular legacy Claude inputs are present. | Warn, then migrate their doctrine into AGENTS-first output on init. |
| missing | No canonical or legacy contract exists. | Create AGENTS-first output plus the thin adapter on init. |
| casefold_alias | A differently cased `AGENTS.md` is the same inode. | Warn and repair the host naming before cutover. |
| duplicate_copy | A differently cased `AGENTS.md` has the same bytes but a different inode. | Warn and repair the host naming before cutover. |
| conflict | Candidate doctrine, adapter, or skill root is unsafe. | Refuse to select or initialize a default. |

Resolve every discovered candidate before comparison. Classify two candidates as
`casefold_alias` only when their paths differ by case and their resolved device
and inode are equal. Classify as `duplicate_copy` only when resolved device and
inode differ but the SHA-256 bytes are equal. Classify as `conflict` when their
SHA-256 values differ, or when a non-adapter legacy contract disagrees with the
canonical doctrine. Do not use path spelling alone to infer identity.

Legacy candidates include both root `CLAUDE.md` and `.claude/CLAUDE.md`.
Either candidate is a `conflict` when it is a symlink (including a dangling
symlink) or any non-regular file. A successful compatibility initialization
copies root doctrine first, then nested doctrine when both exist, with a marked
separator; it removes root `CLAUDE.md` and writes `.claude/CLAUDE.md` exactly
as `@../AGENTS.md`. This preserves both legacy doctrines and leaves the project
in the thin `adapter` state.

`agent-surface-doctor.py --classify` is the production discovery routine.
`init-project.sh` calls it before any write. The `agent-surface-check` cutover
wrapper requires `canonical` or the exact thin `adapter` state. Repository
values in manifests and wrapper scopes must resolve inside the workspace root;
`..` escapes are rejected. `.agents/skills` itself, as well as its contents,
must not be symlinks.

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
