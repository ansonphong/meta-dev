# Output Format

Classify tasks as a JSON array. Each entry:

```json
{
  "tasks": [
    {
      "id": "task-1",
      "title": "Add payment intent endpoint",
      "blast_radius": "high",
      "classification": "hitl",
      "confidence": 0.95,
      "reasoning": "Monetization path — payment charge creation. Requires human audit per the host project's CLAUDE.md policy."
    },
    {
      "id": "task-2",
      "title": "Update privacy policy link",
      "blast_radius": "low",
      "classification": "hotl",
      "confidence": 1.0,
      "reasoning": "UI copy change only. No logic or data mutation."
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Task identifier from input |
| `title` | string | Short task description |
| `blast_radius` | string | One of: `low`, `moderate`, `high` |
| `classification` | string | One of: `hotl` (auto-execute), `hitl` (human gate), `needs_clarification` |
| `confidence` | number | 0.0–1.0 confidence in classification |
| `reasoning` | string | Why this classification was chosen |
