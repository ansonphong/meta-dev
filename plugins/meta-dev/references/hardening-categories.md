# Hardening categories

Full hardening uses this inventory for coverage, not an agent count. Apply the
project's actual stack and risk. Deterministic checks run once; reviewers own
judgment. Record non-applicable categories and unresolved blockers.

- Cross-reference integrity: master/phase handles, paths, and task inventories
  agree; no phantom or duplicate tasks.
- Internal consistency and terminology: requirements do not contradict across
  sections; names match live contracts and project conventions.
- Completeness and dependencies: every requested outcome has an owner and
  acceptance evidence; producers precede consumers; cross-plan inputs exist.
- Contract fields/schema: inputs, outputs, error shapes, storage and client
  consumers agree. Trace new fields through every consuming boundary.
- Implicit assumptions and feasibility: required inputs and runtime guards
  exist; a compiling call must not silently do nothing.
- State lifecycle: initialization, mutations, resets, persistence, snapshots,
  and reachable UI states preserve invariants.
- Security and side channels: authorization at trust boundaries, secrets,
  scope limiters, data exposure, and permission checks on every path.
- Behavioral claims: challenge each meaningful always/never claim with a
  concrete counterexample, including failures and alternate entry points.
- Verification soundness/reachability: commands prove the claimed behavior;
  multi-step checks remain executable after prior state changes. No trivial
  always-passing assertions or broad task gates.
- Execution context: paths/commands match the actual repository root, working
  directory, dependency environment, and tool availability.
- Architecture mapping: use existing registries/helpers deliberately; explain
  new boundaries and avoid duplicate infrastructure.
- Ground truth, imports, and staleness: verify live symbols, relevant callers,
  import chains, and changes since inspection. Record anchors, not snapshots.
- Edge cases/integration: error paths, cancellation, concurrency, retries, and
  rollback preserve invariants across the affected scope.
- Migration/compatibility: old clients, saved data, and optional settings have
  a defined compatibility or migration path.
- Performance/resources: bounded algorithms, I/O, memory, subscriptions,
  caches, timers, cleanup, and resource use match realistic workloads.
- Value/logic correctness: accumulators versus last-write values, branches,
  bounds, nullable values, and returned final results are correct.
- Dead code/error handling/type safety: inspect unused paths and escape
  hatches; distinguish legitimate public callbacks and abstract methods.
- API drift: mounted routes and actual callers agree on paths, fields, events,
  casing, and serialization.
- Test coverage: follow declared test policy and risk, not one test per public
  function/component. Critical boundaries need meaningful negative evidence.
- Stubs and plan claims: claimed completion corresponds to usable live
  behavior. Empty returns, TODO comments, or example text are candidates for
  inspection, not automatic defects without context.
