# Tool Allowlists

Headless workers start at Tier 1. Escalate only when the task requires it.

## Tier 1 — Read-Only (default)

```json
{
  "allowedTools": ["Bash", "Read"],
  "Bash": {
    "allow": [
      "cat", "head", "tail", "grep", "find", "ls", "wc",
      "sort", "uniq", "diff", "echo", "printf", "date",
      "jq", "pwd", "which", "file", "stat", "du", "df",
      "git diff", "git show", "git log", "git status",
      "npm ls", "pip list"
    ]
  }
}
```

**Use when:** simple query, log inspection, status check, code reading.

## Tier 2 — Read + Write Files

```json
{
  "allowedTools": ["Bash", "Read", "Write", "Edit"],
  "Bash": {
    "allow": ["*"]
  }
}
```

**Use when:** generating files, fixing lint, running tests that write output.

## Tier 3 — Full Access

```json
{
  "allowedTools": ["Bash", "Read", "Write", "Edit"],
  "Bash": {
    "allow": ["*"]
  }
}
```

Plus explicit git commit/push permission in the task prompt.

**Use when:** auto-fix agent in repair-loop, code review fix agent, changelog cut that bumps and tags.
