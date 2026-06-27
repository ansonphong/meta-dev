# Sniff Catalog — every smell grug know, how to detect, what to say

Grounded in: grug brain developer philosophy (grugbrain.dev), Fowler/refactoring.guru code-smell catalog, common hack patterns, and the bitter experience of plans that became nightmares. For each smell: **detection** (how to spot it, with a threshold so grug not over-flag), **why grug no like** (the principle), **grug say** (the simplest fix — never more complex than the smell).

> **Cardinal rule (grug law #2):** the fix must be grug-approved. If the only fix adds more complexity than the smell costs, the finding becomes "leave it, here is why" at a lower stink level. Never recommend a design pattern to kill a smell that a small edit fixes.

> **Target-type rule:** Plans use §Plan Smells below. Code uses §Code Smells. Never cross the streams — plan smells don't apply to code, code smells don't apply to plans.

---

# Plan Smells (PRIMARY — apply to plan .md files)

## Group P1 — complexity demon in plans (grug's apex predator — weight heaviest)

### P1.1 Over-engineered phase structure
- **Detect:** >5 phases for a <20-task plan; phases with only 1 task each; phase structure that mirrors "enterprise SDLC" for a one-person project; sub-sub-phases (Phase 2.3.1).
- **Why:** phase overhead is real cost — each phase gate is a decision, a review, a context switch. grug: "flat list of tasks better than pretty phase diagram."
- **grug say:** collapse to 3–4 phases max. merge single-task phases into neighbors. if a phase has one task, the task IS the phase — drop the phase heading.

### P1.2 Speculative / future phases
- **Detect:** Phase N+1 designed in detail while Phase 1 is not done; "Phase 3: AI-powered recommendations" with no Phase 1 working; "Future: pluggable backends" when there is only one backend.
- **Why:** grug fear "maybe build later". planning things that will change before you reach them is waste. YAGNI applies to plans too.
- **grug say:** delete or collapse to a one-line "Later:" note. detail only the phase you are shipping now. future phases get one sentence, not task breakdowns.

### P1.3 Premature architecture in plan
- **Detect:** plan specifies microservices for a single-user app; abstract factory pattern mandated in task description; "we'll use event sourcing" for a CRUD app; architecture diagram more complex than the problem.
- **Why:** architecture in a plan becomes architecture in code. complexity in the plan metastasizes.
- **grug say:** delete the architecture mandate. let the code find its shape. the plan describes WHAT to build and HOW to verify — not which design patterns to use.

### P1.4 Nested sub-plans / recursion
- **Detect:** a task that says "execute sub-plan X" or "see sub-plan Y" — plans calling plans; deeply nested master-plan → phase-plan → task-plan structure.
- **Why:** grug brain can hold one plan. two plans = two places to update, two places to get stale, two places to forget.
- **grug say:** inline the sub-plan's tasks into the master plan. one flat list. one source of truth.

---

## Group P2 — vague handwave (tasks that say nothing)

### P2.1 Task with no concrete deliverable
- **Detect:** task description that does not name a specific file, endpoint, component, or behavior. "Improve performance" (by how much? measured how?), "Clean up codebase" (which files? what is "clean"?), "Make it better" (what is "better"?).
- **Why:** if grug cannot tell when task is done, task is never done. vagueness is the enemy of execution.
- **grug say:** rewrite task to name: exact file(s) touched, exact change, exact verify command that proves completion. "Improve performance" → "Reduce `/api/search` p99 latency from 800ms to 200ms. Verify: `ab -n 1000` shows p99 < 200ms."

### P2.2 Missing Verify command
- **Detect:** a `### Task N:` with no `Verify:` line. Task describes work but has no test/gate that proves it worked.
- **Why:** task with no verify is a wish, not a task. grug cannot know if done or broken.
- **grug say:** add `Verify:` line — a specific command that exits 0 on success. every task gets one. no exceptions.

### P2.3 "The AI / LLM will handle this" (assumed magic)
- **Detect:** task defers to AI/LLM/automation with no spec, no prompt, no expected output shape. "AI generates the description", "LLM handles classification", "auto-fix with Claude."
- **Why:** "AI" is not magic — it needs a spec like any other component. underspecified AI step = undefined behavior.
- **grug say:** specify: exact prompt, expected output schema, validation of output, fallback on failure. AI is a tool, not a wizard. if you cannot write the prompt, you have not specified the task.

### P2.4 Underspecified integration
- **Detect:** "connect to API" / "integrate with X" — no endpoint URL, no request/response shape, no auth method, no error handling mentioned.
- **Why:** "integrate" is a handwave, not a task. the real work is in the details.
- **grug say:** name the exact endpoints, request/response schemas, auth mechanism, error codes to handle. "integrate with Stripe" → "call `POST /v1/checkout/sessions` (Stripe API), map response to `CheckoutSession` model, handle `card_declined` and `rate_limit` errors."

### P2.5 BARE link / "see also" without substance
- **Detect:** task body is a URL or "see <link>" with no summary; reference to external doc with no extracted relevant detail.
- **Why:** link rots. external doc changes. the plan must carry the meaning, not just a pointer.
- **grug say:** extract the relevant detail into the task. the link is supplemental, not the content.

---

## Group P3 — missing gate / unsafe

### P3.1 Destructive task with no rollback
- **Detect:** task that deletes, drops, truncates, purges, migrates data, or `rm -rf` with no backup step, no rollback command, no "how to undo this."
- **Why:** destructive + no undo = big stink every time. grug fear irreversible change.
- **grug say:** add a backup step BEFORE the destructive action. add a rollback command. add a verify that backup is restorable. if truly irreversible, flag it loudly with a pause-gate.

### P3.2 No acceptance criteria
- **Detect:** plan has no "Done means:" / acceptance section; no user-visible behavior defined; no way to tell if the plan as a whole succeeded.
- **Why:** plan with no finish line is a treadmill. grug cannot ship what grug cannot define as done.
- **grug say:** add an acceptance section: 3–5 concrete, user-visible outcomes that mean the plan is complete. "User can upload a photo and receive a 360 panorama within 30 seconds."

### P3.3 Money-path task with no audit trail
- **Detect:** task touches payments, credits, licensing, billing with no logging, no idempotency, no reconciliation step.
- **Why:** money vanishes silently. grug cannot debug "user says they paid but license shows inactive" without logs.
- **grug say:** add: structured logging on every state change, idempotency key on every charge, reconciliation query in verify step.

### P3.4 Deploy step with no smoke test
- **Detect:** plan ends with "Deploy" task that has no post-deploy health check, no smoke test, no rollback-if-unhealthy.
- **Why:** deploy-and-pray is prayer, not engineering.
- **grug say:** add post-deploy smoke test: hit the health endpoint, verify the new version string, confirm critical path works. add rollback command if smoke fails.

---

## Group P4 — dependency rot

### P4.1 Circular dependency
- **Detect:** Task A depends on Task B, Task B depends on Task A (directly or transitively).
- **Why:** circular dep = cannot sequence. both tasks wait on each other forever.
- **grug say:** break the cycle. usually means the tasks are really one task (merge them) or the dependency is wrong (one direction is fake — remove it).

### P4.2 Impossible ordering
- **Detect:** Task 5 needs the output of Task 8, but Task 8 is listed after Task 5 with no dependency declared; task needs a file created by a later task.
- **Why:** plan says build in order X but reality requires order Y. execution will hit a wall.
- **grug say:** reorder tasks to match real dependency graph. or add the missing dependency and note that Task 5 is blocked until Task 8.

### P4.3 Phantom dependency
- **Detect:** task uses a module/endpoint/file that no task in the plan creates; dependency on work not in this plan and not listed in `**Depends on:**`.
- **Why:** plan assumes something exists that doesn't. execution hits "import error" at runtime.
- **grug say:** either add the missing prerequisite task, or list it in `**Depends on:**` as an external dependency with its status (done/in-progress/blocked).

### P4.4 Missing dependency declaration
- **Detect:** Task A and Task B touch the same file with no dependency between them; two tasks edit overlapping regions.
- **Why:** parallel execution of overlapping edits = merge conflict guaranteed. or worse, silent overwrite.
- **grug say:** declare the dependency: the later task depends on the earlier one. or merge the tasks if the edits are really one change.

---

## Group P5 — scope creep / gold-plating

### P5.1 "Nice to have" in critical path
- **Detect:** task on the critical path that is not required for the plan's stated goal; polishing/optimization before core works; "add dark mode" in a plan whose goal is "working login."
- **Why:** nice-to-haves in critical path = delayed ship for things nobody asked for. grug ship ugly first, pretty later.
- **grug say:** move to a separate "Post-launch" or "Nice to have" section, after all critical-path tasks. or delete if truly irrelevant.

### P5.2 Future phases designed in detail
- **Detect:** Phase 2/3/4 with full task breakdowns while Phase 1 is not yet executed; detailed design for features that depend on unbuilt foundation.
- **Why:** speculative work rots. by the time you reach Phase 3, the foundation has changed and the detailed plan is wrong. the time spent detailing it is waste.
- **grug say:** collapse future phases to one-line descriptions. detail them when the phase before them is DONE and you know what the world looks like.

### P5.3 Gold-plated non-functional requirements
- **Detect:** "must handle 1M QPS" for a single-user app; "99.999% uptime" for an internal tool; "horizontal scaling" before there is one server.
- **Why:** solving problems you don't have is the definition of over-engineering.
- **grug say:** delete or downgrade to "scale when we have >1 user." state the ACTUAL requirement, not the impressive-sounding one.

---

## Group P6 — duplicate / redundant work

### P6.1 Duplicate tasks
- **Detect:** two tasks that describe the same work under different names; Task 3: "Add user auth" and Task 7: "Add login endpoint" — same thing.
- **Why:** two tasks = two places to track, two places to get out of sync, possibility of two implementations colliding.
- **grug say:** merge into one task. the broader task absorbs the narrower one.

### P6.2 Redundant verification
- **Detect:** Task A's verify command also verifies Task B's deliverable; same test runs in 3 task verifies; verify chain that tests the whole system per task instead of per-plan.
- **Why:** redundant tests = slow execution, confusing failures (which task broke it?).
- **grug say:** each task's Verify tests ONLY that task's deliverable. end-to-end tests go in the plan's acceptance section, run once at the end.

### P6.3 Task that duplicates what a dependency delivers
- **Detect:** Task B builds X, but Task A (which B depends on) already built X.
- **Why:** double work or worse, conflicting implementations.
- **grug say:** remove the duplicate. Task B uses what Task A built — that is what the dependency means.

---

## Group P7 — underspecified / unfounded

### P7.1 Unfounded time estimate
- **Detect:** "should take ~2 hours", "approx 30 min", "quick task" — with no basis, no breakdown.
- **Why:** made-up numbers become false expectations. grug: "estimate is guess with pretty font."
- **grug say:** remove the estimate, or replace with a breakdown that justifies it. "~2 hours" alone is a whiff; "~2 hours" on a task that touches 10 files cross-subsystem is a smell.

### P7.2 File reference that doesn't exist
- **Detect:** task says "edit `src/foo.py`" but `src/foo.py` does not exist in the repo; task declares files that would be CREATED but lists them as if they exist.
- **Why:** plan detached from codebase reality. execution hits "file not found" immediately.
- **grug say:** verify every file reference against the repo. mark files to CREATE vs EDIT explicitly. `src/foo.py (CREATE)` vs `src/bar.py (EDIT)`.

### P7.3 Technology choice with no rationale
- **Detect:** "Use Redis for caching" with no explanation of why Redis vs in-memory; "We'll use Kafka" for 10 messages/day; technology mandated by name with no "because."
- **Why:** tech choice without rationale = resume-driven development. grug use simplest tool that works.
- **grug say:** add one-line rationale, or downgrade to the simpler choice. "Use Redis" → "Use in-memory dict (Redis when >1 server)."

---

## Group P8 — happy-path-only design

### P8.1 No error handling in spec
- **Detect:** plan describes only success flow; no mention of error states, edge cases, retry, timeout, fallback.
- **Why:** production is all edge cases. happy-path plans ship broken software.
- **grug say:** add error-handling tasks or call out error paths in each task: "Handle: network down, API returns 500, file missing, disk full, rate limited."

### P8.2 Missing migration-failure path
- **Detect:** DB migration task with no "what if migration fails halfway"; schema change with no downgrade tested.
- **Why:** failed migration = broken DB. half-applied migration = the worst kind of broken.
- **grug say:** add: transaction boundary, downgrade command, verify downgrade works, backup before migration.

### P8.3 External-call assumed success
- **Detect:** task calls external API/service with no timeout, no retry, no circuit-breaker, no fallback.
- **Why:** external calls fail. grug plan for failure or failure plan for grug.
- **grug say:** add: timeout (named value), retry strategy (how many, backoff), fallback behavior (what the user sees when it fails).

---

## Group P9 — phantom coupling in plans

### P9.1 Undeclared file overlap
- **Detect:** Task A and Task B both touch `src/utils.py` but no dependency declared between them.
- **Why:** parallel edits to same file = merge hell.
- **grug say:** either add dependency (one must go first), or merge tasks, or split the file so each task touches its own.

### P9.2 Shared state introduced without coordination
- **Detect:** two tasks each add to the same global config, registry, or database table with no coordination task.
- **Why:** two independent implementations of shared state = conflict at integration time.
- **grug say:** add a coordination task that defines the shared schema FIRST, then both tasks build against it.

---

## Group P10 — chesterton fence in plans

### P10.1 Unexplained removal / rewrite proposal
- **Detect:** plan proposes deleting or rewriting an existing system with no explanation of why the current system exists, what edge cases it handles, what incidents shaped it.
- **Why:** "old code bad, rewrite good" is the most expensive lie in software. chesterton fence: understand before removing.
- **grug say:** add a "Why the current system exists" note before the rewrite task. if the reason is unknown, add a research/spelunking task BEFORE the rewrite task.

### P10.2 "Simplify" with no current-complexity analysis
- **Detect:** task says "Simplify X" with no description of what makes X complex now, what edge cases the complexity serves, what the simplified version sacrifices.
- **Why:** "simplify" without analysis = "rewrite from memory, reintroduce old bugs."
- **grug say:** specify: what is complex now, why it got that way, what the simpler version does differently, what (if anything) is lost.

---

# Code Smells (SECONDARY — apply to source files)

## Group C1 — complexity demon (grug's apex predator — weight heaviest)

### C1.1 Speculative generality
- **Detect:** code built for a future that has not arrived — a config option never set to anything but default, a parameter only ever passed one value, a hook with no second caller, "for when we need it" abstractions. Threshold: generality with exactly ONE concrete use today.
- **Why:** grug fear "maybe use later". complexity demon love future-proofing. YAGNI.
- **grug say:** delete the unused generality. inline to the one real case. add it back when the second case actually arrives ("grug know cut point when grug see cut point").

### C1.2 Premature / wrong abstraction
- **Detect:** interface/abstract-base/protocol with exactly one implementer; factory that builds one type; a `BaseFoo`→`FooImpl` pair with no second `Impl`; a wrapper that only forwards. Threshold: 1 implementer / 1 caller.
- **Why:** abstraction has a cost (indirection, two places to read). one user does not pay for it. grug: "repeat code sometimes often better than complex DRY solution".
- **grug say:** inline the abstraction into its single caller. keep the concrete class. abstract only when 2-3 real uses reveal the shared shape.

### C1.3 Arrow code (deep nesting)
- **Detect:** nesting depth ≥ 4 (if-inside-if-inside-for-inside-if); the code "points right". Threshold: 4 levels, or 3 with long bodies.
- **Why:** hard to hold in head. each level is a condition grug must track.
- **grug say:** early return / guard clauses to flatten. extract the inner block to a named function. invert conditions.

### C1.4 Clever one-liner / dense expression
- **Detect:** a single expression chaining many operations, nested ternaries, comprehension-inside-comprehension, regex doing three jobs, no intermediate names.
- **Why:** grug cannot debug what grug cannot see. "easier debug! see result of each expression more clearly" — name the steps.
- **grug say:** break into named intermediate variables, one operation each. lines are cheap; debugging a mystery is not.

### C1.5 God object / does-everything class
- **Detect:** a class/module that touches unrelated concerns (db + http + formatting + business logic); methods that share no fields; very high method+field count with low cohesion. Threshold: ≥3 distinct responsibilities OR no shared state among method clusters.
- **Why:** change anything → risk everything. cannot test one thing alone.
- **grug say:** split along the natural cut-point (the method clusters that share state). but only when the cut is clear — do not shatter into nano-classes (that is complexity too).

---

## Group C2 — big thing (bloaters)

### C2.1 Long method
- **Detect:** a function doing several distinct steps. Threshold (guidance, not law): ~50+ lines, OR clearly separable phases with comment-banners marking sections ("# step 1", "# now do X").
- **Why:** long is ok if FLAT and linear; long is a smell when it hides several operations.
- **grug say:** extract the labelled phases into named functions — ONLY at clear seams. a flat 60-line linear function with no seams: leave it (whiff at most).

### C2.2 Long parameter list
- **Detect:** ≥5 parameters, or params that always travel together. Threshold: 5+.
- **Why:** hard to call right, easy to swap argument order, signals missing object.
- **grug say:** if params always go together → introduce a param object / dataclass / options struct. if some are derivable → derive inside. boolean flags → see C4.7.

### C2.3 Large class
- **Detect:** very long class with many fields/methods. Threshold: judgment — only flag when also low-cohesion (else see C1.5) or clearly two things glued together.
- **grug say:** extract the cohesive sub-cluster into its own class at the seam.

### C2.4 Data clumps
- **Detect:** the same group of 3+ values passed around together repeatedly (`x, y, w, h` everywhere; `host, port, user, pass`).
- **Why:** repeated grouping is a hidden object asking to be born.
- **grug say:** make the clump a small value object. now it travels as one and can grow methods.

---

## Group C3 — repeat-or-abstract (grug's DRY nuance — BOTH directions stink)

### C3.1 Real duplication
- **Detect:** the SAME non-trivial logic copy-pasted 3+ times (rule of three), especially with a bug-fix that would need applying in N places. Threshold: 3+ real copies of non-trivial logic.
- **Why:** N places to fix one bug = shotgun surgery waiting.
- **grug say:** factor — but ONLY if the cut-point is clear and the copies are truly the same thing (not coincidentally similar). 2 copies: usually leave (WET is fine). coincidental similarity: leave, they will diverge.

### C3.2 Premature / forced DRY (the OPPOSITE smell — grug-specific)
- **Detect:** an abstraction created to remove duplication that now has one caller, or many callers that each pass a flag to get different behavior (the abstraction is fighting itself); a helper with a `mode`/`type` param that switches its whole behavior.
- **Why:** "repeat code sometimes often better than complex DRY solution". forced DRY couples things that should be free.
- **grug say:** un-abstract. inline back to the call sites that wanted different things. duplication you can see beats coupling you cannot.

---

## Group C4 — hack & shortcut (mostly mechanical — high confidence)

### C4.1 TODO / FIXME / HACK / XXX
- **Detect:** grep `TODO|FIXME|HACK|XXX|@hack|@temp` in changed/target code.
- **grug say:** resolve it, or convert to a tracked issue with a link. a HACK with no ticket is a HACK forever.

### C4.2 Swallowed exception
- **Detect:** `catch (e) {}` / `except: pass` / `except Exception: pass` / catch that only `console.log`s and continues when it should handle or re-raise.
- **Why:** errors vanish, debugging becomes archaeology. grug love logging — silent failure is the enemy.
- **grug say:** handle it (recover), or log-and-re-raise, or narrow the catch to the specific expected exception. never swallow blind.

### C4.3 Magic number / magic string
- **Detect:** unexplained literal in logic (`* 86400`, `if status == 3`, `retries < 5`); a string compared against in multiple places.
- **Why:** reader does not know what `3` means; change it in one place, miss another.
- **grug say:** name it a constant (`SECONDS_PER_DAY`, `STATUS_ACTIVE`). whiff if the literal is obvious in context (`i + 1`, `* 2`).

### C4.4 Hardcoded secret / credential
- **Detect:** grep `password|passwd|api[_-]?key|secret|token|aws_|private_key` assigned a string literal; connection strings with creds.
- **Why:** big stink always. secrets in source leak.
- **grug say:** move to env var / secret store. rotate the leaked value. (flag at `big stink`, every time.)

### C4.5 Commented-out code
- **Detect:** blocks of code commented out (not prose comments), especially with no explanation.
- **Why:** dead weight, confuses reader, git already remembers.
- **grug say:** delete it. git is the graveyard. if "might need later" → that is what history is for.

### C4.6 Dead code
- **Detect:** unreferenced function/variable/branch; unreachable code after return; a flag that is never true. Verify zero consumers via grep before flagging (chesterton fence — group C7).
- **grug say:** delete after confirming zero callers. but CONFIRM first (entry points, dynamic dispatch, reflection can hide callers).

### C4.7 Boolean-trap parameter
- **Detect:** function called with a bare `true`/`false` whose meaning is invisible at the call site (`render(true)`, `save(data, false, true)`).
- **Why:** call site unreadable; easy to pass wrong.
- **grug say:** split into two named functions, OR pass a named enum/options object. caller should read like a sentence.

### C4.8 Stringly-typed
- **Detect:** strings used where an enum/type belongs — status/kind/mode passed as raw strings and compared with `==` in many places.
- **Why:** typo = silent bug; no autocomplete (grug's 90% of type-system value).
- **grug say:** introduce an enum / literal-union / constant set. let the type system and IDE catch typos.

---

## Group C5 — coupling demon (couplers)

### C5.1 Feature envy
- **Detect:** a method that uses another object's data/methods more than its own (lots of `other.x`, `other.y`, `other.calc()`).
- **Why:** behavior lives far from the data it needs. grug: "put code on the thing that do the thing".
- **grug say:** move the method onto the object whose data it envies. behavior goes to the data.

### C5.2 Message chain
- **Detect:** `a.b().c().d().e()` — reaching through several objects.
- **Why:** caller now knows the whole graph; any link change breaks it.
- **grug say:** ask the first object for what you actually want (add a method that returns it). do not reach through. (do not over-apply — one `.` chain of getters can be fine.)

### C5.3 Middle man
- **Detect:** a class/method whose body only forwards to another object (every method is `return delegate.foo()`).
- **grug say:** talk to the delegate directly; remove the pass-through. (unless the middle man adds real value — adapting, guarding — then keep.)

### C5.4 Inappropriate intimacy / reaching into internals
- **Detect:** one module poking another's private fields, internal state, or `_private` members; tight two-way coupling.
- **grug say:** expose a small intentional method; stop reaching past the front door.

---

## Group C6 — fear-the-spooky (grug's named fears)

### C6.1 Shared mutable global state
- **Detect:** module-level mutable variable written from multiple places; singleton holding request/user state; global cache mutated without guard.
- **Why:** "grug, like all sane developer, fear concurrency". shared mutable state is where the spooky bugs live.
- **grug say:** make it stateless; pass state explicitly; use a queue/immutable structure. if it must be shared+mutable, isolate and guard it loudly.

### C6.2 Premature optimization
- **Detect:** clever performance hack (bit-twiddling, manual loop-unroll, caching layer, micro-opt) with NO evidence of a measured bottleneck; optimizing CPU while ignoring an obvious network/IO cost.
- **Why:** "hitting network equivalent of many, many millions cpu cycle". optimizing the wrong thing adds complexity for nothing.
- **grug say:** revert to the simple version; profile first; optimize only the proven hot path. note where the REAL cost likely is (usually IO/network).

### C6.3 Missing logging on error/important path
- **Detect:** error path, money path, or external-call failure with no log; a `catch` that recovers silently on an important operation.
- **Why:** grug love log — "logging very important". you cannot debug production blind.
- **grug say:** add a log at the right level with enough context (ids, inputs) to debug later. (do not over-log happy-path trivia — that is noise.)

---

## Group C7 — chesterton fence (applies to diffs that DELETE or REWRITE)

### C7.1 Unexplained removal / rewrite
- **Detect:** a diff that deletes or substantially rewrites existing non-trivial code with no stated reason, no test covering the old behavior, and no evidence the author understood why it was there.
- **Why:** "take time understand system first". code is ugly-and-gronky for reasons (edge cases, prod incidents). removing it blind reintroduces old bugs.
- **grug say:** before removing — find why it exists (git blame, the test it satisfies, the edge case it guards). if reason is dead, remove with a note. if reason unknown, do NOT remove yet.

---

## Anti-flag list (grug will NOT flag these — flagging them is itself a smell)

**Plan anti-flags:**
- a flat task list with ≤5 phases (flat is GOOD)
- a plan with no architecture diagram (diagrams rot — code is the design)
- a task that trusts the developer to figure it out (not every detail needs a spec — trust the executor on mechanical tasks)
- a plan that defers details to execution time (that is what execution is FOR)
- a plan with "just" 3 tasks for a small change (not everything needs a master plan)

**Code anti-flags:**
- a `switch`/`if-else` chain that is flat and readable (no Strategy pattern needed)
- 2 copies of similar code (rule of three not met)
- a long-but-flat linear function with no seams
- a magic number that is obvious in context (`i+1`, `*2`, `/100` for percent)
- duplication that is coincidental and will diverge
- a getter chain of one or two `.` on a stable object
- comments that explain WHY (those are good — only flag comments that compensate for a bad name or restate WHAT the code already says)
- any "improvement" whose fix is more complex than the current code
