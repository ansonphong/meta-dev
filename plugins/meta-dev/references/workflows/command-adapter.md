# Codex Command Adapter

Resolve plugin-relative files from the selected skill's own path. Read the named
command and apply `references/workflows/protocol.md` once; reuse loaded context.
Treat text after the skill mention as `$ARGUMENTS`. Applicable `AGENTS.md` and
routed neutral context supply project rules; `CLAUDE.md` is a compatibility input
only when investigating an adapter or migration.

Translate vendor syntax to real native tools: `${CLAUDE_PLUGIN_ROOT}` means the
resolved plugin root; Read/Edit/Bash and Agent/Task mean available host operations.
TaskCreate/TaskUpdate use a native tracker if present. Claude command frontmatter
is not a Codex model or tool contract. Use configured native routes and explicit
model/context flags; external backends require existing authorization.

Carry scoped authorization across stages, workers, repairs and compaction.
Planning/review/diagnosis alone grant no source authority. Preserve protected
human gates; ask only for new scope, decisions or authority.

## Codex efficiency boundary

The selected command owns the task. A stage name, section heading, example,
or descriptive reference is not an invocation. Load a referenced skill only for
an explicit request, unfamiliar tool or concrete unresolved question.
When the selected command explicitly invokes a skill or command, follow that
required step: use the matching native skill or read its canonical
`workflow-skills/<name>/SKILL.md` / `commands/<name>.md` and execute it inline.
A vendor Skill tool name does not require that vendor tool to exist. These
required steps differ from descriptive mentions and automatic stage chains. `--to N`
is a stage ceiling, not permission to run every associated specialist workflow.

Stage 6 uses one native Codex review through the configured route; preserve
requested delivery/final reviews and reuse unchanged covering evidence.
Do not infer `meta-eval`, `meta-audit`, or standalone `housekeeping` from execution.
Optional reviewer `INFRA_RED` does not authorize switching model families.
Before dispatching two or more external workers, state the count and obtain
confirmation unless existing authorization already covers that dispatch.
Do not turn routine repairs or replacements within that authorization into a
new permission request. Shared protocol and project rules override incompatible
vendor recipes; unavailable tools never become invented capabilities.
