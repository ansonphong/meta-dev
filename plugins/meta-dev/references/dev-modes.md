# Existing mode and gate flags

Use `references/workflows/protocol.md` for stage outcomes and authority and
`references/adaptive-workflow.md` for depth/capacity. No mode creates another
lifecycle or adds model capabilities.

- Interactive pauses for consequential unresolved decisions or an explicit
  user gate, not every stage transition.
- `--cruise`/autopilot proceeds within authorized scope; it never adds authority.
- `--autonomous` or a scoped unattended implementation request permits execution
  for its scope. Read `references/autonomous-mode.md` when using that mode.
- Brainstorm/Stage 1 stops with `brainstorm.md`; design/Stage 2 stops with
  required `design.md` and optional supporting files. Stage 3 creates
  `00-master-plan.md`, using meta-planner when applicable, otherwise one page.
  Stage 4 edits and hardens all applicable preceding artifacts. User overrides apply.
- Any stage may add supporting research in the subject directory's `research/`
  subfolder; research never replaces its required artifact or advances its ceiling.
- Default `--to` is 4 for other planning-only requests. An implementation go permits
  execution and review; explicit stage ceilings remain binding.
- `--gate all` selects stage checkpoints; `--gate exec` gates implementation
  when not already authorized; `--gate none` removes routine checkpoints but
  does not authorize source work or waive protected actions.
- `--codex` selects the existing read-only Codex second opinion at Stage 4.5;
  `--cross-family` selects the configured permitted reviewer. Both are opt-in,
  not a mandatory part of the six stages. Honor external-service authorization.

Native tracking is optional when absent. Record durable state through planctl;
coalesce related artifact commits. No six-commit minimum, per-stage push or
implicit audit/evaluation/housekeeping. A budget cap never converts a blocker
into PASS. Preserve actual acceptance/manual gates and unrelated peer work.
