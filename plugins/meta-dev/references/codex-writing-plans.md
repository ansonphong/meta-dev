# Codex Writing Plans Contract

This is the execution-plan contract for the native Codex `plan` workflow. It
adapts the useful parts of Superpowers `writing-plans` to meta-dev's centralized
plan ledger, focused-test policy, shared-worktree git rules, and GPT-5.6.

## Contents

1. Planning boundary
2. Plan size, storage, and target
3. Required investigation
4. Single-file plan structure
5. Task contract
6. No-placeholder rule
7. Self-review gate
8. Handoff

## 1. Planning boundary

A request to investigate, design, or plan authorizes inspection and writing the
plan artifact. It does not authorize implementation. Finish by saving the plan
and reporting its path.

Write for a skilled implementation agent that has no conversation history. The
plan must carry the context that would otherwise disappear at compaction or in
a fresh worker:

- the requested outcome and explicit non-goals;
- verified current behavior, relevant symbols, callers, and data flow;
- decisions already made and the reason for each;
- exact files and semantic anchors;
- interfaces between tasks;
- ordered implementation actions;
- focused verification commands and expected results;
- failure handling, blast radius, and rollback.

Do not make the executor repeat the planner's discovery work.

## 2. Plan size, storage, and target

Use one dated Markdown file for ordinary medium-sized work:

```text
plans/<repo>/YYYY-MM-DD-descriptive-kebab-case.md
```

Choose the single-file form when the change is one cohesive outcome, normally
within one logical repository, and can be expressed in roughly two to six
independently verifiable tasks. A single task may touch several related files.

Use the full multi-phase planner only when the work has independent subsystems,
cross-repository sequencing, more than about six tasks, or phase boundaries
that need separate review gates. Its artifact is a directory whose index is
`00-master-plan.md`.

Storage rules:

- Store plans under the host project's central `plans/<repo>/` ledger, never in
  a child code repository or `docs/`.
- Use today's local date and a lowercase kebab-case slug.
- Do not leave a plan only in chat.
- Do not write `status:`. Plan state is derived.
- A single-file plan contains task headings but no Markdown checkbox rows.
- In a multi-phase plan, `00-master-plan.md` is the sole checkbox ledger.

Plan target:

```yaml
target: lean | standard | explicit    # optional; absent means `standard`
```

`target` scales authoring depth to the capability of the executing agent.
`references/plan-targets.md` is the ONE definition of the tiers, the tier-to-backend
mapping, the capability ordering, and the blast-radius override. Read it and set the
field; do not restate the table in the plan or in this document.

## 3. Required investigation

Before drafting:

1. Resolve the host project root and logical repository.
2. Read the applicable `AGENTS.md` files and only the context/docs relevant to
   the change.
3. Inspect every proposed production file and the nearest focused verifier.
4. Search callers, consumers, schemas, serializers, and persisted boundaries
   for any interface being changed.
5. Check recent history when a surprising implementation may be intentional.
6. Record the inspected revision and whether relevant files were already dirty.
7. Resolve contradictions before writing. Ask only when a choice would
   materially change the product or contract.

Every statement about the current codebase must come from inspected source.
Never invent a symbol, path, payload, or test command because it looks likely.

## 4. Single-file plan structure

Render these sections in this order:

1. Frontmatter: `stage`, `repo`, `context`, `docs`, `depends`, `blocks`, `why`.
2. Title.
3. `Outcome`: goal and user-visible result.
4. `Architecture`: chosen approach and why it fits the existing system.
5. `Tech Stack`: only technologies that affect the implementation.
6. `Global Constraints`: exact project-wide rules that every task inherits.
7. `Codebase Ground Truth`: inspected revision, current behavior, symbols,
   callers, data flow, and non-obvious constraints. Record **anchors, not frozen
   content** — the symbol name plus the invariant that matters, never pasted file
   bodies or signature dumps, which are stale the moment the tree moves (LP-007).
8. `Decisions`: locked choices with rationale.
9. `Non-Goals`.
10. `File Structure`: every create/modify/delete/move path and responsibility.
11. `Implementation Tasks`.
12. `Acceptance Criteria`.
13. `Failure Modes`.
14. `Blast Radius`.
15. `Rollback`.

Keep the skill prompt lean; put detail in the saved artifact. Concision is not a
license to omit execution-critical information.

## 5. Task contract

Each task must produce one coherent, reviewable, independently verifiable
change. Fold scaffolding, config, and docs into the task whose deliverable needs
them.

**Objective, Files, Acceptance, and Commit are invariant across every target.**
Context depth, Work sketch depth, and Verify-After detail scale by target per
`references/plan-targets.md`.

Every task includes:

- **Objective:** the concrete state produced by this task.
- **Context:** the exact existing symbols/behavior the implementer must know.
- **Dependencies:** prior task outputs or `none`.
- **Files:** exact paths, action, responsibility, and semantic anchors.
- **Interfaces:** exact inputs consumed and outputs produced, including
  signatures, types, payloads, event names, or storage shapes.
- **Work:** ordered actions. Name the target symbol and the actual
  transformation. Include a verified code sketch or contract when it removes
  ambiguity.
- **Test policy:** `test: yes` only when the host policy says the failure is
  critical enough to deserve a test; otherwise `test: no`.
- **Verify-Before:** required for behavior-changing `test: yes` tasks, with the
  expected failure or baseline.
- **Verify-After:** one focused test file/node or declared-file-scoped check,
  plus expected output. Never use a broad suite as a task gate.
- **Acceptance:** observable task-local completion criteria.
- **Commit:** exact repository root, message, and explicit paths. Follow the
  host's shared-worktree commit form.

For moves or zero-behavior refactors, point to the verified source symbol and
say which transformations are permitted. Do not fabricate a replacement body
that will be stale by execution time.

For interfaces shared by later tasks, define the exact name and type in the
producing task. Repeat the necessary contract in each consuming task; a fresh
worker may receive only one task.

## 6. No-placeholder rule

The following make a plan invalid:

- `TBD`, `TODO`, `implement later`, or “fill in details”;
- “add validation,” “handle edge cases,” or “write tests” without naming the
  cases and expected behavior;
- “similar to Task N” instead of restating the needed contract;
- a path without its intended change;
- a command without its expected result;
- a code step without a symbol, transformation, or verified sketch;
- a later task referencing a type, field, endpoint, or function that no earlier
  task defines;
- broad verification such as a whole repository test, build, or type check when
  a focused command exists;
- line-number-only anchors. Prefer symbols because line numbers drift.
- pasted file contents or signature dumps presented as ground truth. Record the
  symbol and the invariant; everything frozen drifts, not just line numbers.

The expected-result ban binds **whenever a command is given**. At `target: lean` a
task may instead state an acceptance condition and let the executing agent choose the
command — that is not a placeholder, and it is the only tier where omitting the
command is permitted. Every other entry above applies at every tier.

Unknowns that genuinely cannot be resolved during planning are named decisions
with an owner and a blocking condition, not hidden placeholders.

## 7. Self-review gate

Before rendering, review the completed IR with fresh eyes:

1. **Request coverage:** map every requested behavior and non-goal to a task or
   acceptance criterion.
2. **Fresh-agent test:** confirm a new agent could execute each task without the
   conversation or another task's prose.
3. **Ground-truth test:** confirm every path, symbol, signature, and command was
   inspected or clearly introduced by the plan.
4. **Interface consistency:** confirm producers and consumers use identical
   names, types, and payload shapes.
5. **Dependency order:** confirm no task consumes an output that does not yet
   exist.
6. **Placeholder scan:** remove every vague instruction described above.
7. **Verification quality:** confirm commands are focused, runnable from the
   stated directory, and include expected results.
8. **Scope check:** split independent subsystems; remove speculative extras.
9. **Artifact check:** confirm the dated path, frontmatter, no `status:`, and no
   single-file checkbox rows.

Fix failures inline before saving. Validation is a gate, not a report appendix.

## 8. Handoff

After the renderer succeeds, report:

- the exact saved plan path;
- whether it is single-file or multi-phase;
- the number of tasks;
- any unresolved blocker;
- that implementation has not started.

Do not automatically execute the plan. Wait for an explicit implementation
request.
