# Versioning Config

Schema: `plugins/meta-dev/schemas/versioning.schema.json`
Template: `plugins/meta-dev/templates/versioning.json`

## Structure

```json
{
  "strategy": "semver",
  "repos": [
    {
      "id": "my-api",
      "name": "My API",
      "current_version": "0.1.0",
      "version_files": ["backend/pyproject.toml", "backend/app/__init__.py"],
      "git_tag_prefix": "api-v",
      "follows": null,
      "follows_mode": "patch",
      "independent": false
    }
  ]
}
```

## Fields

- `strategy`: semver, calver, or custom
- `repos[].current_version`: current semver string
- `repos[].version_files`: glob paths to files containing version strings
- `repos[].git_tag_prefix`: prefix for git tag (e.g. "v", "api-v-")
- `repos[].follows`: upstream repo id for cascade bumps
- `repos[].follows_mode`: bump type when following (major|minor|patch)
- `repos[].independent`: if true, exempt from cascade

## CLI Integration

- `/meta-version status` — read and display versions
- `/meta-version bump --type patch` — bump and tag
- `/meta-version sync` — detect/fix drift between versioning.json and files
