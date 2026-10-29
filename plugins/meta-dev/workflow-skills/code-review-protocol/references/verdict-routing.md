# Verdict Routing

Maps the structured review verdict to a report action. Review/audit is
report-only absent existing scoped implementation authority or explicit `--fix`.

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
   result states. Check intended valid behavior and the relevant refusal behavior;
   retain still-applicable green evidence from unchanged scope.
4. Stage exact paths and create a scoped commit if files changed, including
   on a red result.
5. Re-review the fixes, affected behavior, and integration seams; carry forward
   unresolved findings. Reuse evidence for unchanged clean dimensions. Broaden
   review only when changed contracts invalidate that evidence, and name the
   changed contract and why each added scope was affected. Emit and validate a
   new structured verdict.

Auth, money, migrations/schema, destructive changes, and cross-repo contracts
retain their explicit authority gates; existing authority counts. Authorization
cannot be inferred from
severity, confidence, fix complexity, or a suggested fix.

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
      "failure_path": "entry point → changed contract → observed failure",
      "violated_requirement": "specific requirement or invariant",
      "missing_evidence": "specific proof needed to accept or dismiss the finding",
      "suggested_fix": "specific remediation"
    }
  ],
  "summary": "concise result"
}
```

Final acceptance adds `"reviewed": {"base_ref": "<full SHA>",
"target_ref": "<full SHA>", "scope": ["path/to/file.py"],
"integration_reviewed": true}` to the single verdict. Ordinary task reviews
and batch rendering do not require this final-acceptance field.

`PASS` means no substantive issue. `CONDITIONAL_PASS` means bounded,
non-critical issues with a safe disposition. `FAIL` means a critical/high issue
or an unresolved concern that makes acceptance unsafe. Zero issues is valid.

## Validation and final plan acceptance

Validate structured output with `scripts/review-batch-render.py --validate-only`
before recording a pass. It accepts one verdict or a `{"reviews": [...]}` batch;
invalid output leaves acceptance pending. For a final planctl PASS, retain one
verdict per source repository with full baseline/target SHAs, every exact scoped
file and `integration_reviewed: true` only after inspecting the completed joins.

```bash
bash ${PLUGIN_ROOT}/scripts/planctl.sh review <plan-file> pass --by <reviewer> \
  --repo-root <absolute-source-repo> --base-ref <start-sha> --target-ref <reviewed-sha> \
  --scope <repo-relative-file> --scope <another-file> --verdict-file <single-pass-json>
```

Scoped working contents must match the reviewed commit. Planctl validates refs,
file content, plan contract and integration coverage; ledger-only commits do not
invalidate that evidence. Old unbound PASS events need a covering review. Keep
aggregate completion open when a single-repository verdict cannot cover a
cross-repository run; retain separate covering verdicts per repository. A partial
phase PASS never substitutes for final integration acceptance.
