# Verdict Routing

Maps review verdict to action. Input from code-review-protocol output.

## Routing Table

| Verdict | Fix Complexity | Action | Agent | When |
|---------|---------------|--------|-------|------|
| pass | — | Done. Commit + close review. | — | Always |
| needs_fix | trivial | Auto-fix and commit. | haiku | Single-line fix, typing hint, import add |
| needs_fix | moderate | Generate fix, apply, re-verify, commit. | sonnet | Logic fix, null guard, reorder, test add |
| needs_fix | structural | Write fix proposal to inbox as advisory. Do not auto-commit. | — | Refactor across modules, interface change |
| needs_review | — | Write finding to inbox as advisory with options. | — | Architecture concern, security uncertainty |

## Fix Complexity Heuristic

| Complexity | Signs | Max Changes |
|-----------|-------|-------------|
| trivial | 1-3 lines changed, single file, mechanical | 3 lines |
| moderate | 3-30 lines, 1-2 files, judgment needed | 30 lines |
| structural | 30+ lines, 3+ files, interface changes | Surface only |

## Auto-commit Rules

- Trivial + moderate fixes: commit directly (per #1 RULE standing auth)
- Structural fixes: NEVER auto-commit. Write to inbox.
- Money/auth/migration files: NEVER auto-commit regardless of complexity.
