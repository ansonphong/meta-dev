# Loop-Gap Config Generation

How `/meta-planner` generates the loop-gap scan config — the file `/loop-gap` reads to know what to scan.

**Where it goes** is the `loop-gap-config` row of **`references/plan-artifacts.md`**: directory plan → `<plan-dir>/.loop-gap-config.md` (dot-prefixed, hidden inside the dir); **single-file plan → `<plan-stem>.loop-gap-config.md`**, a sibling carrying the plan's full stem. Never at the plans root — an orphan config names no plan.

## Config sections (all mandatory)

### Scan Settings
```yaml
mode: plan
target: <plan-directory>
plan_date: <YYYY-MM-DD>
git_baseline: <SHA>   # VERIFY at generation: run `git -C <repo> rev-parse HEAD` and paste the REAL current SHA.
                      # A stale/fabricated SHA silently breaks staleness detection (loop-gap diffs against it).
                      # The Phase 0 re-anchor re-checks at execute time, but the authored baseline must be current.
```

### Codebase Verification Targets
Table of files the plan references, their action (Create/Modify/Test), and the signature snapshot captured during Stage 1.5.

### Affected Files
Files NOT in the plan that import/call plan-modified code. From grep during Stage 1.5.

### Verification Hooks Summary
Count table: per-phase pre-hooks and post-hooks.

### Role Agent Focus Areas
Specific, non-generic guidance for each role agent (Implementer, Tester, Consumer) about what to watch for.

### Gap Categories to Prioritize
Ordered list based on plan characteristics. Template-heavy → prioritize codebase_mismatch, stale_assumption. New APIs → prioritize contract, test_validity, import_chain.

## Integration with loop-gap

The generated `.loop-gap-config.md` is read by `/loop-gap` at scan start. No other coupling. See `references/loopgap-integration.md` for what loop-gap does with it.
