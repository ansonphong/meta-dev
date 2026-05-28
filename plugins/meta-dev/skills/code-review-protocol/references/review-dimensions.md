# Review Dimensions — Detailed Rubric

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
| Input validation | Pydantic/schema validation on all public inputs | Raw user input passed to query, missing length limit |
| Data leakage | No PII in logs, error messages, or responses | Stack trace in response, email in log, internal ID exposed |
| Money path | Payment/balance operations idempotent | Race condition on balance update, no rollback on failure |

## 3. Patterns

| Criterion | Pass | Needs Fix |
|-----------|------|-----------|
| Project conventions | Follows CLAUDE.md patterns | Deep import not used, wrong component pattern, old svelte 4 syntax |
| File organization | Single responsibility per file | Mixed concerns, utility sprawl, >400 line module |
| Naming | Self-documenting names | Cryptic abbreviation, hungarian notation, misleading name |

## 4. Coverage

| Criterion | Pass | Needs Fix |
|-----------|------|-----------|
| New code tested | Corresponding tests added | No tests for new functionality |
| Edge cases | null/empty/unauthorized tested | Only happy path covered |
| Existing tests pass | Full suite green | Tests broken by change |

## 5. Scope

| Criterion | Pass | Needs Fix |
|-----------|------|-----------|
| File boundary | Only declared files touched | Drive-by refactor in unrelated file, formatting-only diff in untouched module |
| Side effects | No hidden config changes | Log level changed, feature flag toggled, import reorder in unrelated file |
