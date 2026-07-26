# Cut Workflow

Triggered by `/meta-changelog cut` or auto-threshold.

## Steps

1. **Read present.md** — Count entries per tag
2. **Compute bump type:**
   - Any `breaking` → major
   - Any `feat` → minor
   - Else → patch
3. **Generate identifiers:**
   - `short_id` = first 7 chars of `sha256sum <present.md>`
   - `slug` = hyphenated, from most prominent tag + count
4. **Rename:**
   - `plans/_archive/changelogs/<since>--present.md`
   - → `plans/_archive/changelogs/<since>--<until>-<short_id>-<slug>.md`
5. **Bootstrap:**
   - Create `plans/_archive/changelogs/<today>--present.md`
6. **Draft release post** (haiku-level model) from cut file
7. **Auto-bump version** via `scripts/version-bump.py --type auto`
8. **Optional publish** if `release_post_target` configured

## Config: `plans/_dashboard/changelog.json`

```json
{
  "auto_cut": "weekly",
  "auto_cut_threshold": 20,
  "auto_cut_schedule": "sun 23:00",
  "release_post_target": null,
  "publish_on_cut": false
}
```

| Field | Meaning |
|-------|---------|
| `auto_cut` | `manual` (default), `weekly`, `N_entries`, `before_deploy` |
| `auto_cut_threshold` | When `N_entries`, cut after this many entries |
| `auto_cut_schedule` | When `weekly`, cron-like schedule |
| `release_post_target` | Path or URL for release post output |
| `publish_on_cut` | Whether to auto-publish release post |
