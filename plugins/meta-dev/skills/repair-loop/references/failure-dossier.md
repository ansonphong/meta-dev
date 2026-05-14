# Failure Dossier

Generated when repair-loop exhausts 3 attempts. Written to inbox as advisory.

## Format

```json
{
  "dossier": {
    "task_id": "<task-id>",
    "error_type": "test|lint|type|review|build",
    "original_error": "exact error output",
    "attempts": [
      {
        "attempt": 1,
        "approach": "Fixed missing import",
        "result": "Still failing: same error"
      },
      {
        "attempt": 2,
        "approach": "Restructured function logic",
        "result": "New error: type mismatch in helper"
      },
      {
        "attempt": 3,
        "approach": "Added null guard + type annotation",
        "result": "Still failing: same error"
      }
    ],
    "confidence": 0.3,
    "recommendation": "Requires deeper understanding of the module's data flow. Consider opus-level review or manual investigation.",
    "suggested_action": "Surface to user as advisory for manual triage"
  }
}
```

## Fields

| Field | Description |
|-------|-------------|
| `task_id` | Which task failed |
| `error_type` | Category of failure |
| `original_error` | Exact failure output (first occurrence) |
| `attempts` | Array of what was tried, what happened |
| `confidence` | 0.0–1.0 — how confident we are this is fixable with current approach |
| `recommendation` | What to do next (human review, opus analysis, upstream fix) |
| `suggested_action` | concrete next step |
