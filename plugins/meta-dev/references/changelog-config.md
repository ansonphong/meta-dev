# Changelog Config

Schema: `plugins/meta-dev/schemas/changelog.schema.json`
Template: `plugins/meta-dev/templates/changelog.json`

## Structure

```json
{
  "dir": "plans/_archive/changelogs",
  "active_file": "plans/_archive/changelogs/2026-05-11--present.md",
  "auto_add": true,
  "auto_cut_threshold": 50,
  "tag_vocabulary": ["feat", "fix", "chore", "breaking", "docs", "perf", "refactor", "test", "auto"],
  "release_post_target": "@my-project"
}
```

## Fields

- `dir`: changelog directory
- `active_file`: current active period file
- `auto_add`: auto-append entries on commit
- `auto_cut_threshold`: auto-cut when entry count exceeds this
- `tag_vocabulary`: allowed entry tags
- `release_post_target`: where to publish closed period summaries

## CLI Integration

- `/meta-changelog add --tag feat --title "..." --body "..."`
- `/meta-changelog cut` — close active period, start new
- `/meta-changelog status` — entry counts and suggested bump
