# Version Manager

## Config

`plans/_dashboard/versioning.json` — array of repos with version_files.

## Strategies

- **semver**: MAJOR.MINOR.PATCH
- **calver**: YYYY.MM.PATCH
- **custom**: script-defined

## Cascades

`follows` field: when upstream bumps, follower bumps by `follows_mode` (major|minor|patch).
`independent: true` opts out of cascade.

## Atomic Bump

1. Update versioning.json current_version
2. Update all version_files (package.json, pyproject.toml, etc.)
3. Git commit + tag
4. Cascade to followers
5. Push tags if configured
