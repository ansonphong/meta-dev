---
name: repair-loop
description: Attempt auto-fix with 3-attempt cap, smallest-fix-first strategy, failure dossier to inbox. Use when verify step fails.
---

# Repair Loop

3 attempts max. Smallest fix first. Dossier on exhaustion.

## Procedure

1. Read failure output (from test failure, lint error, crash trace, review finding)
2. Attempt 1: smallest fix (single regex, typing hint, missing import)
3. Re-run verify. If pass → commit + resolve.
4. If fail → Attempt 2: moderate fix (restructure function, add null check, fix logic)
5. Re-run verify. If pass → commit + resolve.
6. If fail → Attempt 3: structural fix (refactor, add missing class/interface)
7. Re-run verify. If pass → commit + resolve.
8. If fail → write failure dossier to inbox as advisory (per `references/failure-dossier.md`)

## Rules

- Each attempt must be DIFFERENT from prior attempts (no retry with same approach)
- After each attempt, re-run the EXACT same verify command
- If a different error appears (new failure, no regression), that resets the attempt counter
- 3 consecutive failures on the same error → dossier and stop
- Destructive operations (rm, drop, force-push) → never attempt; convert to advisory immediately

## Supported Verify Triggers

- Test failure (`pytest`, `vitest`)
- Lint error (`eslint`, `shellcheck`)
- Type error (`mypy`, `pyright`, `svelte-check`)
- Review finding (`code-review-protocol` output)
- Build failure (Vite, tsc, bundler)
