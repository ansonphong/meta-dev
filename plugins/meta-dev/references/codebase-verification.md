# Codebase Verification Protocol

The Stage 1.5 ground-truth pass. Before writing any phase file, verify every file reference in the plan against the actual codebase.

## Step 1: Collect all file references

Scan the input plan for every path in:
- `- Files:` / `- Create:` / `- Modify:` / `- Test:` lines
- Code blocks (import statements, file paths in comments)
- Prose descriptions matching file-path patterns

Build a table: path | plan says | action | exists? | current signature

## Step 2: Read and verify each file

### For Modify/Test files (should exist):
1. Read the actual file
2. Extract function/class/method signatures the plan mentions
3. Compare against plan assumptions — note mismatches
4. Record current signature snapshot (embedded in phase files)

### For Create files:
1. Verify parent directory exists
2. Check for naming conflicts
3. Check import targets — will other files find this after creation?

### For Test files:
1. If exists: verify test class/function names plan references
2. If new: verify test framework matches project conventions

## Step 3: Check for plan staleness

```bash
git log --since=<PLAN_DATE> --name-only -- <FILES>
```

Files modified after plan date → flag as potentially stale. Read diffs to determine if assumptions hold.

## Step 4: Discover callers

```bash
grep -rn "from <module> import\|import <module>" --include="*.py" --include="*.ts" --include="*.svelte"
```

Record affected files — they may need updates not in the plan.

## Step 5: Resolve mismatches

- Wrong file path → fix in plan, document correction
- Wrong function signature → update plan to use actual signature
- Missing file → verify created by prior task, or flag as gap
- Stale assumptions → update plan to match current codebase
- Unaccounted callers → add to affected files list
