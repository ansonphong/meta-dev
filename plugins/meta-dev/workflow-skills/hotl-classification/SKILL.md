---
name: hotl-classification
description: Classify tasks as HOTL-safe (auto-execute) or HITL-required (human gate) by blast radius. Use before dispatching plan execution.
---

# HOTL Classification

Given a task or plan, classify each task. Output JSON.

## Procedure

1. For each task in input:
   - Identify blast radius (read `references/blast-radius.md`)
   - Apply rules: payments/auth/migrations/deletion/email → HITL high; API/auth-adjacent/cross-module → HOTL moderate; docs/UI copy/isolated tests → HOTL low
2. Read `plans/_dashboard/settings.json` → `meta_dev.gates` for routing config
3. Output JSON per `references/output-format.md`

## Stop Conditions
- Ambiguous task → mark `needs_clarification`, never guess
- Mixed blast radius → split task before classifying
