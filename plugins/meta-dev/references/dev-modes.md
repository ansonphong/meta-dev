# Development modes

Read `references/adaptive-workflow.md` for depth and
`references/dev-swarms.md` for stage exit criteria. Mode changes prompts and
stage ceilings, not model capabilities or source permissions.

## Detect intent

- Interactive is the default. Pause at material unresolved decisions or the
  requested gate, not merely because a stage label changed.
- Explicit `--cruise`/autopilot means proceed through authorized stages without
  routine transition prompts.
- `--autonomous` or an unambiguous request to implement unattended supplies
  execution permission for the declared scope and suppresses routine prompts.
  Follow `references/autonomous-mode.md`; no automatic paid consultant.
- Diagnosis/probe requests remain read-only unless fixes were also requested.
- Accept Edits tool mode and incidental words such as "auto" or "walk" do not
  independently authorize execution.

Default `--to` is 4. An explicit implementation request, `--to 5|6`, or a
scoped cruise/autonomous execution request permits Stage 5. `--gate none`
alone only removes transition prompts; it does not turn an audit into a fix.

## Depth is independent of mode

Keep the six-stage progress framework. For a mechanical, understood change,
Stages 1–4 may be satisfied by a brief intent, contract, and focused check.
New behavior may use focused planning/hardening when risks are bounded; neither
three files nor a new module forces a fixed swarm. High-risk work retains its
contract/security gates. Resolve depth through `scripts/workflow-policy.py`.

## Advance on evidence

Track stage progress with the native task surface when present and emit state
through `stage-emit.sh`/planctl. Minimal hosts use concise progress messages;
do not fail work because a vendor-specific TaskCreate tool is missing.

For each stage, produce its minimum sufficient artifact, meet exit criteria,
record state, and advance within the requested ceiling. Related design and
planning records may share an artifact. Commit meaningful changes at safe seams;
there is no six-commit minimum and no automatic per-stage push.

A stage blocked after its bounded retries parks that subject, not unrelated
work. Stage 4 needs no unresolved blocker, not zero cosmetic suggestions.
A budget cap never converts unresolved material findings into success.

## Optional extra-family review

`--codex` requests the read-only Stage 4.5 Codex second opinion.
`--cross-family` uses the configured permitted review route. OFF by default.
The native owner triages findings, with no mandatory integrate-back vendor.
See `references/dev-swarms.md`; execution permission is unchanged.

## Completion

Stage 6 uses one native covering review, not implicit meta-eval + meta-audit +
housekeeping calls. Sync relevant context and plan state. Archive only when
required acceptance/manual gates permit. Push only under explicit user/project
release authority. Preserve unrelated dirty work rather than requiring a clean
entire tree.

Multiple subjects may proceed independently with disjoint ownership, within the
same host-wide worker budget. Do not multiply per-subject caps into unbounded
nested fan-out. Planning artifacts remain under configured plans_root, never
source directories or vendor context trees.
