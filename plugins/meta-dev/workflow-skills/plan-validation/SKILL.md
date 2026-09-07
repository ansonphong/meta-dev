---
name: plan-validation
description: Judgment-based plan quality checks — cross-reference integrity, dependency ordering, contract completeness, terminology consistency
---

# Plan Validation Skill

Run the renderer and planner validator first; do not repeat passing deterministic checks. This pass evaluates whether the plan actually meets the request.

## Checks

1. **Cross-reference integrity** — Use deterministic validator evidence for handle/ledger consistency; inspect only unresolved semantic cross-references.

2. **Dependency ordering** — Use renderer dependency validation; judge whether any real producer/consumer dependency was omitted.

3. **Contract completeness** — For every API endpoint in the design doc, is there a corresponding implementation task? For every user-visible behavior, is there focused acceptance evidence consistent with the declared test policy? Do not require a test per UI component.

4. **Terminology consistency** — Are naming conventions consistent across all files? Use the project's naming conventions, without assuming a language or test framework.

5. **File path accuracy** — Do all file paths in the plan match actual project structure? Any stale paths from renames?

6. **Checker completeness** — Does every Verify-After command test what it claims to test? No verification commands that always pass.

7. **Focused verification** — Does every automated Verify-After name one test
file/node or explicitly scoped declared-file check? Reject bare/directory pytest,
`-k` without a file, package-wide npm/Vitest/Jest, `npm run check`,
`svelte-check`, project-wide `tsc`, builds, and full suites anywhere in the
execution plan, including phase-end acceptance. Broad release checks belong to
CI/ship, not `/meta-execute`. Critical-risk tasks must name a focused verifier
or an explicit human gate.

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

### Verification Scope
- [ finding ]

## Summary
- Errors: N | Warnings: M
```
