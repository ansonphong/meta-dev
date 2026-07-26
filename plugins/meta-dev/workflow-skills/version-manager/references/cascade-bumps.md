# Cascade Bumps

When a repo bumps, its downstream followers auto-bump per configuration.

## Cascade Rules

1. **Direction:** upstream → downstream only. If `my-api` bumps and `my-web` follows it, the web repo bumps after the API.
2. **Scope:** controlled by `follows_mode`:
   - `major` — downstream always bumps at same level as upstream
   - `minor` — downstream bumps minor (or patch) but never major
   - `patch` — downstream bumps patch only
3. **Independent repos** (`independent: true`) are skipped during cascade.
4. **Order:** topological sort by `follows` graph. Cycles blocked by validation.

## Example Cascade

```
my-api bumps v2.3.0 → minor
  └── my-web follows_mode=minor → bumps v1.8.0
       └── my-admin follows_mode=patch → bumps v0.5.1
```

## Edge Cases

| Situation | Behavior |
|-----------|----------|
| Upstream bumps major, downstream follows_mode=patch | Downstream bumps patch only |
| Circular follows | Validation error at config load |
| Missing upstream | Cascade skipped, warning logged |
| Multiple followers | All bumped in parallel (order doesn't matter at same depth) |
