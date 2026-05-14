# Versioning Strategies

## Semver — `major.minor.patch`

Default. Follows conventional-commits semantics.
- breaking change → major
- new feature → minor
- bug fix / chore → patch

Updates script: Regex-replace in `version_files`.

## Calver — `YYYY.MM.patch`

Date-based. Patch resets monthly.
- `2026.05.1` → `2026.05.2` (same month, build 2)
- `2026.05.2` → `2026.06.1` (new month, patch resets)

Updates script: Computes from current date.

## Custom — `script:./path/to/script.sh`

Any arbitrary versioning logic. Provide executable that:
- Takes `--current <version>` and `--type major|minor|patch`
- Prints new version to stdout

Example:
```json
{
  "strategy": "custom",
  "custom_script": "scripts/version-custom.sh"
}
```
