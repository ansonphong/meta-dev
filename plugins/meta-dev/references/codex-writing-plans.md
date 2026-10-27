# Native planning

Use `references/workflows/protocol.md` for authority and stage outcomes.
Apply its plan-file gate first: an explicit request for a plan file or invocation
of the plan command/skill requests a saved plan. Otherwise write one only when
durable planning is necessary for consequential uncertainty, dependencies or
coordination, explaining the concrete need first. Routine work proceeds directly
with intent, focused checks and results in chat. Loading this reference or a
generic planning skill does not itself request a file. If no plan is needed,
stop this authoring workflow and continue the authorized task directly.

Write a plan a skilled owner can execute without rediscovering the task.
Use the project's central plan location and existing layout conventions.
For a warranted plan, use one short record; create a feature directory or phase
files only when the project layout or the work needs them. Never relocate existing
unrelated artifacts merely to enforce a preferred shape.

Include the outcome/non-goals, inspected revision and relevant live anchors,
decisions, exact files, dependencies/interfaces, observable acceptance and
focused verification commands with expected results. Explain only what affects
implementation. No fixed fifteen-section template, code-body transcript or
separate DOD/design/gap report is required for an understood change.
Check coverage, live-code assumptions, producer/consumer joins and scope before
implementation. Ask only for consequential decisions the available evidence
cannot resolve. Unknowns need an owner/blocking condition, not vague TODOs.

## State and existing managed artifacts

Planctl is the only state write door. Use one canonical ledger; an ordinary
single-file plan owns its rows, while a multi-phase plan uses 00-master-plan.md.
Create/update task state through planctl and never type derived `status:`.
Preserve individual task acceptance when one owner implements a coupled slice.

Simple Markdown may be authored directly using project conventions. When using
the explicit `/meta-planner` or updating an existing schema-managed artifact,
retain its IR and use `scripts/plan-artifact-render.py --validate` then the
existing renderer. Do not replace a managed artifact with incompatible prose.
Use `references/plan-targets.md` and `scripts/workflow-policy.py` when selecting
a target; sensitive risk still raises contract/verification precision.

Save the plan this turn and report its exact path and unresolved decisions.
Planning-only requests stop before source implementation. An existing scoped
implementation request continues without another go. Execution ownership,
focused testing and same-cause escalation follow references/execute-charter.md.
