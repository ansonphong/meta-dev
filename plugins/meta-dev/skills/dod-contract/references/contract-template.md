# DoD Contract Template

```json
{
  "contract_id": "<task-id>",
  "task": "<task description>",
  "scope": {
    "included": ["file1.py", "file2.py"],
    "excluded": ["unrelated_module.py"]
  },
  "acceptance_criteria": [
    "AC1: <measurable condition>",
    "AC2: <measurable condition>"
  ],
  "test_plan": {
    "unit": ["pytest path/to/test -k test_name"],
    "integration": ["pytest path/to/integration -k test_name"],
    "e2e": ["bun run test:e2e -- --grep pattern"]
  },
  "rollback_plan": "git revert <sha> && redeploy",
  "blast_radius": "low|moderate|high",
  "verification_hooks": [
    "shellcheck <script>",
    "cd backend && pytest tests/ -v"
  ]
}
```

## Mandatory Sections

| Section | Required | Description |
|---------|----------|-------------|
| `scope.included` | YES | Files this task touches |
| `scope.excluded` | YES | Files intentionally NOT touched (boundary guard) |
| `acceptance_criteria` | YES | 2-5 measurable conditions of done |
| `test_plan` | YES | Commands to verify each criterion |
| `rollback_plan` | YES | How to undo if this goes wrong |
| `blast_radius` | YES | Must match HOTL classification |
| `verification_hooks` | YES | Pre-commit checks to run |

## Principle

Every contract must be falsifiable. If you cannot write a test command that proves the criterion is met, the criterion is not well-defined.
