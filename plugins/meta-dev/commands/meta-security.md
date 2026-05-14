---
name: meta-security
description: Security audit — OWASP Top 10 + STRIDE threat modeling with parallel agent swarm, confidence-gated findings
argument-hint: [<path> | "full"] [--fix]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-security

OWASP Top 10 + STRIDE audit. Parallel agents per audit phase, confidence gate >= 0.8 for findings.

## Phases

1. Secrets archaeology (credentials in code/git)
2. Authentication & session audit (JWT, cookies, CSRF)
3. Input validation (SQLi, XSS, path traversal, SSRF) — dedup with meta-eval cache
4. Payment security (Stripe, webhooks, atomic balance ops)
5. Supply chain (dependency audits)
6. Authorization (IDOR, roles, visibility enforcement, rate limits)
7. Data exposure (error responses, debug mode, headers)
8. Cryptographic review (key storage, token generation, password hashing)
9. Infrastructure (CORS, CSP, TLS, HSTS)

Output: `plans/meta/security-audit-{date}.md`. With `--fix`, applies HIGH+ confidence >= 0.9 fixes.
