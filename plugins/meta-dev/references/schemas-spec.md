# Schema Specifications

All schemas use JSON Schema draft-07. Files in `plugins/meta-dev/schemas/`.

## Settings Schema

Validates `plans/_dashboard/settings.json`. Controls all harness behavior.

Key sections:
- `meta_dev.components` -- enable/disable features
- `meta_dev.dashboard` -- dashboard behavior (auto-inject, refresh)
- `meta_dev.inbox` -- issue inbox configuration
- `meta_dev.overlord` -- overlord model, auto-fix, max loops
- `meta_dev.changelog` -- auto-add, auto-cut, version strategy
- `meta_dev.versioning` -- default strategy, git tag behavior
- `meta_dev.gates` -- risk-based gate routing (auto_execute | review_after | gate_before_execute)

## Versioning Schema

Multi-repo version tracking. Each repo has `id`, `name`, `current_version`, `version_files` (paths to update), optional `follows` (cascade from upstream).

## Changelog Schema

Active/closed period file paths, auto-cut config, tag vocabulary, release post settings.

## State Schema

Runtime state shape. `active_sessions`, `overlord` status, `sweep_log`, `recent_commits` (capped 50).

## Inbox Schema

Single issue/advisory item. Required: `id` (ULID, `inb_` prefix), `kind` (issue|advisory), `source`, `severity`, `title`, `status`, `created`. Advisory items have `awaits` + `options` (user-choice commands).
