# Entry Format

Each entry is a single line in `<today>--present.md`.

## Format

```
<datetime>Z | <tag> | <title> [(ref:<sha>)]
```

## Tags

| Tag | Use When |
|-----|----------|
| `breaking` | Breaking API change, migration, config incompatibility |
| `feat` | New feature, endpoint, component |
| `fix` | Bug fix, hotfix |
| `docs` | Documentation, plan files, comments |
| `refactor` | Code restructure, no behavior change |
| `test` | Test addition or fix |
| `chore` | Deps, CI, lint, tooling, build |

## Examples

```
2026-05-12T10:30:00Z | feat | Add payment intent endpoint (ref:abc1234)
2026-05-12T11:15:00Z | fix | Correct account balance race condition (ref:def5678)
2026-05-12T14:00:00Z | docs | Update API reference for payment flow (ref:ghi9012)
```

## Body (Optional)

Multi-line entries attach a body block after the header line, indented by 2 spaces:

```
2026-05-12T10:30:00Z | feat | Add payment intent endpoint (ref:abc1234)
  Implements POST /api/v1/orders with the payment provider SDK.
  Configurable via plans/_dashboard/monetization.json.
```
