# Security Audit Protocol — OWASP Top 10 + STRIDE

The full protocol behind `/meta-security`. Nine parallel audit phases, confidence-gated findings, project-parameterized critical invariants, and a self-improving detection loop. The command file (`commands/meta-security.md`) stays thin and links here.

This protocol is **stack-agnostic**. It carries generic OWASP/STRIDE checks for any web/API codebase, and pulls all project-specific security boundaries (license schemes, cross-domain cookies, payment providers, upload rules) from the host project rather than hardcoding them. See "Always-Checked Critical Invariants" below.

---

## Step 0: Parse Arguments & Confidence Gate

Input is `$ARGUMENTS`.

1. **`<repo>`** — a repo/subdir name from `meta_dev.paths.plan_subdirs` (or the host's repo map) → audit that repo.
2. **`<path>`** — a directory or file glob → audit those files.
3. **`--scope auth|payment|all`** — restrict to a phase-group (see Scope Phase-Groups). Default `all`.
4. **`--fix`** — after the audit, apply fixes for CRITICAL/HIGH findings at confidence ≥ 0.9, then re-verify (see Step 6).
5. **No args** → auto-detect changed files via `git diff --name-only HEAD~5..HEAD` and scope to those.

**Confidence gate: report findings at confidence ≥ `meta_dev.security.confidence_threshold` (default 0.8) only.** Rationale: false positives are worse than a missed low-severity finding — they waste developer time and erode trust in the tool. A finding below threshold is dropped, not downgraded.

Read the threshold from config: `bash scripts/config-get.sh meta_dev.security.confidence_threshold`.

---

## Step 0.5: Read Learned Patterns

Before auditing, read this file's `## Learned Patterns` section (bottom). For each active pattern:

- If it extends a phase's checklist → fold the extra check into that phase.
- If it identifies a recurring vulnerability class → raise that check's priority and lower its evidence bar within the confidence gate.
- Record which patterns were active in the report's metadata (`Patterns active:` line).

Patterns are lazy-loaded: read only this command's section, not every command's.

---

## Step 1: Determine Scope

1. Repo/path provided → scope = that target.
2. `--scope` provided → run only that phase-group's phases.
3. Otherwise → `git diff --name-only HEAD~5..HEAD`, collect changed files.
4. Apply the scope filter to the target file set.

**meta-eval cache dedup contract:** If `/meta-eval` wrote `.claude/cache/input-validation-report.json` during the current review cycle, do **not** re-grep injection/XSS/path/SSRF in Phase 3 — cite that report's findings instead and note "deduped from meta-eval cache" in the report. Always write a fresh report to that cache path at the end of this run (see Step 4) so downstream consumers can dedup against it.

---

## Scope Phase-Groups

`--scope` maps to phase-groups so partial audits stay coherent:

| Scope | Phases run |
|-------|-----------|
| `auth` | 1 (secrets), 2 (auth/session), 6 (authorization) |
| `payment` | 1 (secrets), 4 (payment/licensing), 8 (crypto) |
| `all` (default) | 1–9 |

The Always-Checked Critical Invariants (below) run under **every** scope, including partial ones.

---

## Step 2: Launch Parallel Audit Phases

Dispatch the phases in the active scope as parallel agents, grouped to reduce dispatch overhead. Model tier per group comes from config (see Model-Tier Escalation). Default grouping:

- **Group A — identity:** Phase 2 (auth/session) + Phase 6 (authorization)
- **Group B — input/injection:** Phase 3 (input validation) + Phase 9 (infrastructure)
- **Group C — secrets/crypto/exposure:** Phase 1 (secrets) + Phase 7 (data exposure) + Phase 8 (crypto)
- **Group D — value paths:** Phase 4 (payment/licensing) + Phase 5 (supply chain)

### Phase 1: Secrets Archaeology

- Grep codebase for API keys, tokens, passwords, secrets hardcoded in source.
- Check git history (`git log -p -S<pattern>`) for accidentally committed secrets.
- Verify `.env` / secret files are gitignored.
- Hardcoded credentials vs environment-variable usage.
- No secrets in client-side code (compiled JS bundles, frontend components).

### Phase 2: Authentication & Session

- Session secret/signing key: sourced from env, sufficiently strong (not a literal/default; ≥ 32 bytes of entropy).
- Cookie flags: `Secure`, `HttpOnly`, `SameSite` set on session/auth cookies.
- Cross-domain / cross-subdomain cookie scoping correct (no over-broad `Domain=`).
- CSRF protection on all state-changing routes (token or equivalent).
- Password hashing: bcrypt/argon2/scrypt with an appropriate cost/work factor (not MD5/SHA1/unsalted).
- Rate limiting on login/auth/credential-reset endpoints.

### Phase 3: Input Validation

(Dedup with meta-eval cache per Step 1 if present.)

- SQL injection: parameterized queries / ORM only, no string-built SQL.
- XSS: user input escaped in templates (auto-escaping on); no unescaped sinks.
- Path traversal: upload/download paths sanitized, normalized, confined to a base dir.
- Command injection: no `os.system()`, no `subprocess.*(shell=True)`, no backtick exec with user input.
- Template injection: no `render_template_string()` (or equivalent) on user input.
- Deserialization: no `pickle.loads()` / `yaml.load()` (unsafe loader) / `eval()` on untrusted data.
- SSRF: outbound requests built from user input are allowlisted / validated.

### Phase 4: Payment & Licensing Security

- Payment-provider webhook signature verified on **every** webhook handler (not just one).
- Price/amount integrity: server-side lookup, never trust client-submitted amounts.
- License/entitlement issuance uses correct key management (signing key server-side only).
- License validation: signature verification + expiry + activation/seat limits enforced.
- Refund/chargeback handling does not leave entitlements active.
- Idempotency keys on payment-mutation endpoints (no double-charge / double-grant).

### Phase 5: Supply Chain

- Python deps: `pip-audit` (or check `requirements.txt`/lockfile against known CVEs).
- Node deps: `npm audit` (or check lockfile).
- Versions pinned to exact (or hash-locked) versions.
- Stale deps: anything > 1 year old with known CVEs.

### Phase 6: Authorization

- Endpoint access control: admin/privileged routes gated by role check.
- IDOR: can user A read/mutate user B's resources by changing an ID? Verify ownership checks.
- Privilege escalation: lower tier cannot reach higher-tier features/endpoints.
- API key / token scoping: least-privilege, not omnipotent.
- Inter-service token flows validate the **subject's ownership** of what the token grants.

### Phase 7: Data Exposure

- No stack traces / debug pages in production responses.
- Debug mode disabled in production (`DEBUG`/`FLASK_DEBUG`/equivalent off).
- No sensitive values (tokens, keys, PII) in logs.
- API responses don't leak internal fields (password hashes, internal IDs, raw model dumps).
- DB credentials / connection strings not surfaced in errors.

### Phase 8: Cryptographic Review

- Signature scheme implemented correctly (no nonce reuse, correct verify path).
- Private/signing keys stored server-side only, never in repo or client bundle.
- Public keys distributed/embedded correctly where verification happens.
- Token generation uses a CSPRNG (`secrets`, not `random`).
- TLS: minimum version enforced (≥ TLS 1.2), weak ciphers disabled.
- Password hashing cost/work factor appropriate (bcrypt ≥ 12, argon2 tuned).

### Phase 9: Infrastructure

- CORS: not `*` with credentials; allowlist explicit origins.
- CSP header defined and not trivially bypassable (`unsafe-inline`/`unsafe-eval` flagged).
- Rate limiting applied at the edge for auth + API endpoints.
- HTTPS enforced (HTTP→HTTPS redirect, HSTS).
- Security headers present: `X-Frame-Options`/frame-ancestors, `X-Content-Type-Options: nosniff`, `Strict-Transport-Security`.

---

## Always-Checked Critical Invariants (Project-Parameterized)

These run under **every** scope (including `--scope auth|payment`), regardless of which phases the scope selects. The always-on guarantee is fixed; the *content* is supplied by the host project, not hardcoded here.

**Resolution order:**

1. Read `bash scripts/config-get.sh meta_dev.security.always_checked_invariants` — a list of `{ id, description, check }` entries.
2. If empty/unset, extract security boundaries from root `AGENTS.md` and routed security/conventions context, following `references/host-project-contract.md`.
3. For each invariant, run the described check against the target and report violations through the same confidence gate and severity model as the numbered phases.
4. If a project defines none, run only the generic OWASP/STRIDE phases above and note "no project invariants configured" in the report.

**Example invariant shapes** (the host fills these in for its own stack — these are illustrative, not defaults to assume):

- Signature-based license keys verified offline; signing key server-side only.
- Cross-subdomain session isolation; one subdomain cannot impersonate another's session.
- Inter-service token flow validates the requester's ownership of the granted resource.
- Payment-provider webhook signature verified on every handler.
- File-upload paths sanitized against traversal.
- Auth / validation / submission endpoints rate-limited.

Never hardcode a specific project's domains, key schemes, or provider names in this file — pull them from config or the host project contract.

---

## Model-Tier Escalation

Read per-group tiers from `bash scripts/config-get.sh meta_dev.security.model_tiers`. Defaults:

| Phase group | Default model |
|-------------|--------------|
| Group A (identity) | sonnet |
| Group B (input/infra) | sonnet |
| Group C (secrets/crypto/exposure) | sonnet, **crypto (Phase 8) escalates to opus** |
| Group D (value paths) | **opus** (payment/licensing is money-path + entitlement) |
| Findings synthesis | **opus** verdict agent |

After the phase agents return, a single **findings-synthesis agent (opus)** merges results, applies the confidence gate + dedup + severity sort, and emits the verdict. Any CRITICAL finding forces a FAIL verdict (block).

---

## Step 3: Collect, Gate, Dedup, Sort

1. Collect findings from all dispatched phases + invariants.
2. **Confidence gate:** drop anything below threshold (default 0.8).
3. **Dedup:** same file + same vulnerability type = one finding (keep highest-confidence instance, merge line refs).
4. **Severity sort:** CRITICAL > HIGH > MEDIUM > LOW.

---

## Step 4: Generate Report

````markdown
# /meta-security Report — {Repo/Scope}

**Date:** {YYYY-MM-DD}
**Target:** {repo or path}
**Scope:** {auth | payment | all}
**Phases run:** {N}/9
**Patterns active:** {LP-NNN, … or "none"}
**Invariants checked:** {N project invariants | "none configured"}

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | N |
| HIGH | N |
| MEDIUM | N |
| LOW | N |
| **Total** | **N** |

## Critical Findings (must fix before deploy)

1. **[PHASE/INVARIANT]** Description
   - File: `path:line`
   - Confidence: 0.X
   - Fix: specific remediation

## High Findings (fix soon)
…

## Medium Findings (next sprint)
…

## Low Findings (informational)
…

## Passed Checks

- [x] No credentials in code or git history
- [x] Session configuration secure
- [x] {project invariant} enforced
- …

## Recommendation

**Status:** PASS | CONDITIONAL PASS (fix CRITICALs) | FAIL
````

Write the report to `{plans_root}/meta/{YYYY-MM-DD}-security-audit.md` (resolve `plans_root` from config). **Date leads** — see `references/plan-artifacts.md`; a trailing date scatters the series across the directory. Also write/refresh `.claude/cache/input-validation-report.json` with Phase 3 findings for downstream meta-eval dedup.

**Verdict rule:** any CRITICAL → FAIL. CRITICAL fixed but HIGH open → CONDITIONAL PASS. No CRITICAL/HIGH → PASS.

---

## Step 5: Self-Improving Detection

After the audit:

1. Find past reports: `find {plans_root} -name "security-audit-*" | head -10`.
2. If 3+ exist, tally vulnerability classes across them.
3. If the **same class appears in 3+ separate audits**, generalize it and append an LP entry to this file's `## Learned Patterns` (and, where relevant, to `meta-planner` / `loop-gap` references so the gap is caught upstream).
4. The detecting run records the new LP; it does not commit (the orchestrator/caller commits).

---

## Step 6: Apply Fixes (`--fix`)

If `--fix` was passed:

1. For each CRITICAL/HIGH finding at confidence ≥ 0.9, apply the smallest correct fix.
2. **Re-verify:** re-run the phase that produced the finding against the changed files.
3. Produce a before/after section: finding → fix → re-run result (resolved / still open).
4. Findings below 0.9, or any that fail re-verification, are surfaced unfixed for human review.

---

## When to Use

- **Stage 6 of /meta-dev** — conditional: trigger only when changed files match security-sensitive patterns (auth/, payment/, webhook handlers, crypto/key code, upload handlers, dependency manifests). Skip otherwise.
- **Standalone** — point at any repo or path.
- **After dependency updates** — re-run Phase 5.
- **With `--fix`** — apply + re-verify high-confidence fixes.

---

## Learned Patterns

<!-- Auto-maintained by the self-improving detection loop (Step 5). Generalized only — no project-specific entries. -->
<!-- Max 20 patterns. Append-only here — ONLY meta-audit removes/consolidates patterns. -->
<!-- A pattern qualifies only after the same vulnerability class appears in 3+ separate audits. -->

(No patterns yet. Patterns are added automatically when recurring vulnerability classes are detected across 3+ separate audits.)
