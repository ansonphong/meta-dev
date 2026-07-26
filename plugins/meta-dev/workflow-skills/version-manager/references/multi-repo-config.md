# Multi-Repo Config

Stored in `plans/_dashboard/versioning.json`.

## Example

```json
{
  "repos": [
    {
      "id": "my-api",
      "path": "/opt/my-project/backend",
      "strategy": "semver",
      "version_files": [
        "backend/pyproject.toml",
        "backend/app/__init__.py"
      ],
      "follows": null,
      "follows_mode": "patch",
      "independent": false
    },
    {
      "id": "my-web",
      "path": "/opt/my-project/frontend",
      "strategy": "semver",
      "version_files": [
        "frontend/package.json"
      ],
      "follows": "my-api",
      "follows_mode": "minor",
      "independent": false
    },
    {
      "id": "docs",
      "path": "/opt/my-project/docs",
      "strategy": "calver",
      "version_files": [
        "docs/conf.py"
      ],
      "follows": null,
      "independent": true
    }
  ]
}
```

## Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | YES | Unique repo identifier |
| `path` | YES | Absolute path on disk |
| `strategy` | YES | `semver`, `calver`, or `custom` |
| `version_files` | YES | Files to update with new version |
| `follows` | NO | Upstream repo id this depends on |
| `follows_mode` | NO | `major`, `minor`, `patch` — cascade scope |
| `independent` | NO | If true, never auto-bumped by cascade |
