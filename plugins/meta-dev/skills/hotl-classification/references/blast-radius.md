# Blast Radius Criteria

Classify blast radius before dispatching. Higher blast radius → HITL gate required.

## Classification Table

| Blast Radius | Level | Examples | Gate |
|-------------|-------|----------|------|
| Payments / Monetization | HIGH | Account balances, payment charges, subscription tiers, refunds, credit conversion | HITL required |
| Authentication / Authorization | HIGH | Login, signup, password reset, JWT, API keys, role changes, user deletion | HITL required |
| Database Migrations | HIGH | Alembic revisions, column drops, data backfills, type changes | HITL required |
| User Data Deletion | HIGH | Account removal, bulk content wipe, GDPR erasure | HITL required |
| Email / Notifications | HIGH | Transactional email (password, receipt), broadcast pushes, mass DM | HITL required |
| API Changes (public) | MODERATE | Endpoint signature changes, response shape, error codes, rate limit changes | HOTL with review |
| Auth-Adjacent | MODERATE | Permission checks, visibility logic, sharing settings (not auth itself) | HOTL with review |
| Cross-Module Refactor | MODERATE | Touches 3+ modules, changes shared interfaces | HOTL with review |
| Documentation | LOW | Docstrings, README, inline comments, plan files | HOTL safe |
| UI Copy / Layout | LOW | Labels, tooltips, error messages (not functionality) | HOTL safe |
| Isolated Tests | LOW | New test cases, test fixture updates, test organization | HOTL safe |
| Lint / Format | LOW | Prettier, eslint, formatting only | HOTL safe |
| Config (non-sensitive) | LOW | Feature flags (off by default), log level, display prefs | HOTL safe |
