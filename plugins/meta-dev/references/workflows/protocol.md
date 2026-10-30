# Shared workflow contract

Meta-dev supplies stage outcomes, durable plan state and acceptance.
The native host supplies tools, working method and session management. User/project
instructions and mandatory environment protections take precedence.

## Six stages

| Stage | Required outcome |
|---|---|
| Brainstorm | Intent, scope, alternatives and consequential unknowns understood. |
| Design | Approach, interfaces and meaningful tradeoffs decided. |
| Plan | Concrete changes, dependencies and focused acceptance evidence identified. |
| Harden | Plan checked against relevant live code; no unresolved blocker. |
| Execute | Approved outcome implemented, repaired, verified and committed. |
| Review | Independent review covers the actual result and integration seams. |

Stages do not require separate agents or approval prompts. Keep required
complexity checks; combined stages may share a check where permitted.

### Required stage artifacts

These are mandatory baseline deliverables, not examples. Unless the user
explicitly specifies otherwise:

- Stage 1 (Brainstorm): write `brainstorm.md` with intent, scope, alternatives
  and unknowns. Supporting research files belong in `research/`. Do not create a design or
  master plan yet.
- Stage 2 (Design): write `design.md` with approach, interfaces and tradeoffs.
  Supporting design files are allowed, but never replace required `design.md`.
  Do not create a master plan yet.
- Stage 3 (Plan): create `00-master-plan.md`. Invoke `commands/meta-planner.md`
  through the native command adapter when multi-phase decomposition or detailed
  task planning is applicable. For bounded work, write a one-page master plan
  with concrete changes and focused acceptance checks using existing plan
  tooling; do not force phases or invoke the planner just for ceremony.
- Stage 4 (Harden): check and edit all applicable preceding artifacts, including
  `brainstorm.md`, `design.md`, supporting design files, `00-master-plan.md` and
  planner output. Resolve gaps, contradictions and live-code assumptions across
  them; do not harden only the master plan or create a replacement master plan.

Adapt depth, supporting files and phase structure to the work, but never silently
rename, omit or substitute a required artifact or exceed the stage ceiling.

Compact staged plans may use ordinary Markdown under project conventions. If
using the IR renderer, use version `1.0` single-file layout with artifact_path
ending in `00-master-plan.md`; version `1.1` requires dated filenames and must
not silently override the staged workflow filename.

Use one subject directory under the project's configured planning location
(portable fallback: `plans/<repo>/<subject>/`, using the configured repository
alias). Reuse valid existing artifacts and
preserve unrelated files. Brainstorm and design documents are ordinary Markdown,
not executable plans: do not add plan state/ledgers or call planctl/stage-emit on
those files. Never create a placeholder master plan for early-stage tracking.

Any stage may create supporting research files in a shared `research/` subfolder
inside that subject directory. Create it only when research is needed; use
descriptive filenames and link relevant findings from the stage artifact.
Research supplements the required deliverables and never replaces them or
advances the stage ceiling. Reuse relevant existing research across stages.
Stage 4 checks research supporting its decisions and updates stale or
contradictory findings as needed.

A brainstorm/Stage 1 request stops at Stage 1; a design/Stage 2 request stops at
Stage 2. Natural-language stage limits bind just like `--to 1` and `--to 2`.
Only an explicitly broader range proceeds further, producing each requested
stage's artifact in order. Resume from valid artifacts without repeating stages.
Explicit user instructions may override filenames, omit files or combine records.
Routine work outside an explicit staged workflow or individual stage request
may keep one short record in chat.

## Skill selection and context

Load a skill for an explicit request, an unfamiliar tool, or a concrete unresolved
question that could change the result. Explicitly selecting a command also
selects the steps it requires; follow their native or canonical inline procedure.
Reuse valid instructions and evidence;
do not reload them at stage boundaries. A stage name or slight keyword overlap
does not trigger a skill, mandatory workflow chain or new document. Project/user
requirements remain binding. This rule also applies when optional external skill
packs prescribe blanket invocation; do not let them expand the selected task.

Create a plan file only when requested (including the plan command) or necessary
for consequential uncertainty, dependencies or coordination. Explain an unrequested
plan's concrete need first. Use the project's location and state conventions.
Without a plan, keep scope, approach, checks and results in chat.
This rule does not suppress required brainstorm/design artifacts; entering
Stage 3 requests its master plan.

## Authority

A planning/review/diagnosis request is read-only with respect to source unless
fixes are requested. An explicit scoped implementation request covers necessary
reversible decisions, repairs, verification, commits and integration through
completion. Carry authority across stages, workers and compaction; do not ask
again merely because a stage changed or an ordinary test failed.

Ask only for genuinely missing product decisions, new scope or authority.
Deployment, live migration, external spending/sending, destructive operations
and protected human actions require authority covering those actions/targets;
existing authority counts. Sensitive work retains appropriate contract/security
checks without automatically demanding another go. Desktop smoke tests require
scheduled approval covering interactions, environment and rollback.
Do not bypass denied operations, expose credentials or invent capabilities.

The default `/meta-dev` ceiling is Stage 4 for planning-only work without an
earlier named stopping stage. Brainstorm/design requests retain their Stage 1/2
ceilings. A scoped
implementation go or explicit execution request allows progression through
implementation and closing review. Explicit stage ceilings and human gates
still apply. Tool permission modes alone never grant source authority.

## Execution and state

Completion ownership, focused verification, causal failures, same-cause
reassessment, bounded escalation and genuine blockers are authoritative in
`references/execute-charter.md`. Scheduling depth/capacity comes from
`references/adaptive-workflow.md` and existing configured budgets/routes.
Use native tools; no mandatory delegation, model switching or cross-family
review. Apply explicit runner model/context flags without silently dropping them.

For existing or requested/necessary plans, Markdown is git truth and
`scripts/planctl.sh` is the only state write door. Plan frontmatter, ledgers,
stage tracking, review recording and archival apply only to those plans;
never create a plan just to satisfy bookkeeping. Without a plan, report scope,
verification, review and results in chat. File ownership claims remain applicable.
When a plan exists, one conductor owns acceptance/state; workers own scoped implementation and
exact-path commits. Keep one acceptance record per handle, even when one owner
implements a coupled slice. Inspect the actual diff and whole-task evidence
before accepting through planctl. Continue dependency-ready disjoint work.

Return the existing causal result: `FOCUSED_PASS`, `TASK_RED`, `BASELINE_RED`,
`INFRA_RED` or `BROAD_VERIFY_OMITTED`, with actual command, exit/output, commits
and unresolved acceptance. A focused pass proves only its covered behavior;
unavailable evidence and budgets never establish acceptance.

## Review and closeout

Keep required independent review. The normal final gate is one native reviewer
covering the complete change and integration seams. Reuse a covering phase
review; do not add a second closing pass over unchanged content. External or
cross-family reviewers are opt-in, not a default stage. If independent review
is unavailable, label self-review honestly and leave the required gate open.

Use `workflow-skills/code-review-protocol/SKILL.md` when performing review.
Load structured verdict and source-bound acceptance details only when recording
acceptance or when requested. Batch findings/repairs, review affected deltas and
retain unaffected evidence. A review does not authorize fixes; an existing scoped
implementation go covers repairs.

Update only affected declared context/docs and owning plan/runbook state.
Archive only after required acceptance/manual gates pass. Batch bookkeeping
at useful seams. Push only under release authority; never infer deployment.
Report actual results and blockers briefly, without elaborate cards or ceremony.
Do not claim measured savings from instruction changes alone.

## Host adapters and explicit commands

The primary Codex menu is `meta-dev`, `plan`, `harden`, `execute`, `review`,
`diagnose`, `runbook`, `ops`, and `command-router`. Other command skills remain
explicitly invocable through `$meta-dev:<command>`; their metadata disables
implicit invocation. The Codex manifest sets `commands: []` to disable automatic
legacy-command migration: native skills already cover those commands, so
`source-command-*` duplicates must not be generated. Claude retains its native
command surface.
Translate unavailable vendor syntax to actual host tools, never simulate tools
with invented capabilities. Headless runners are for deliberate CLI crossings.
`references/workflows/command-adapter.md` describes the Codex adapter.

`routes.json` remains the command routing source: each command maps to one real
workflow/subcommand and procedure; aliases share targets, unknown names fail
closed. Explicit model/backend selection uses existing configuration and runner
validation, not a new routing framework.

Campaign runbooks are only for related plans that need cross-plan ordering.
One campaign conductor shares actual host capacity across members/workers/fixers;
disjoint write sets may proceed concurrently and overlapping owners serialize.
A campaign or model selection never expands authority.
