---
name: version-manager
description: Multi-repo, context-aware versioning. Declarative config, semver/calver/custom strategies, follows cascades, atomic version_files updates.
---

# Version Manager

Config: `plans/_dashboard/versioning.json`. See `references/multi-repo-config.md`.

## Operations

- **status** → `scripts/version-status.sh [--repo id]`
- **bump** → `scripts/version-bump.py [--repo id] [--type major|minor|patch|auto]`
- **sync** → `scripts/version-sync.py [--repo id]` (drift fix)
- **config** → `/meta-config set versioning.repos[<i>].<field> <value>`

## Strategies

`references/strategies.md`: semver, calver, custom (script-based).

## Cascade

`follows` field → downstream bumps when upstream bumps. `follows_mode: major|minor|patch` controls scope.
`independent: true` → opt out of cascade.

## Auto-bump

When called by changelog-engine.cut, type = `auto`:
- Any `[breaking]` entry → major
- Any `[feat]` → minor
- Else → patch
