# Verdict Routing

Maps the structured review verdict to a report action. Review/audit is
report-only unless the user explicitly supplied `--fix` or a go-word.

## Routing Table

| Verdict | Default action | Mutation |
|---|---|---|
| `PASS` | Report acceptance evidence; record verdict when the owning workflow calls for it. | None |
| `CONDITIONAL_PASS` | Report each bounded issue and its disposition. | None |
| `FAIL` | Report blocking evidence and affected scope. | None |

Do not commit merely to "close review." Do not dispatch a fixer because a
dimension returned `NEEDS_FIX`. Inbox/state writes are separate workflow actions
and require their own scope or the owning conductor's explicit contract.

## Authorized remediation

When and only when explicit fix permission exists:

1. Emit and preserve the original review verdict.
2. Partition issues by causal branch and declared file scope.
3. Apply the smallest supported fix using the host-native executor. External
   fixers are explicit opt-ins.
4. Run the named focused verifier once. Classify it with the shared execution
   result states.
5. Stage exact paths and create one scoped commit if files changed, including
   on a red result.
6. Re-review the repaired diff and emit a new structured verdict.

Auth, money, migrations/schema, destructive changes, and cross-repo contracts
still require explicit confirmation. Authorization cannot be inferred from
severity, confidence, fix complexity, or a suggested fix.
