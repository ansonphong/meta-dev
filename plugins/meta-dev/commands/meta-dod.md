---
name: meta-dod
description: Invoke DOD contract skill — define Definition of Done contract for a feature or task
argument-hint: <feature-or-task-description>
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /meta-dod

Invoke `dod-contract` skill to produce a Definition of Done contract for a subject.

## Output

Structured contract covering:

- **Acceptance criteria** — specific, testable conditions
- **Verification steps** — how to confirm each criterion is met
- **Quality gates** — tests, review, security checks that must pass
- **Exclusions** — explicit "not in scope" items
- **Dependencies** — what must exist before this can be done

Written to `plans/<feature>/dod-contract.md`.

Detail: skill `dod-contract` in `plugins/meta-dev/skills/dod-contract/`.
