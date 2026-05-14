---
name: meta-classify
description: Invoke HOTL classification skill — categorize subjects by type, complexity, and risk
argument-hint: <subject-description>
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-classify

Invoke `hotl-classification` skill to categorize a subject by type (feature/bug/refactor/docs/infra), complexity (S/M/L/XL), and risk profile.

## Usage

The skill reads the subject description and returns structured classification:

- **Type** — feature / bug / refactor / docs / infra
- **Complexity** — S (<5 tasks) / M (5-15) / L (15-30) / XL (30+)
- **Risk profile** — picks up security-boundary, money-path, identity-stability tags
- **Recommended pipeline** — which stages of meta-dev to run

Detail: skill `hotl-classification` in `plugins/meta-dev/skills/hotl-classification/`.
