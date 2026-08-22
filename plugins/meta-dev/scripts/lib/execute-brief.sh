#!/usr/bin/env bash
# ============================================================================
# lib/execute-brief.sh — per-backend prompt block. SOURCED, not executed.
#
# Doctrine: references/execute-briefs.md
#
# Caller sets BACKEND (grok|deep|codex|opus|sonnet|fable|glm) and PROMPT.
# md_brief_wrap_prompt prepends a short harness-specific block.
# ============================================================================

md_brief_for_backend() {
    local backend="${1:-}"
    case "$backend" in
        grok)
            cat <<'EOF'
=== BACKEND BRIEF: Grok ===
You are Grok Build, not Claude Code. Do the DIRECT task below.
Farm independent pieces to spawn_subagent (general-purpose). Keep THIS
context as one-line verdicts — do not chew the whole job here.
Git (no PreToolUse): never rebase/stash/add -A/commit -a/bare commit.
Form: git -C <ABS> add -- <paths> && git -C <ABS> commit --only -m "…" -- <paths>.
Commit-on-red. Never "run /loop-gap" as a Claude slash; follow a skill path if needed.
=== END BRIEF ===
EOF
            ;;
        deep)
            cat <<'EOF'
=== BACKEND BRIEF: DeepSeek ===
You are Claude Code on DeepSeek. Slash commands work. Keep this unit SMALL.
Named files only. One acceptance. Stop at first pass. No long-horizon arc.
Critical-breakage tests only — do not over-test. Do not wander the repo.
=== END BRIEF ===
EOF
            ;;
        codex)
            cat <<'EOF'
=== BACKEND BRIEF: Codex ===
You are Codex, not Claude Code. Do the DIRECT task. The work is inlined —
do not re-read a plan file to reconstruct it.
Use --skill/--command only if the dispatcher named one. No Claude slash.
Git: explicit paths + commit --only. Commit-on-red. Final handoff = the JSON object.
=== END BRIEF ===
EOF
            ;;
        opus)
            cat <<'EOF'
=== BACKEND BRIEF: Opus ===
You are Claude Code on Opus. This pass is REVIEW unless the task says otherwise.
Prefer findings over edits. One pass. Do not farm, do not implement a plan,
do not loop. Slash commands work if you must run a named procedure.
=== END BRIEF ===
EOF
            ;;
        sonnet)
            cat <<'EOF'
=== BACKEND BRIEF: Sonnet ===
You are Claude Code on Sonnet. Bounded task. Slash commands work.
Stay on declared files. No unrelated refactors. Commit-on-red with explicit paths.
=== END BRIEF ===
EOF
            ;;
        fable)
            cat <<'EOF'
=== BACKEND BRIEF: Fable ===
You are Claude Code on Fable. Hardest-task reasoning, still one bounded job.
Slash commands work. No unrelated refactors. Commit-on-red with explicit paths.
=== END BRIEF ===
EOF
            ;;
        glm)
            cat <<'EOF'
=== BACKEND BRIEF: GLM ===
You are Claude Code on GLM. You may hold a short stateful phase.
Slash commands work. Still no unrelated refactors. Commit-on-red with explicit paths.
Farm tiny mechanical leaves rather than bloating this thread.
=== END BRIEF ===
EOF
            ;;
        *)
            cat <<'EOF'
=== BACKEND BRIEF ===
Do the named task only. Commit-on-red with explicit paths. Do not wander.
=== END BRIEF ===
EOF
            ;;
    esac
}

md_brief_wrap_prompt() {
    local backend="${BACKEND:-}"
    local block
    block="$(md_brief_for_backend "$backend")"
    [[ -z "$block" ]] && return 0
    PROMPT="${block}

${PROMPT}"
}
