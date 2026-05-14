# Changelog Engine

## Files

- Active: `plans/_archive/changelogs/<since>--present.md`
- Closed: `plans/_archive/changelogs/<since>--<until>-<sha>-<slug>.md`

## Entry Format

```
-[`tag`] **Title** — Body (`sha7`)
```

Tags: `feat`, `fix`, `chore`, `breaking`, `docs`, `perf`, `refactor`, `test`, `auto`

## Auto-Cut

Trigger: manual (`/meta-changelog cut`), weekly cron, N entries threshold, or before deploy.

Bump logic:
- Any `[breaking]` entry → major
- Any `[feat]` entry → minor
- Else → patch

## Release Post

Drafted by haiku from closed period file. Optional publish to configured target (e.g., project social account).
