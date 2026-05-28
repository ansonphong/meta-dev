---
name: plan-validation
description: Judgment-based plan quality checks — cross-reference integrity, dependency ordering, contract completeness, terminology consistency
---

# Plan Validation Skill

Judgment checks that can't be scripted deterministically. Invoked by `/meta-planner` Stage 4.

## Checks

1. **Cross-reference integrity** — Do master plan task IDs match phase file task IDs 1:1? Are any tasks in master missing from phase files or vice versa?

2. **Dependency ordering** — Does the task order respect declared dependencies? Are there tasks whose `Depends on:` references a task that appears later in the sequence?

3. **Contract completeness** — For every API endpoint in the design doc, is there a corresponding implementation task? For every UI component, is there a corresponding test?

4. **Terminology consistency** — Are naming conventions consistent across all files? PascalCase classes, `Test` prefix, project file naming.

5. **File path accuracy** — Do all file paths in the plan match actual project structure? Any stale paths from renames?

6. **Checker completeness** — Does every Verify-After command test what it claims to test? No verification commands that always pass.

## Output Format

```markdown
## Plan Validation Report — <plan-name>

### Cross-Reference
- [ finding ]

### Dependency Ordering
- [ finding ]

### Contract Completeness
- [ finding ]

### Terminology
- [ finding ]

### File Paths
- [ finding ]

### Verification Soundness
- [ finding ]

## Summary
- Errors: N | Warnings: M
```
