---
name: changelog-engine
description: Batch engineering changelog. Append entries during work, cut on demand or auto-threshold, draft release post, pair with version bump.
---

# Changelog Engine

Active period file: `plans/_archive/changelogs/<since>--present.md`
Closed period: `plans/_archive/changelogs/<since>--<until>-<sha>-<slug>.md`

## Operations

- **add** → `scripts/changelog-add.sh --tag T --title T --body B`
- **cut** → `scripts/changelog-cut.sh`
  1. Read present.md, count by tag
  2. Auto-bump: any `breaking`→major, any `feat`→minor, else patch
  3. Generate slug + short_id
  4. Rename present.md → closed filename
  5. Bootstrap fresh `<today>--present.md`
  6. Draft release post (haiku) from cut file → `references/release-post-draft.md`
  7. Invoke version-bump.py with computed type
  8. Optional: publish to configured release_post_target

## Config

`plans/_dashboard/changelog.json` per `references/cut-workflow.md`.

## Auto-triggers

PostToolUse(git commit) hook calls `changelog-add.sh` if `auto_add_on_commit: true`.
Auto-cut: `manual` | `weekly` | `N_entries` | `before_deploy`.
