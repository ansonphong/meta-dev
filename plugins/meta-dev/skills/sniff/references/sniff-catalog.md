# Sniff Catalog — every smell grug know, how to detect, what to say

Grounded in: grug brain developer philosophy (grugbrain.dev), Fowler/refactoring.guru code-smell catalog, and common hack patterns. For each smell: **detection** (how to spot it, with a threshold so grug not over-flag), **why grug no like** (the principle), **grug say** (the simplest fix — never more complex than the smell).

> **Cardinal rule (grug law #2):** the fix must be grug-approved. If the only fix adds more complexity than the smell costs, the finding becomes "leave it, here is why" at a lower stink level. Never recommend a design pattern to kill a smell that a small edit fixes.

---

## Group 1 — complexity demon (grug's apex predator — weight heaviest)

### 1.1 Speculative generality
- **Detect:** code built for a future that has not arrived — a config option never set to anything but default, a parameter only ever passed one value, a hook with no second caller, "for when we need it" abstractions. Threshold: generality with exactly ONE concrete use today.
- **Why:** grug fear "maybe use later". complexity demon love future-proofing. YAGNI.
- **grug say:** delete the unused generality. inline to the one real case. add it back when the second case actually arrives ("grug know cut point when grug see cut point").

### 1.2 Premature / wrong abstraction
- **Detect:** interface/abstract-base/protocol with exactly one implementer; factory that builds one type; a `BaseFoo`→`FooImpl` pair with no second `Impl`; a wrapper that only forwards. Threshold: 1 implementer / 1 caller.
- **Why:** abstraction has a cost (indirection, two places to read). one user does not pay for it. grug: "repeat code sometimes often better than complex DRY solution".
- **grug say:** inline the abstraction into its single caller. keep the concrete class. abstract only when 2-3 real uses reveal the shared shape.

### 1.3 Arrow code (deep nesting)
- **Detect:** nesting depth ≥ 4 (if-inside-if-inside-for-inside-if); the code "points right". Threshold: 4 levels, or 3 with long bodies.
- **Why:** hard to hold in head. each level is a condition grug must track.
- **grug say:** early return / guard clauses to flatten. extract the inner block to a named function. invert conditions.

### 1.4 Clever one-liner / dense expression
- **Detect:** a single expression chaining many operations, nested ternaries, comprehension-inside-comprehension, regex doing three jobs, no intermediate names.
- **Why:** grug cannot debug what grug cannot see. "easier debug! see result of each expression more clearly" — name the steps.
- **grug say:** break into named intermediate variables, one operation each. lines are cheap; debugging a mystery is not.

### 1.5 God object / does-everything class
- **Detect:** a class/module that touches unrelated concerns (db + http + formatting + business logic); methods that share no fields; very high method+field count with low cohesion. Threshold: ≥3 distinct responsibilities OR no shared state among method clusters.
- **Why:** change anything → risk everything. cannot test one thing alone.
- **grug say:** split along the natural cut-point (the method clusters that share state). but only when the cut is clear — do not shatter into nano-classes (that is complexity too).

---

## Group 2 — big thing (bloaters)

### 2.1 Long method
- **Detect:** a function doing several distinct steps. Threshold (guidance, not law): ~50+ lines, OR clearly separable phases with comment-banners marking sections ("# step 1", "# now do X").
- **Why:** long is ok if FLAT and linear; long is a smell when it hides several operations.
- **grug say:** extract the labelled phases into named functions — ONLY at clear seams. a flat 60-line linear function with no seams: leave it (whiff at most).

### 2.2 Long parameter list
- **Detect:** ≥5 parameters, or params that always travel together. Threshold: 5+.
- **Why:** hard to call right, easy to swap argument order, signals missing object.
- **grug say:** if params always go together → introduce a param object / dataclass / options struct. if some are derivable → derive inside. boolean flags → see 4.7.

### 2.3 Large class
- **Detect:** very long class with many fields/methods. Threshold: judgment — only flag when also low-cohesion (else see 1.5) or clearly two things glued together.
- **grug say:** extract the cohesive sub-cluster into its own class at the seam.

### 2.4 Data clumps
- **Detect:** the same group of 3+ values passed around together repeatedly (`x, y, w, h` everywhere; `host, port, user, pass`).
- **Why:** repeated grouping is a hidden object asking to be born.
- **grug say:** make the clump a small value object. now it travels as one and can grow methods.

---

## Group 3 — repeat-or-abstract (grug's DRY nuance — BOTH directions stink)

### 3.1 Real duplication
- **Detect:** the SAME non-trivial logic copy-pasted 3+ times (rule of three), especially with a bug-fix that would need applying in N places. Threshold: 3+ real copies of non-trivial logic.
- **Why:** N places to fix one bug = shotgun surgery waiting.
- **grug say:** factor — but ONLY if the cut-point is clear and the copies are truly the same thing (not coincidentally similar). 2 copies: usually leave (WET is fine). coincidental similarity: leave, they will diverge.

### 3.2 Premature / forced DRY (the OPPOSITE smell — grug-specific)
- **Detect:** an abstraction created to remove duplication that now has one caller, or many callers that each pass a flag to get different behavior (the abstraction is fighting itself); a helper with a `mode`/`type` param that switches its whole behavior.
- **Why:** "repeat code sometimes often better than complex DRY solution". forced DRY couples things that should be free.
- **grug say:** un-abstract. inline back to the call sites that wanted different things. duplication you can see beats coupling you cannot.

---

## Group 4 — hack & shortcut (mostly mechanical — high confidence)

### 4.1 TODO / FIXME / HACK / XXX
- **Detect:** grep `TODO|FIXME|HACK|XXX|@hack|@temp` in changed/target code.
- **grug say:** resolve it, or convert to a tracked issue with a link. a HACK with no ticket is a HACK forever.

### 4.2 Swallowed exception
- **Detect:** `catch (e) {}` / `except: pass` / `except Exception: pass` / catch that only `console.log`s and continues when it should handle or re-raise.
- **Why:** errors vanish, debugging becomes archaeology. grug love logging — silent failure is the enemy.
- **grug say:** handle it (recover), or log-and-re-raise, or narrow the catch to the specific expected exception. never swallow blind.

### 4.3 Magic number / magic string
- **Detect:** unexplained literal in logic (`* 86400`, `if status == 3`, `retries < 5`); a string compared against in multiple places.
- **Why:** reader does not know what `3` means; change it in one place, miss another.
- **grug say:** name it a constant (`SECONDS_PER_DAY`, `STATUS_ACTIVE`). whiff if the literal is obvious in context (`i + 1`, `* 2`).

### 4.4 Hardcoded secret / credential
- **Detect:** grep `password|passwd|api[_-]?key|secret|token|aws_|private_key` assigned a string literal; connection strings with creds.
- **Why:** big stink always. secrets in source leak.
- **grug say:** move to env var / secret store. rotate the leaked value. (flag at `big stink`, every time.)

### 4.5 Commented-out code
- **Detect:** blocks of code commented out (not prose comments), especially with no explanation.
- **Why:** dead weight, confuses reader, git already remembers.
- **grug say:** delete it. git is the graveyard. if "might need later" → that is what history is for.

### 4.6 Dead code
- **Detect:** unreferenced function/variable/branch; unreachable code after return; a flag that is never true. Verify zero consumers via grep before flagging (chesterton fence — group 7).
- **grug say:** delete after confirming zero callers. but CONFIRM first (entry points, dynamic dispatch, reflection can hide callers).

### 4.7 Boolean-trap parameter
- **Detect:** function called with a bare `true`/`false` whose meaning is invisible at the call site (`render(true)`, `save(data, false, true)`).
- **Why:** call site unreadable; easy to pass wrong.
- **grug say:** split into two named functions, OR pass a named enum/options object. caller should read like a sentence.

### 4.8 Stringly-typed
- **Detect:** strings used where an enum/type belongs — status/kind/mode passed as raw strings and compared with `==` in many places.
- **Why:** typo = silent bug; no autocomplete (grug's 90% of type-system value).
- **grug say:** introduce an enum / literal-union / constant set. let the type system and IDE catch typos.

---

## Group 5 — coupling demon (couplers)

### 5.1 Feature envy
- **Detect:** a method that uses another object's data/methods more than its own (lots of `other.x`, `other.y`, `other.calc()`).
- **Why:** behavior lives far from the data it needs. grug: "put code on the thing that do the thing".
- **grug say:** move the method onto the object whose data it envies. behavior goes to the data.

### 5.2 Message chain
- **Detect:** `a.b().c().d().e()` — reaching through several objects.
- **Why:** caller now knows the whole graph; any link change breaks it.
- **grug say:** ask the first object for what you actually want (add a method that returns it). do not reach through. (do not over-apply — one `.` chain of getters can be fine.)

### 5.3 Middle man
- **Detect:** a class/method whose body only forwards to another object (every method is `return delegate.foo()`).
- **grug say:** talk to the delegate directly; remove the pass-through. (unless the middle man adds real value — adapting, guarding — then keep.)

### 5.4 Inappropriate intimacy / reaching into internals
- **Detect:** one module poking another's private fields, internal state, or `_private` members; tight two-way coupling.
- **grug say:** expose a small intentional method; stop reaching past the front door.

---

## Group 6 — fear-the-spooky (grug's named fears)

### 6.1 Shared mutable global state
- **Detect:** module-level mutable variable written from multiple places; singleton holding request/user state; global cache mutated without guard.
- **Why:** "grug, like all sane developer, fear concurrency". shared mutable state is where the spooky bugs live.
- **grug say:** make it stateless; pass state explicitly; use a queue/immutable structure. if it must be shared+mutable, isolate and guard it loudly.

### 6.2 Premature optimization
- **Detect:** clever performance hack (bit-twiddling, manual loop-unroll, caching layer, micro-opt) with NO evidence of a measured bottleneck; optimizing CPU while ignoring an obvious network/IO cost.
- **Why:** "hitting network equivalent of many, many millions cpu cycle". optimizing the wrong thing adds complexity for nothing.
- **grug say:** revert to the simple version; profile first; optimize only the proven hot path. note where the REAL cost likely is (usually IO/network).

### 6.3 Missing logging on error/important path
- **Detect:** error path, money path, or external-call failure with no log; a `catch` that recovers silently on an important operation.
- **Why:** grug love log — "logging very important". you cannot debug production blind.
- **grug say:** add a log at the right level with enough context (ids, inputs) to debug later. (do not over-log happy-path trivia — that is noise.)

---

## Group 7 — chesterton fence (applies to diffs that DELETE or REWRITE)

### 7.1 Unexplained removal / rewrite
- **Detect:** a diff that deletes or substantially rewrites existing non-trivial code with no stated reason, no test covering the old behavior, and no evidence the author understood why it was there.
- **Why:** "take time understand system first". code is ugly-and-gronky for reasons (edge cases, prod incidents). removing it blind reintroduces old bugs.
- **grug say:** before removing — find why it exists (git blame, the test it satisfies, the edge case it guards). if reason is dead, remove with a note. if reason unknown, do NOT remove yet.

---

## Anti-flag list (grug will NOT flag these — flagging them is itself a smell)

- a `switch`/`if-else` chain that is flat and readable (no Strategy pattern needed)
- 2 copies of similar code (rule of three not met)
- a long-but-flat linear function with no seams
- a magic number that is obvious in context (`i+1`, `*2`, `/100` for percent)
- duplication that is coincidental and will diverge
- a getter chain of one or two `.` on a stable object
- comments that explain WHY (those are good — only flag comments that compensate for a bad name or restate WHAT the code already says)
- any "improvement" whose fix is more complex than the current code
