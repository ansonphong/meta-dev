---
stage: 5
repo: app
status: completed
---
# Mini plan — completed≠done regression fixture

A stage-5 plan whose EXECUTION boxes are all done but whose frontmatter still
carries the legacy `status: completed` (the pre-M1 world). Derivation must yield
`needs-review`, NOT `done` — the bug that read 0% on the control plane.

## Build

- [x] `T1.1` Wire the parser #a1b2
- [x] `T1.2` Wire the derive interpreter #c3d4
- [x] `T1.3` Golden-table test #e5f6

## Acceptance

- [ ] Verify the render by eye
