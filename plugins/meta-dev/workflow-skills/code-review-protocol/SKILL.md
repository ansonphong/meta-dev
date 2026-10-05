---
name: code-review-protocol
description: Structured, report-only review across correctness, safety, patterns, coverage, and scope with host-native reviewer routing.
---

# Code Review Protocol

Review is an evidence-producing operation, not standing permission to edit.
Read `../../references/workflows/protocol.md`, then review the requested diff
across the five dimensions below.

## Dimensions

1. **Correctness** — Does it work? Logic errors, race conditions, off-by-one, type mismatches.
2. **Safety** — Edge cases, auth bypass, data leakage, injection, money-path errors.
3. **Patterns** — Follows project conventions? Naming, error handling, logging, module structure.
4. **Coverage** — Declared test policy and acceptance evidence satisfied? Relevant failure cases covered?
5. **Scope** — Touches only declared files? No drive-by changes.

See `references/review-dimensions.md` for full rubric.

## Procedure

1. Resolve the declared scope, intent/spec, base ref, target ref, changed files,
   and focused outcomes. Compute the diff from refs when possible.
2. Read project instructions and every changed file needed to understand the
   diff. Do not widen into unrelated cleanup.
3. Inspect the full declared scope across all five dimensions before deciding
   the verdict. A blocking issue does not end the review. Report every distinct,
   evidence-backed, actionable issue found; do not invent issues to fill a list.
   If any declared scope could not be inspected, identify it and the reason in
   the summary, and score affected dimensions `NEEDS_REVIEW`.
4. Score each dimension `PASS`, `NEEDS_FIX`, or `NEEDS_REVIEW` using
   `references/review-dimensions.md`.
5. Emit the structured verdict below and route it through
   `references/verdict-routing.md`.
6. Stop. Only an explicit `--fix` or user go-word authorizes a separate
   remediation pass. A `NEEDS_FIX` score does not authorize edits or a commit.

## Verdict

```json
{
  "verdict": "PASS | CONDITIONAL_PASS | FAIL",
  "confidence": 0.9,
  "blast_radius": "isolated | file | module | cross-cutting | dependency-graph",
  "dimensions": {
    "correctness": "PASS | NEEDS_FIX | NEEDS_REVIEW",
    "safety": "PASS | NEEDS_FIX | NEEDS_REVIEW",
    "patterns": "PASS | NEEDS_FIX | NEEDS_REVIEW",
    "coverage": "PASS | NEEDS_FIX | NEEDS_REVIEW",
    "scope": "PASS | NEEDS_FIX | NEEDS_REVIEW"
  },
  "issues": [
    {
      "severity": "critical | high | medium | low",
      "file": "path",
      "line": 1,
      "title": "short title",
      "description": "evidence and impact",
      "suggested_fix": "specific remediation"
    }
  ],
  "summary": "concise result"
}
```

`PASS` means no substantive issue. `CONDITIONAL_PASS` means bounded,
non-critical issues with a safe disposition. `FAIL` means a critical/high issue
or an unresolved concern that makes acceptance unsafe. Zero issues is valid.

## Reviewer adapter

- Native Codex review defaults to the configured `gpt-6-sol`, high-effort
  route. Do not spawn an external reviewer unless the user explicitly selects
  one.
- Claude Code retains its command/agent/project reviewer configuration. The
  protocol does not declare a universal Opus reviewer.
- An external reviewer is an additional explicit lens. Record its identity and
  keep its evidence distinct from the native verdict.
