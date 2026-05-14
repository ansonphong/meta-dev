# Config Cascade

Three-layer deep merge. Later layers override earlier.

## Layers

1. **Defaults** (`plugins/meta-dev/templates/settings.json`) -- read-only, shipped with plugin
2. **Project** (`plans/_dashboard/settings.json`) -- committed, shared with team
3. **Local** (`plans/_dashboard/settings.local.json`) -- gitignored, per-machine

## Merge Rules

- Objects merge recursively (nested keys preserved)
- Scalars and arrays: later layer wins completely
- `null` in later layer: deletes key from merged output

## Schema Validation

Every write validates against `schemas/settings.schema.json`. Invalid writes rejected.

## When to Use Each Layer

| Layer | What goes there |
|-------|----------------|
| Local | Model overrides, personal refresh rates, machine-specific paths |
| Project | Team gates, changelog targets, versioning repos, inbox sources |
| Defaults | Never edit directly. Update via plugin version bumps. |

## Dot-Notation

`config-get.sh meta_dev.overlord.model` -> `"sonnet"`
`config-set.sh meta_dev.gates.high_risk gate_before_execute`
