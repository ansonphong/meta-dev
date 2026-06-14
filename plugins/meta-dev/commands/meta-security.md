---
name: meta-security
description: Security audit — OWASP Top 10 + STRIDE threat modeling with parallel agent swarm, confidence-gated findings
argument-hint: "[<repo> | <path>] [--scope auth|payment|all] [--fix]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /meta-security

OWASP Top 10 + STRIDE audit run as a parallel agent swarm. Findings are gated at confidence ≥ 0.8 (false positives waste dev time and erode trust). Project-specific security boundaries are pulled from config / host CLAUDE.md, never hardcoded.

Full protocol: `references/security-audit-protocol.md`.

## Arguments

Input is `$ARGUMENTS`.

- `<repo>` — a repo/subdir name → audit that repo
- `<path>` — a file or directory glob → audit those files
- `--scope auth|payment|all` — phase-group filter (default `all`)
- `--fix` — apply + re-verify fixes for CRITICAL/HIGH findings at confidence ≥ 0.9
- *(no args)* — auto-detect from `git diff --name-only HEAD~5..HEAD`

`--scope` phase-groups: `auth` → phases 1,2,6 · `payment` → phases 1,4,8 · `all` → phases 1–9. Project critical invariants run under **every** scope.

## Flow

Execute the protocol in `references/security-audit-protocol.md`:

1. **Step 0** — parse args; load confidence gate (`bash scripts/config-get.sh meta_dev.security.confidence_threshold`, default 0.8).
2. **Step 0.5** — read this protocol's `## Learned Patterns`; fold active patterns into the relevant phases.
3. **Step 1** — determine scope; honor the meta-eval cache dedup contract (`.claude/cache/input-validation-report.json`).
4. **Step 2** — dispatch the in-scope phases as parallel grouped agents; also run the **Always-Checked Critical Invariants** (from `bash scripts/config-get.sh meta_dev.security.always_checked_invariants` or host CLAUDE.md) regardless of scope. Tier per group from `meta_dev.security.model_tiers`; money-path + crypto escalate to opus.
5. **Step 3** — apply confidence gate, dedup (same file + same vuln type), severity-sort.
6. **Step 4** — write the report to `{plans_root}/meta/security-audit-{date}.md` and refresh `.claude/cache/input-validation-report.json`. Verdict: any CRITICAL → FAIL.
7. **Step 5** — self-improving detection: if a vuln class recurs across 3+ past audits, append an LP entry.
8. **Step 6** — if `--fix`: apply fixes ≥ 0.9 confidence, re-run the producing phase, report before/after.

A single **opus findings-synthesis agent** merges all phase output, applies the gate, and emits the verdict (PASS | CONDITIONAL PASS | FAIL).

## When to Use

- **Stage 6 of /meta-dev** — conditional on changed files matching security-sensitive patterns (auth, payment/webhooks, crypto/keys, uploads, dependency manifests).
- **Standalone** — any repo or path.
- **After dependency updates** — re-run supply-chain phase.

Config: `bash scripts/config-get.sh meta_dev.security.*` for threshold, invariants, scopes, and model tiers.
