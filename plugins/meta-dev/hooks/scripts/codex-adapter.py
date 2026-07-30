#!/usr/bin/env python3
"""Bridge Codex lifecycle payloads to the existing Claude-compatible hooks.

Codex uses ``apply_patch`` for edits, while the legacy hooks expect Claude's
Edit/Write payload, so only the generic Bash path is delegated.

**This adapter must never touch a Claude Code session.**  Claude already has its
own PreToolUse chain (``.claude/hooks/meta-guard-check.sh`` -> ``guard-check.sh``);
running the Codex path there applies Codex's stricter shared-worktree git policy
on top of it, which is not what either layer was designed for.

The original gate was "``PLUGIN_ROOT`` is set", on the assumption that only Codex
exports it.  That assumption is false -- Claude Code populates the plugin-root
environment for plugin hooks too, so the gate never fired and the Codex policy
silently governed Claude sessions.  It presented as *intermittent* (some agents
blocked, some not) purely because the variable's presence varies by launch path
and Claude Code version, which made it look like random breakage rather than one
mis-scoped hook.  Burned 2026-07-26: ``git push`` was refused in a Claude session
by a Codex-only policy that also had push missing from its allowlist.

Gate positively on the harness instead: bail whenever Claude Code's own markers
are present.  ``META_DEV_GIT_POLICY_IN_CLAUDE=1`` re-enables it deliberately.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = os.environ.get("PLUGIN_ROOT", "")

# Claude Code exports these into every hook process it spawns.
CLAUDE_MARKERS = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_PROJECT_DIR")


def in_claude_session() -> bool:
    """True when this hook is running under Claude Code rather than Codex."""
    if os.environ.get("META_DEV_GIT_POLICY_IN_CLAUDE") == "1":
        return False
    return any(os.environ.get(marker) for marker in CLAUDE_MARKERS)


def emit(value: dict) -> None:
    print(json.dumps(value, separators=(",", ":")))


def run_legacy(script: str, payload: str) -> str:
    environment = os.environ.copy()
    environment["CLAUDE_PLUGIN_ROOT"] = ROOT
    result = subprocess.run(
        ["bash", str(Path(ROOT) / "hooks" / "scripts" / script)],
        input=payload, text=True, capture_output=True, env=environment,
        timeout=18,
    )
    return result.stdout.strip()


def deny(reason: str) -> None:
    emit({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": f"meta-dev git policy: {reason}",
    }})


def bash_command(payload: dict) -> str | None:
    """Normalize Codex's Bash input aliases without accepting malformed input."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    # Codex production payloads use ``cmd``; retain ``command`` for older hook
    # payloads. A supplied malformed primary field is never silently bypassed.
    if "cmd" in tool_input:
        command = tool_input["cmd"]
    else:
        command = tool_input.get("command")
    return command if isinstance(command, str) else None


def normalized_bash_payload(payload: dict, command: str) -> str:
    """Preserve Codex fields while supplying the legacy Bash command key."""
    normalized = dict(payload)
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        raise ValueError("Bash tool_input is missing or malformed")
    normalized_input = dict(tool_input)
    normalized_input["command"] = command
    normalized["tool_input"] = normalized_input
    return json.dumps(normalized, separators=(",", ":"))


def normalize_legacy_pretool_output(output: str) -> dict | None:
    """Translate Claude's PreToolUse decision shape to Codex's contract.

    Codex treats exit 0 with no output as approval.  It accepts an explicit
    ``permissionDecision: allow`` only when the hook also rewrites the call via
    ``updatedInput``.  The legacy guard emits bare ``allow`` decisions, so
    forwarding them verbatim makes every safe Bash call report a hook failure.
    """
    decoded = json.loads(output)
    if not isinstance(decoded, dict):
        raise ValueError("legacy Bash guard returned a non-object decision")
    specific = decoded.get("hookSpecificOutput")
    if not isinstance(specific, dict):
        raise ValueError("legacy Bash guard returned no hook-specific decision")
    if specific.get("hookEventName") != "PreToolUse":
        raise ValueError("legacy Bash guard returned the wrong hook event")

    decision = specific.get("permissionDecision")
    if decision == "deny":
        return decoded
    if decision != "allow":
        raise ValueError("legacy Bash guard returned an unsupported decision")

    # A future legacy rewrite is already valid Codex output and must survive.
    if "updatedInput" in specific:
        return decoded

    # Preserve warning text while dropping Claude's unsupported bare allow.
    message = decoded.get("systemMessage")
    if isinstance(message, str) and message:
        return {"systemMessage": message}
    return None


def main() -> int:
    # Claude Code runs its own guard chain — never layer the Codex policy on it.
    if in_claude_session():
        return 0
    if not ROOT or not Path(ROOT).is_dir():
        return 0
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return 0
    event = payload.get("hook_event_name", "")
    tool = payload.get("tool_name", "")

    # The hook file deliberately uses generic Bash/apply_patch matchers.  Keep
    # this filter in code too: Codex tool aliases and future matcher expansion
    # must not accidentally run Bash policy against unrelated local functions.
    if event in {"PreToolUse", "PostToolUse"} and tool not in {"Bash", "apply_patch"}:
        return 0

    if event == "PreToolUse" and tool == "Bash":
        sys.path.insert(0, str(Path(ROOT) / "scripts" / "lib"))
        from git_policy import validate_shell  # pylint: disable=import-outside-toplevel
        command = bash_command(payload)
        if command is None:
            deny("Bash command is missing or malformed")
            return 0
        decision = validate_shell(command)
        if not decision.allowed:
            deny(decision.reason)
            return 0
        try:
            legacy_payload = normalized_bash_payload(payload, command)
            output = run_legacy("guard-check.sh", legacy_payload)
        except (OSError, subprocess.SubprocessError, ValueError):
            deny("legacy Bash guard could not inspect the command")
            return 0
        if output:
            try:
                normalized_output = normalize_legacy_pretool_output(output)
            except (json.JSONDecodeError, ValueError):
                deny("legacy Bash guard returned a malformed decision")
                return 0
            if normalized_output is not None:
                emit(normalized_output)
        else:
            deny("legacy Bash guard returned no decision")
        return 0

    if event == "PostToolUse" and tool == "Bash":
        run_legacy("on-bash.sh", raw)
        return 0

    if event == "SessionStart":
        output = run_legacy("on-session-start.sh", raw)
        if output:
            emit({"hookSpecificOutput": {
                "hookEventName": "SessionStart", "additionalContext": output,
            }})
        return 0

    if event == "UserPromptSubmit":
        output = run_legacy("on-stage-prompt.sh", raw)
        if output:
            print(output)
        return 0

    if event == "Stop":
        output = run_legacy("on-run-complete.sh", raw)
        if output:
            emit({"systemMessage": output})
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
