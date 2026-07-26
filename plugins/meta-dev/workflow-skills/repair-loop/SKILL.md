---
name: repair-loop
description: Attempt auto-fix with 3-attempt cap, smallest-fix-first strategy, failure dossier to inbox. Use when verify step fails.
---

# Repair Loop

3 attempts max. Smallest fix first. Dossier on exhaustion.

## Procedure

1. Read failure output (from test failure, lint error, crash trace, review finding)
2. Attempt 1: smallest fix (single regex, typing hint, missing import)
3. Re-run verify. If pass → exact-path local commit + resolve.
4. If fail → Attempt 2: moderate fix (restructure function, add null check, fix logic)
5. Re-run verify. If pass → exact-path local commit + resolve.
6. If fail → Attempt 3: structural fix (refactor, add missing class/interface)
7. Re-run verify. If pass → exact-path local commit + resolve.
8. If fail → exact-path local commit of the final attempt, then write the
   failure dossier to inbox as advisory (per `references/failure-dossier.md`)

## Rules

- Each attempt must be DIFFERENT from prior attempts (no retry with same approach)
- After each attempt, re-run the EXACT same verify command
- If a different error appears (new failure, no regression), that resets the attempt counter
- 3 consecutive failures on the same error → dossier and stop
- Persistence and acceptance are separate: before every return after editing,
  stage only the declared files and create a local commit. A red commit does
  not resolve the repair; it preserves the attempt before the dossier/STOP.
- Never push from the repair worker; the conductor owns the remote and pushes
  only after green verification.
- Destructive operations (rm, drop, force-push) → never attempt; convert to advisory immediately

## Supported Verify Triggers

- Test failure (`pytest`, `vitest`)
- Lint error (`eslint`, `shellcheck`)
- Type error (`mypy`, `pyright`, `svelte-check`)
- Review finding (`code-review-protocol` output)
- Build failure (Vite, tsc, bundler)
