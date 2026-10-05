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

1. Finish every commissioned review against the same declared scope and
   base/target refs before editing. Preserve each original verdict, merge
   duplicate findings, and triage the complete issue set. Record the disposition
   of findings that will remain unresolved.
2. Partition accepted fixes by causal branch and declared file scope. Apply the
   smallest supported fixes together within each branch using the host-native
   executor. External fixers are explicit opt-ins.
3. Run each branch's named focused verifier once. Classify it with the shared execution
   result states.
4. Stage exact paths and create a scoped commit if files changed, including
   on a red result.
5. Re-review the fixes, affected behavior, and integration seams; carry forward
   unresolved findings. Reuse evidence for unchanged clean dimensions. Broaden
   review only when changed contracts invalidate that evidence. Emit a new
   structured verdict.

Auth, money, migrations/schema, destructive changes, and cross-repo contracts
still require explicit confirmation. Authorization cannot be inferred from
severity, confidence, fix complexity, or a suggested fix.
