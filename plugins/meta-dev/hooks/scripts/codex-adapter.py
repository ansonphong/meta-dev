#!/usr/bin/env python3
"""Bridge Codex lifecycle payloads to the existing Claude-compatible hooks.

Codex ships ``PLUGIN_ROOT`` for bundled hooks; without it this is deliberately
a no-op, so the adapter cannot affect a Claude session or an arbitrary script
invocation.  Codex uses ``apply_patch`` for edits, while the legacy hooks expect
Claude's Edit/Write payload, so only the generic Bash path is delegated.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = os.environ.get("PLUGIN_ROOT", "")


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


def main() -> int:
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
            print(output)
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
