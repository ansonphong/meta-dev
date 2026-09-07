# Review Dimensions — Detailed Rubric

Each dimension returns `PASS`, `NEEDS_FIX`, or `NEEDS_REVIEW`.
`NEEDS_REVIEW` means the evidence is insufficient or the issue needs a product,
architecture, security, or other human judgment. It never means "silently fix."

## 1. Correctness

| Criterion | Pass | Needs Fix |
|-----------|------|-----------|
| Logic matches intent | All branches handle expected flow | Off-by-one, inverted condition, missing early return |
| Type safety | Types match across call chain | Wrong type used, missing union member, `any` where concrete type exists |
| Async correctness | `await` on all coroutines, proper task management | Fire-and-forget coroutine, missing `await`, shared mutable state across tasks |
| Error handling | Errors caught at correct level, meaningful messages | Bare `except`, swallowed exception, debug trace in user-facing path |

## 2. Safety

| Criterion | Pass | Needs Fix |
|-----------|------|-----------|
| Auth check | Every mutation endpoint checks permissions | Missing permission decorator, user ID from URL not verified |
| Input validation | Boundary validation matches the project's contracts | Raw user input passed to query, missing required bounds |
| Data leakage | No PII in logs, error messages, or responses | Stack trace in response, email in log, internal ID exposed |
| Money path | Payment/balance operations idempotent | Race condition on balance update, no rollback on failure |

## 3. Patterns

| Criterion | Pass | Needs Fix |
|-----------|------|-----------|
| Project conventions | Follows root AGENTS.md and routed project patterns | Violates a declared interface or framework convention |
| File organization | Responsibilities and boundaries are coherent | Mixed concerns that create a concrete maintenance or correctness risk |
| Naming | Self-documenting names | Cryptic abbreviation, hungarian notation, misleading name |

## 4. Coverage

| Criterion | Pass | Needs Fix |
|-----------|------|-----------|
| Declared test policy | Required tests and focused acceptance evidence exist | A required test or acceptance check is missing |
| Edge cases | Relevant boundary/failure cases have evidence proportional to risk | A critical reachable failure lacks required coverage |
| Existing evidence | Task acceptance is established; omissions are honestly recorded | Evidence is missing, unsound, or broken by the change; omission is presented as a pass |

Read the task's `test:` tag, project/user testing requirements, and configured
test policy. Ordinary `test: no` work may pass using existing focused checks or
other declared evidence; do not demand a new test per function or UI component.
Required critical tests and human gates remain mandatory.

## 5. Scope

| Criterion | Pass | Needs Fix |
|-----------|------|-----------|
| File boundary | Only declared files touched | Drive-by refactor in unrelated file, formatting-only diff in untouched module |
| Side effects | No hidden config changes | Log level changed, feature flag toggled, import reorder in unrelated file |

## Evidence rules

- Cite a file and line for every issue when the target is line-addressable.
- Explain the reachable failure or violated contract; style preference alone is
  not a correctness finding.
- Review the declared scope and focused verifier. Do not require a broad suite
  or build as a task/phase gate.
- `BASELINE_RED` and `BROAD_VERIFY_OMITTED` are not review failures without
  causal evidence that the change is unsafe.
- A suggested fix describes remediation. It does not grant permission to edit.
