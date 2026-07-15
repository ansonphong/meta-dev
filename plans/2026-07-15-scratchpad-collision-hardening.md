# Scratchpad Collision Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop headless review/execute runs from silently skipping a lens when a staged prompt file is empty/overwritten — make the wrappers fail LOUD on an empty prompt, accept a prompt-by-file input, and teach the conductor to stage intermediates under unique, atomically-written paths.

**Architecture:** Two-pronged, both entirely inside the meta-dev framework repo. (1) **Wrapper hardening** — one shared `lib/read-prompt.sh` helper, sourced by the three headless runners (`codex`/`grok`/`claude`-`headless-exec`), that resolves the prompt from a positional arg *or* a new `--prompt-file <path>` and hard-fails (exit 1, diagnostic) on a missing/empty/whitespace-only prompt. (2) **Orchestration convention** — a "Scratchpad staging" contract added to the execute-loop protocol + headless-worker skill so the conductor stages to unique per-run paths, writes atomically, verifies `[ -s ]`, and passes absolute paths by `--prompt-file`.

**Tech Stack:** Bash (`set -euo pipefail`), the existing `plugins/meta-dev/scripts/lib/*.sh` sourced-helper pattern, meta-dev skill markdown, `plugin.json` version manifest.

## Global Constraints

- **Repo:** ALL edits land in the source checkout `/mnt/d/Projects/360-Hextile/meta-dev` (NOT `~/.claude/plugins/...` — the installed copy is overwritten on update).
- **HARD RULE #1 (verbatim from meta-dev/CLAUDE.md):** Every push to origin MUST bump the patch version in `plugins/meta-dev/.claude-plugin/plugin.json`. `1.3.38` → `1.3.39`. Without a version bump the cache stays frozen and edits never register.
- **Plugin-relative paths:** use `${CLAUDE_PLUGIN_ROOT}` in skills/commands; scripts self-locate via `SCRIPT_DIR`.
- **Commit messages:** `feat(phase):` / `fix(phase):` / `chore(phase):`.
- **Line endings:** LF only (WSL2 writes).
- **Shell mode:** all three runners run under `set -euo pipefail`; the helper must be safe under `set -u` (reference `$PROMPT` defensively).
- **Testing policy:** critical-breakage tests only. The one test file here (`lib/test-read-prompt.sh`) guards silent lens-skip — it earns its keep; add no others.
- **Precedence rule (lock this term):** when `--prompt-file` is provided it is AUTHORITATIVE — its contents replace any positional prompt. Document it identically everywhere it appears.

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `plugins/meta-dev/scripts/lib/read-prompt.sh` | Single source of truth for prompt resolution + empty/whitespace fail-loud validation. Exposes `resolve_prompt <input_file> <runner_name>`, mutating global `$PROMPT`. | Create |
| `plugins/meta-dev/scripts/lib/test-read-prompt.sh` | Hermetic unit tests for the helper (no external CLI). | Create |
| `plugins/meta-dev/scripts/codex-headless-exec` | Codex runner — add `--prompt-file`, swap inline guard for `resolve_prompt`. | Modify |
| `plugins/meta-dev/scripts/grok-headless-exec` | Grok runner — same wiring. | Modify |
| `plugins/meta-dev/scripts/claude-headless-exec` | Deep/GLM/Sonnet workhorse runner — same wiring (largest blast radius; read before editing). | Modify |
| `plugins/meta-dev/skills/agentic-exec-loop/references/loop-protocol.md` | Conductor-side "Scratchpad staging" contract. | Modify |
| `plugins/meta-dev/skills/headless-worker/SKILL.md` | Cross-reference the `--prompt-file` input + staging rule. | Modify |
| `plugins/meta-dev/.claude-plugin/plugin.json` | Version bump `1.3.38 → 1.3.39`. | Modify |

**Interface produced by Task 1, consumed by Tasks 2–4 (lock these names/signatures):**
- File: `plugins/meta-dev/scripts/lib/read-prompt.sh`
- Function: `resolve_prompt <input_file> <runner_name>`
  - `<input_file>`: path from `--prompt-file` (may be empty string ⇒ use positional).
  - `<runner_name>`: label for diagnostics, e.g. `codex-headless-exec`.
  - Effect: sets global `PROMPT`; calls `exit 1` (loud) on missing/empty/whitespace-only prompt.

---

### Task 1: Shared prompt-resolution helper + hermetic tests

**Files:**
- Create: `plugins/meta-dev/scripts/lib/read-prompt.sh`
- Test: `plugins/meta-dev/scripts/lib/test-read-prompt.sh`

**Interfaces:**
- Consumes: nothing (leaf helper).
- Produces: `resolve_prompt <input_file> <runner_name>` → mutates global `PROMPT`, `exit 1` on invalid.

- [ ] **Step 1: Write the failing test**

Create `plugins/meta-dev/scripts/lib/test-read-prompt.sh`:

```bash
#!/usr/bin/env bash
# Hermetic unit tests for lib/read-prompt.sh — the guard runs before any
# codex/grok/claude CLI invocation, so no external tool or auth is needed.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="$HERE/read-prompt.sh"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
pass=0; fail=0
check() { if [[ "$1" == "$2" ]]; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $3 (got '$1' want '$2')"; fi; }

# 1) non-empty positional prompt → exit 0, PROMPT preserved
( source "$LIB"; PROMPT="do the thing"; resolve_prompt "" test; [[ "$PROMPT" == "do the thing" ]] )
check "$?" 0 "positional non-empty passes"

# 2) whitespace-only positional → exit 1
( source "$LIB"; PROMPT="   "; resolve_prompt "" test ) 2>/dev/null
check "$?" 1 "whitespace positional rejected"

# 3) empty --prompt-file → exit 1
: > "$tmp/empty.prompt"
( source "$LIB"; PROMPT=""; resolve_prompt "$tmp/empty.prompt" test ) 2>/dev/null
check "$?" 1 "empty prompt-file rejected"

# 4) missing --prompt-file → exit 1
( source "$LIB"; PROMPT=""; resolve_prompt "$tmp/nope.prompt" test ) 2>/dev/null
check "$?" 1 "missing prompt-file rejected"

# 5) non-empty --prompt-file → exit 0 AND PROMPT loaded from file (overrides positional)
printf 'from file' > "$tmp/ok.prompt"
out="$( source "$LIB"; PROMPT="positional"; resolve_prompt "$tmp/ok.prompt" test; printf '%s' "$PROMPT" )"
check "$?" 0 "prompt-file happy path exits 0"
check "$out" "from file" "prompt-file overrides positional"

echo "read-prompt.sh: $pass passed, $fail failed"
[[ "$fail" -eq 0 ]]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /mnt/d/Projects/360-Hextile/meta-dev && bash plugins/meta-dev/scripts/lib/test-read-prompt.sh`
Expected: FAIL — `read-prompt.sh: No such file or directory` (the helper does not exist yet).

- [ ] **Step 3: Write minimal implementation**

Create `plugins/meta-dev/scripts/lib/read-prompt.sh`:

```bash
#!/usr/bin/env bash
# ============================================================================
# lib/read-prompt.sh — shared prompt resolution + fail-loud validation for the
# headless-exec runners (codex / grok / claude). SOURCED, not executed.
#
#   resolve_prompt <input_file> <runner_name>
#     Populates the global $PROMPT and HARD-FAILS (exit 1) on a prompt that is
#     missing / empty / whitespace-only, with a diagnostic naming the empty
#     source. Turns a mis-staged conductor scratchpad file into a LOUD error
#     instead of the silent "No prompt provided" degradation that skips a lens.
#
#   Precedence: when <input_file> is non-empty it is AUTHORITATIVE — its
#   contents replace any positional $PROMPT the caller already parsed.
#
# Conductor-side staging rules (unique per-run paths, atomic writes, verify
# before dispatch) live in:
#   skills/agentic-exec-loop/references/loop-protocol.md → "Scratchpad staging".
# ============================================================================

resolve_prompt() {
    local infile="$1" runner="${2:-headless-exec}"
    PROMPT="${PROMPT-}"   # safe under `set -u` even if caller left it unset

    if [[ -n "$infile" ]]; then
        if [[ ! -s "$infile" ]]; then
            echo "[ERROR] $runner: --prompt-file '$infile' is missing or empty." >&2
            echo "        The conductor staged a prompt to a path that was overwritten or" >&2
            echo "        never written. Stage to a UNIQUE per-run path and verify '[ -s FILE ]'" >&2
            echo "        before dispatch (loop-protocol.md -> Scratchpad staging)." >&2
            exit 1
        fi
        PROMPT="$(cat "$infile")"
    fi

    # Reject whitespace-only: $(...) strips trailing newlines but not embedded
    # spaces/tabs, and a blank prompt is never a real task.
    if [[ -z "${PROMPT//[[:space:]]/}" ]]; then
        echo "[ERROR] $runner: empty or whitespace-only prompt — nothing to execute." >&2
        echo "        Pass a real task after '--', or --prompt-file <non-empty path>." >&2
        exit 1
    fi
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /mnt/d/Projects/360-Hextile/meta-dev && bash plugins/meta-dev/scripts/lib/test-read-prompt.sh`
Expected: PASS — final line `read-prompt.sh: 6 passed, 0 failed`, exit 0.

- [ ] **Step 5: Commit**

```bash
cd /mnt/d/Projects/360-Hextile/meta-dev
git add plugins/meta-dev/scripts/lib/read-prompt.sh plugins/meta-dev/scripts/lib/test-read-prompt.sh
git commit -m "feat(scripts): shared read-prompt helper — fail-loud on empty prompt + --prompt-file input"
```

---

### Task 2: Wire codex-headless-exec to the helper

**Files:**
- Modify: `plugins/meta-dev/scripts/codex-headless-exec` (defaults ~L65-66, arg-parse ~L85, guard L92-95, usage header L12-13)

**Interfaces:**
- Consumes: `resolve_prompt` from Task 1.
- Produces: `codex-headless-exec --prompt-file <path>` input; exit 1 + diagnostic on empty prompt.

- [ ] **Step 1: Add the `PROMPT_INPUT_FILE` default**

Find (around line 65-66):

```bash
OUTPUT_FORMAT="json"
PROMPT=""
OUTPUT_FILE=""
```

Replace with:

```bash
OUTPUT_FORMAT="json"
PROMPT=""
PROMPT_INPUT_FILE=""
OUTPUT_FILE=""
```

- [ ] **Step 2: Add the `--prompt-file` arg case**

Find (around line 85):

```bash
        --output-file) OUTPUT_FILE="$2"; shift 2 ;;
        -h|--help)  show_help ;;
```

Replace with:

```bash
        --output-file) OUTPUT_FILE="$2"; shift 2 ;;
        --prompt-file) PROMPT_INPUT_FILE="$2"; shift 2 ;;
        -h|--help)  show_help ;;
```

- [ ] **Step 3: Swap the inline guard for `resolve_prompt`**

Find (lines 92-95):

```bash
if [[ -z "$PROMPT" ]]; then
    echo "[ERROR] No prompt provided. Usage: codex-headless-exec [options] -- <prompt>" >&2
    exit 1
fi
```

Replace with:

```bash
# Prompt resolution + fail-loud validation (positional OR --prompt-file).
source "$SCRIPT_DIR/lib/read-prompt.sh"
resolve_prompt "$PROMPT_INPUT_FILE" "codex-headless-exec"
```

- [ ] **Step 4: Document `--prompt-file` in the usage header**

Find (lines 35-36):

```bash
#   --output json|text       Output format (default: json)
#   -h, --help               Show this help
```

Replace with:

```bash
#   --output json|text       Output format (default: json)
#   --prompt-file <path>     Read the prompt from a file (AUTHORITATIVE — overrides
#                            the positional prompt). Non-empty file required.
#   -h, --help               Show this help
```

- [ ] **Step 5: Verify syntax + empty-prompt fail-loud (hermetic)**

Run:
```bash
cd /mnt/d/Projects/360-Hextile/meta-dev
bash -n plugins/meta-dev/scripts/codex-headless-exec && echo "SYNTAX_OK"
bash plugins/meta-dev/scripts/codex-headless-exec --readonly -- ""; echo "exit=$?"
bash plugins/meta-dev/scripts/codex-headless-exec --prompt-file /no/such/file -- x; echo "exit=$?"
```
Expected: `SYNTAX_OK`; first invocation prints `empty or whitespace-only prompt` then `exit=1`; second prints `--prompt-file '/no/such/file' is missing or empty` then `exit=1`. (No `codex` CLI is touched — the guard runs first.)

- [ ] **Step 6: Commit**

```bash
cd /mnt/d/Projects/360-Hextile/meta-dev
git add plugins/meta-dev/scripts/codex-headless-exec
git commit -m "fix(scripts): codex-headless-exec fails loud on empty prompt + accepts --prompt-file"
```

---

### Task 3: Wire grok-headless-exec to the helper

**Files:**
- Modify: `plugins/meta-dev/scripts/grok-headless-exec` (defaults L61-62, arg-parse L103, guard L110-113, usage header L29-31 + show_help heredoc L80-82)

**Interfaces:**
- Consumes: `resolve_prompt` from Task 1.
- Produces: `grok-headless-exec --prompt-file <path>` input; exit 1 + diagnostic on empty prompt. (Grok's internal `PROMPT_FILE="${OUTPUT_FILE}.prompt"` staging at L136/L174 is UNTOUCHED — the helper only populates `$PROMPT`, which grok still stages to its own unique file.)

- [ ] **Step 1: Add the `PROMPT_INPUT_FILE` default**

Find (lines 61-62):

```bash
PROMPT=""
OUTPUT_FILE=""
```

Replace with:

```bash
PROMPT=""
PROMPT_INPUT_FILE=""
OUTPUT_FILE=""
```

- [ ] **Step 2: Add the `--prompt-file` arg case**

Find (around line 103-104):

```bash
        --output-file) OUTPUT_FILE="$2"; shift 2 ;;
        -h|--help)     show_help ;;
```

Replace with:

```bash
        --output-file) OUTPUT_FILE="$2"; shift 2 ;;
        --prompt-file) PROMPT_INPUT_FILE="$2"; shift 2 ;;
        -h|--help)     show_help ;;
```

- [ ] **Step 3: Swap the inline guard for `resolve_prompt`**

Find (lines 110-113):

```bash
if [[ -z "$PROMPT" ]]; then
    echo "[ERROR] No prompt provided. Usage: grok-headless-exec [options] -- <prompt>" >&2
    exit 1
fi
```

Replace with:

```bash
# Prompt resolution + fail-loud validation (positional OR --prompt-file).
source "$SCRIPT_DIR/lib/read-prompt.sh"
resolve_prompt "$PROMPT_INPUT_FILE" "grok-headless-exec"
```

- [ ] **Step 4: Document `--prompt-file` in BOTH usage blocks**

4a. Find (header comment, lines 30-31):

```bash
#   --output-file <path>     Write distilled JSON here (default: /tmp/...grok-…json)
#   -h, --help               Show this help
```

Replace with:

```bash
#   --output-file <path>     Write distilled JSON here (default: /tmp/...grok-…json)
#   --prompt-file <path>     Read the prompt from a file (AUTHORITATIVE — overrides
#                            the positional prompt). Non-empty file required.
#   -h, --help               Show this help
```

4b. Find (show_help heredoc, lines 81-82):

```bash
  --output-file <path>     Write distilled JSON here (default: /tmp/...grok-…json)
  -h, --help               Show this help
```

Replace with:

```bash
  --output-file <path>     Write distilled JSON here (default: /tmp/...grok-…json)
  --prompt-file <path>     Read the prompt from a file (AUTHORITATIVE — overrides
                           the positional prompt). Non-empty file required.
  -h, --help               Show this help
```

- [ ] **Step 5: Verify syntax + empty-prompt fail-loud (hermetic)**

Run:
```bash
cd /mnt/d/Projects/360-Hextile/meta-dev
bash -n plugins/meta-dev/scripts/grok-headless-exec && echo "SYNTAX_OK"
bash plugins/meta-dev/scripts/grok-headless-exec --readonly -- ""; echo "exit=$?"
bash plugins/meta-dev/scripts/grok-headless-exec --prompt-file /no/such/file -- x; echo "exit=$?"
```
Expected: `SYNTAX_OK`; empty prompt → `empty or whitespace-only prompt` + `exit=1`; missing file → `is missing or empty` + `exit=1`. (No `grok` CLI touched.)

- [ ] **Step 6: Commit**

```bash
cd /mnt/d/Projects/360-Hextile/meta-dev
git add plugins/meta-dev/scripts/grok-headless-exec
git commit -m "fix(scripts): grok-headless-exec fails loud on empty prompt + accepts --prompt-file"
```

---

### Task 4: Wire claude-headless-exec to the helper (deep/glm/sonnet workhorse)

> Largest blast radius — this runner backs `--deep`/`--glm`/`--sonnet`. Read the exact regions first, then apply. `SCRIPT_DIR` is defined at line 43 (before the guard at ~292), so sourcing the helper at the guard site is safe.

**Files:**
- Modify: `plugins/meta-dev/scripts/claude-headless-exec` (default `PROMPT=""` ~L131, arg-parse `--)` ~L266, guard ~L292)

**Interfaces:**
- Consumes: `resolve_prompt` from Task 1.
- Produces: `claude-headless-exec --prompt-file <path>` input; exit 1 + diagnostic on empty prompt.

- [ ] **Step 1: Read the exact regions to edit**

Run: `cd /mnt/d/Projects/360-Hextile/meta-dev && sed -n '128,134p;260,300p' plugins/meta-dev/scripts/claude-headless-exec`
Expected: confirms `PROMPT=""` near L131, the `--)` positional case near L266, and the guard block `if [[ -z "$PROMPT" ]]; then / echo "[ERROR] No prompt provided." >&2 / exit 1 / fi` near L292-295. Note the exact surrounding lines for the three edits below.

- [ ] **Step 2: Add the `PROMPT_INPUT_FILE` default**

Find the defaults line:

```bash
PROMPT=""
```

Replace with:

```bash
PROMPT=""
PROMPT_INPUT_FILE=""
```

- [ ] **Step 3: Add the `--prompt-file` arg case**

In the arg-parse `case` block, immediately BEFORE the `--)` positional case, add a new case line. Given the `--)` case reads:

```bash
        --)
```

Insert directly above it:

```bash
        --prompt-file) PROMPT_INPUT_FILE="$2"; shift 2 ;;
```

(so the result is the new `--prompt-file)` line followed by the existing `--)` line — matching the indentation of the neighboring cases confirmed in Step 1.)

- [ ] **Step 4: Swap the inline guard for `resolve_prompt`**

Find the guard block (confirmed in Step 1, ~L292-295):

```bash
if [[ -z "$PROMPT" ]]; then
    echo "[ERROR] No prompt provided." >&2
    exit 1
fi
```

Replace with:

```bash
# Prompt resolution + fail-loud validation (positional OR --prompt-file).
source "$SCRIPT_DIR/lib/read-prompt.sh"
resolve_prompt "$PROMPT_INPUT_FILE" "claude-headless-exec"
```

- [ ] **Step 5: Verify syntax + empty-prompt fail-loud (hermetic)**

Run:
```bash
cd /mnt/d/Projects/360-Hextile/meta-dev
bash -n plugins/meta-dev/scripts/claude-headless-exec && echo "SYNTAX_OK"
bash plugins/meta-dev/scripts/claude-headless-exec -- ""; echo "exit=$?"
bash plugins/meta-dev/scripts/claude-headless-exec --prompt-file /no/such/file -- x; echo "exit=$?"
```
Expected: `SYNTAX_OK`; empty prompt → `empty or whitespace-only prompt` + `exit=1`; missing file → `is missing or empty` + `exit=1`. If the guard sits AFTER backend/env setup and the empty-prompt run reaches other output first, confirm exit is still `1` with the new diagnostic present.

- [ ] **Step 6: Commit**

```bash
cd /mnt/d/Projects/360-Hextile/meta-dev
git add plugins/meta-dev/scripts/claude-headless-exec
git commit -m "fix(scripts): claude-headless-exec fails loud on empty prompt + accepts --prompt-file"
```

---

### Task 5: Conductor-side scratchpad-staging convention

**Files:**
- Modify: `plugins/meta-dev/skills/agentic-exec-loop/references/loop-protocol.md` (insert after the "Context-hygiene contract" section, currently ending at line 152)
- Modify: `plugins/meta-dev/skills/headless-worker/SKILL.md` (insert after the "## Patterns" block, currently ending at line 24)

**Interfaces:**
- Consumes: the `--prompt-file` inputs added in Tasks 2–4 (referenced by name).
- Produces: documentation only — no code.

- [ ] **Step 1: Add the "Scratchpad staging" section to loop-protocol.md**

Find (lines 148-152, the end of the context-hygiene section):

```markdown
## Context-hygiene contract (NON-NEGOTIABLE)
Per phase, the only things crossing back to main: N one-line worker `result`s
+ one phase verdict. The conductor MUST NOT git diff into its own context,
read OUTPUT_FILE.raw, or read the reviewer transcript. The task tracker
(tasks + per-phase verdict) stays in main for user followability.
```

Replace with (appends the new section immediately after):

```markdown
## Context-hygiene contract (NON-NEGOTIABLE)
Per phase, the only things crossing back to main: N one-line worker `result`s
+ one phase verdict. The conductor MUST NOT git diff into its own context,
read OUTPUT_FILE.raw, or read the reviewer transcript. The task tracker
(tasks + per-phase verdict) stays in main for user followability.

## Scratchpad staging — unique paths, atomic writes, fail-loud (NON-NEGOTIABLE)
When the conductor stages an intermediate artifact for a worker (a review
prompt, a distilled diff, a phase log), it MUST NOT reuse a bare fixed name
(`review-prompt.txt`, `p3.log`) in the session scratchpad. Parallel lenses
(codex + grok + tests dispatched together) then race on that one name, a reader
sees a truncated/empty file, the wrapper reports the empty prompt, and the lens
is silently skipped. Rules:

1. **Unique per-run dir.** `RUN="$SCRATCH/run-$(date +%s)-$$"; mkdir -p "$RUN"`.
   Every staged file lives under `$RUN` with a role+lens-qualified name
   (`$RUN/codex-review.prompt`, `$RUN/grok-review.prompt`) — never a bare name.
2. **Atomic write.** Build to `.tmp`, then `mv`, so a concurrent reader never
   observes a half-written file: `build > "$f.tmp" && mv "$f.tmp" "$f"`.
3. **Verify before dispatch.** `[ -s "$f" ] || { echo "prompt build empty" >&2; exit 1; }`
   — never feed a file to a worker without proving it is non-empty first.
4. **Pass the prompt BY FILE, absolutely.** Prefer
   `codex-headless-exec --prompt-file "$f"` (codex/grok/claude runners accept it)
   over `-- "$(cat "$f")"`, and pass an ABSOLUTE path — a headless worker resolves
   "the scratchpad" to its OWN session dir, not the conductor's. The runners now
   hard-fail on an empty `--prompt-file`, so a mis-staged file surfaces LOUDLY
   instead of degrading to a silent usage error.
```

- [ ] **Step 2: Add a staging cross-reference to headless-worker/SKILL.md**

Find (lines 22-24, the end of the "## Patterns" block):

```markdown
# Model override for Sonnet
claude -p "complex architectural review" --model claude-sonnet-5
```
```

Replace with (keeps the closing fence, then appends the note):

```markdown
# Model override for Sonnet
claude -p "complex architectural review" --model claude-sonnet-5
```

## Prompt staging (avoid scratchpad collisions)

Stage prompts to UNIQUE per-run paths and pass them by file, not by reusing a
bare scratchpad name. All three runners (`codex`/`grok`/`claude`-`headless-exec`)
accept `--prompt-file <path>` (AUTHORITATIVE over any positional prompt) and now
hard-fail on a missing/empty file rather than silently skipping the work. Full
conductor-side rules — unique dir, atomic `.tmp`→`mv`, `[ -s ]` verify, absolute
paths — are in `agentic-exec-loop/references/loop-protocol.md` → "Scratchpad
staging".
```

- [ ] **Step 3: Verify the inserts landed cleanly**

Run:
```bash
cd /mnt/d/Projects/360-Hextile/meta-dev
grep -n "Scratchpad staging" plugins/meta-dev/skills/agentic-exec-loop/references/loop-protocol.md
grep -n "Prompt staging" plugins/meta-dev/skills/headless-worker/SKILL.md
```
Expected: one hit in each file; no accidental duplication of surrounding headings.

- [ ] **Step 4: Commit**

```bash
cd /mnt/d/Projects/360-Hextile/meta-dev
git add plugins/meta-dev/skills/agentic-exec-loop/references/loop-protocol.md \
        plugins/meta-dev/skills/headless-worker/SKILL.md
git commit -m "docs(skills): scratchpad-staging contract — unique paths, atomic writes, --prompt-file"
```

---

### Task 6: Version bump + full suite + release readiness

**Files:**
- Modify: `plugins/meta-dev/.claude-plugin/plugin.json` (`version`: `1.3.38` → `1.3.39`)

**Interfaces:**
- Consumes: all prior tasks committed.
- Produces: a release-ready tree; push/publish is a SEPARATE explicit go (not part of this plan's execution).

- [ ] **Step 1: Bump the patch version (HARD RULE #1)**

Find (line 3 of `plugins/meta-dev/.claude-plugin/plugin.json`):

```json
  "version": "1.3.38",
```

Replace with:

```json
  "version": "1.3.39",
```

- [ ] **Step 2: Run the plugin test suite (scripts + schemas)**

Run:
```bash
cd /mnt/d/Projects/360-Hextile/meta-dev
bash plugins/meta-dev/scripts/lib/test-read-prompt.sh
bash plugins/meta-dev/scripts/test-plugin.sh --check-scripts
```
Expected: helper test → `6 passed, 0 failed`; `test-plugin.sh --check-scripts` → all script syntax checks pass (includes `bash -n` over the three edited runners + the new lib).

- [ ] **Step 3: Commit the version bump**

```bash
cd /mnt/d/Projects/360-Hextile/meta-dev
git add plugins/meta-dev/.claude-plugin/plugin.json
git commit -m "chore(release): bump 1.3.38 -> 1.3.39 — scratchpad collision hardening"
```

- [ ] **Step 4: STOP — report release-readiness (do NOT push)**

Push + `/plugin marketplace update meta-dev` + reinstall is a distinct, separately-authorized act (meta-dev/CLAUDE.md reload procedure). Report: commits made, tests green, version at `1.3.39`, ready to push on explicit go.

---

## Self-Review

**1. Spec coverage (against the diagnosis):**
- Wrappers fail loud on empty prompt → Tasks 2/3/4 (guard swap) ✓
- Prompt-by-file input (`--prompt-file`) → Tasks 2/3/4 ✓
- Whitespace-only rejection (the gap the old `-z` guard missed) → Task 1 helper ✓
- Conductor stages unique + atomic + verified + absolute paths → Task 5 ✓
- Reaches the RUNNING copy (version-keyed cache) → Task 6 bump ✓
- Fix lives in framework source, not local `.claude/` → Global Constraints + all tasks target `/mnt/d/Projects/360-Hextile/meta-dev` ✓

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step shows full literal content; the one read-then-edit (Task 4) is because that runner's exact surrounding lines weren't pre-read — Step 1 reads them, and the anchors (`if [[ -z "$PROMPT" ]]`, `--)`, `PROMPT=""`) are unambiguous.

**3. Type/name consistency:** `resolve_prompt` signature `<input_file> <runner_name>`, global `PROMPT`, and arg var `PROMPT_INPUT_FILE` are identical across Tasks 1–4. `--prompt-file` semantics ("AUTHORITATIVE — overrides positional") stated identically in the helper header, all three usage blocks, and both skill files. Version `1.3.38 → 1.3.39` consistent with the observed manifest and cache history.

**Blast radius note:** Tasks 2–4 only *replace* an existing reject-path (previously exit 1 on empty; now exit 1 on empty/whitespace, plus a new opt-in input arg). No happy-path behavior changes for a non-empty positional prompt — existing `-- "<prompt>"` callers are unaffected.
