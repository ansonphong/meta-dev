---
name: code-review-protocol
description: Structured code review across 5 dimensions — correctness, safety, patterns, coverage, scope. Verdict-routed to auto-fix or surface.
---

# Code Review Protocol

Five-dimension review. Input: diff, list of changed files. Output: verdict + routing.

## Dimensions

1. **Correctness** — Does it work? Logic errors, race conditions, off-by-one, type mismatches.
2. **Safety** — Edge cases, auth bypass, data leakage, injection, money-path errors.
3. **Patterns** — Follows project conventions? Naming, error handling, logging, module structure.
4. **Coverage** — Tests added/updated? Edge cases covered? Snapshot drift explained?
5. **Scope** — Touches only declared files? No drive-by changes.

See `references/review-dimensions.md` for full rubric.

## Procedure

1. Load changed files and diff
2. Score each dimension: pass / needs_fix / needs_review
3. Map to action per `references/verdict-routing.md`
4. If `needs_fix` with suggested fix → dispatch fix-agent per routing table
5. If `needs_review` → write finding to inbox

## Verdict

| Verdict | Meaning |
|---------|---------|
| pass | No issues found |
| needs_fix | Specific fixable issue (with suggested change) |
| needs_review | Structural concern, needs human judgment |
