# Work ladder

Routing preferences are configuration, not a user's subscription policy.
Read `meta_dev.ladder` and `meta_dev.workflow` through
`bash ${PLUGIN_ROOT}/scripts/config-get.sh`. Project/local overrides may set
the pool, paused backends, model profiles, and resource ceilings. The shipped
defaults do not assume a named user, paid account, quota balance, or project.

1. Honor an explicit backend/model selection if available and permitted.
2. Otherwise stay on the host-native configured route. External services are
   eligible only when the user/project opted into them and their authorization
   requirements are satisfied.
3. A paused route is unavailable, including when named: explain the configured
   pause and ask for a routing/configuration choice. Never silently replace an
   explicit model or clear a user's quota restriction.
4. Choose the lowest-cost available route sufficient for the task, using local
   measurements where available. Model names alone do not establish cost or
   quality. Do not inherit maximum effort from the conductor.
5. Read `references/adaptive-workflow.md` for conditional delegation, coherent
   slices, and bounded independent review. Grep/inventory is deterministic work
   first; it does not need a frontier worker by default.

## Capability and host separation

`scripts/workflow-policy.py` resolves authoring/execution policy from exact
configured model IDs and aliases. Its shipped frontier profiles include Sol,
Astra, Opus 4.8/5/5.5, and Grok 4.6/4.7. These are planning hints, not availability or
price guarantees. Unknown models fall back safely and can be configured.

Native workers use the host's actual delegation surface. Headless Codex,
Grok, Antigravity, and Cursor receive direct briefs with task excerpts and
artifact paths, not Claude slash commands. A Claude headless process may load
its installed command surface. Vendor loading syntax belongs in adapters;
project rules come from root `AGENTS.md`, routed `docs/agent-context/`, and
canonical skills. `/cursor-execute` is named-only (`cursor-headless-exec`);
never add it to `meta_dev.ladder.pool`.

Optional backends keep their own authentication and explicit-permission gates.
Selecting autonomous execution does not automatically authorize an external
consultant, desktop session, deployment, or paid benchmark.
