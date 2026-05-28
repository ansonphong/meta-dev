# Guard Patterns — Destructive Command Detection + Freeze-Scope Protocol

## Destructive Patterns Reference Table

Commands that `/meta-guard` intercepts and blocks unless explicitly allowed:

| Pattern | Category | Default action | Override |
|---------|----------|---------------|----------|
| `rm -rf` (non-temp paths) | Destructive delete | BLOCK | User types "yes" in confirmation |
| `rm -rf .git/index` | Git corruption | BLOCK | NEVER overrideable — redirect to Windows fix |
| `git reset --hard` | Destructive git | BLOCK | User confirmation |
| `git checkout .` / `git restore .` | Working tree overwrite | BLOCK when uncommitted changes exist | User confirmation |
| `git push --force` | Force push | BLOCK on main/master | User confirmation |
| `git push --force` to non-main | Force push branch | WARN | --force-with-lease suggested |
| `git branch -D` | Branch delete | WARN | |
| `--no-verify` flag | Skip hooks | WARN | |
| `DROP TABLE` / `DROP DATABASE` | Database destruction | BLOCK | User confirmation |
| `chmod 777` | Permissions escalation | WARN | |
| `curl ... | bash` (untrusted URLs) | Remote execution | BLOCK | User confirmation |

## Freeze-Scope Protocol

When `/meta-guard freeze` is invoked:
1. Record the current directory as the `scope-root`
2. Any Edit/Write/Bash outside `scope-root` → BLOCK with message: "Edit outside frozen scope <scope-root>"
3. Any Bash command matching a destructive pattern → BLOCK
4. Unfreeze: `/meta-guard unfreeze`

## Meta-Dev Integration

During `/meta-execute`, meta-guard is active by default:
- Blocks destructive commands that could destroy uncommitted work
- Scope is the plan's declared file set (not the whole repo)
- Warnings for patterns that could affect parallel sessions

## Config

Read scope-root from `bash scripts/config-get.sh meta_dev.guard.scope_root` (default: repo root).
Destructive command categories can be tuned per project via `settings.json`.
