#!/usr/bin/env python3
"""Conservative shared policy for git commands in a shared worktree.

The policy is intentionally a small shell-aware parser, not a regex.  It sees
every simple command in ``&&`` chains, rejects shell constructs it cannot
reliably inspect, and applies one commit form that cannot absorb a peer's
staged index entries.
"""
from __future__ import annotations

import argparse
import os
import re
import shlex
import sys
from dataclasses import dataclass


DENIED_SUBCOMMANDS = {
    "stash", "reset", "restore", "checkout", "clean", "rebase", "revert",
}
READ_ONLY_SUBCOMMANDS = {
    "blame", "branch", "config", "describe", "diff", "log", "ls-files",
    "remote", "rev-list", "rev-parse", "show", "status", "symbolic-ref",
}
SHELL_UNSAFE = ("$(", "`")


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ""


def _separate_unquoted_newlines(command: str) -> str:
    """Turn shell command newlines into semicolons without touching quoted text."""
    result: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(command):
        char = command[index]
        if quote is None:
            if char in {"'", '"'}:
                quote = char
                result.append(char)
            elif char == "\\" and index + 1 < len(command) and command[index + 1] == "\n":
                index += 1  # A backslash-newline is a continuation, not a separator.
            elif char == "\n":
                previous = next((item for item in reversed(result) if not item.isspace()), "")
                if previous not in {"", ";", "&", "|"}:
                    result.append(";")
            else:
                result.append(char)
        else:
            result.append(char)
            if char == "\\" and quote == '"' and index + 1 < len(command):
                index += 1
                result.append(command[index])
            elif char == quote:
                quote = None
        index += 1
    return "".join(result)


def _split_commands(command: str) -> list[list[str]]:
    """Split simple commands while refusing shell forms that hide git calls."""
    if not command.strip():
        return []
    if any(marker in command for marker in SHELL_UNSAFE) or re.search(r"[<>]\(", command):
        raise ValueError("shell substitution cannot be inspected safely")
    lexer = shlex.shlex(_separate_unquoted_newlines(command), posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)
    commands: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in {"&&", ";"}:
            if not current:
                raise ValueError("empty shell command segment")
            commands.append(current)
            current = []
        elif token in {"|", "||", "&", "&;"}:
            raise ValueError(f"shell operator {token!r} cannot be inspected safely")
        else:
            current.append(token)
    if not current:
        raise ValueError("trailing shell command separator")
    commands.append(current)
    return commands


def _is_git_executable(token: str) -> bool:
    """Recognize ``git`` and path-qualified git executables alike."""
    return token == "git" or ("/" in token and os.path.basename(token) == "git")


def _git_command(tokens: list[str]) -> list[str] | None:
    """Return git argv only for an unambiguous direct git invocation."""
    index = 0
    while index < len(tokens) and "=" in tokens[index] and not tokens[index].startswith("="):
        name, _, _ = tokens[index].partition("=")
        if not name.replace("_", "").isalnum():
            return None
        index += 1
    if index == len(tokens):
        return None
    if not _is_git_executable(tokens[index]):
        if any(_is_git_executable(token) or re.search(r"\bgit\s", token) for token in tokens):
            raise ValueError("indirect git invocation cannot be inspected safely")
        return None
    return tokens[index + 1 :]


def _parse_git(argv: list[str]) -> tuple[str, str | None, list[str]]:
    """Return subcommand, absolute -C directory, and remaining arguments."""
    directory: str | None = None
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "-C":
            if index + 1 >= len(argv):
                raise ValueError("git -C requires an absolute repository path")
            if directory is not None:
                raise ValueError("multiple git -C directories are not allowed")
            directory = argv[index + 1]
            if not os.path.isabs(directory):
                raise ValueError("git -C must name an absolute repository path")
            index += 2
            continue
        if token.startswith("-"):
            raise ValueError(f"unsupported git global option {token!r}")
        break
    if index >= len(argv):
        raise ValueError("bare git invocation")
    return argv[index], directory, argv[index + 1 :]


def _explicit_paths(paths: list[str], *, action: str, directory: str) -> None:
    if not paths:
        raise ValueError(f"git {action} requires explicit file paths after --")
    for path in paths:
        if path in {".", "..", "*"} or path.endswith("/"):
            raise ValueError(f"git {action} cannot use broad path {path!r}")
        if any(char in path for char in "*?["):
            raise ValueError(f"git {action} cannot use glob path {path!r}")
        if os.path.isabs(path) or ".." in path.split("/"):
            raise ValueError(f"git {action} path must stay below the repository root: {path!r}")
        if os.path.isdir(os.path.join(directory, path)):
            raise ValueError(f"git {action} cannot use directory path {path!r}")


def _validate_add(directory: str | None, args: list[str]) -> None:
    if directory is None:
        raise ValueError("git add must use git -C <absolute-repository>")
    if any(arg in {"-A", "--all", "-u", "--update"} for arg in args):
        raise ValueError("git add broad staging flags are forbidden")
    if "--" not in args:
        raise ValueError("git add must separate explicit files with --")
    separator = args.index("--")
    if args[:separator]:
        raise ValueError("git add accepts no options before --")
    _explicit_paths(args[separator + 1 :], action="add", directory=directory)


def _validate_commit(directory: str | None, args: list[str]) -> None:
    if directory is None:
        raise ValueError("git commit must use git -C <absolute-repository>")
    if len(args) < 5 or args[0] != "--only" or args[1] != "-m":
        raise ValueError("git commit must use --only -m and explicit paths")
    if not args[2] or args[3] != "--":
        raise ValueError("git commit must be git -C <absolute> commit --only -m <message> -- <files>")
    _explicit_paths(args[4:], action="commit", directory=directory)


def _validate_git(argv: list[str]) -> None:
    subcommand, directory, args = _parse_git(argv)
    if subcommand in DENIED_SUBCOMMANDS:
        raise ValueError(f"git {subcommand} is forbidden in a shared worktree")
    if subcommand == "add":
        _validate_add(directory, args)
    elif subcommand == "commit":
        _validate_commit(directory, args)
    elif subcommand in {"pull", "merge"}:
        if directory is None or args != ["--ff-only"]:
            raise ValueError(f"git {subcommand} is allowed only as git -C <absolute> {subcommand} --ff-only")
    elif subcommand in READ_ONLY_SUBCOMMANDS:
        return
    elif subcommand in {"fetch", "tag"}:
        # These may be legitimate conductor operations but must still be rooted.
        if directory is None:
            raise ValueError(f"git {subcommand} must use git -C <absolute-repository>")
    else:
        raise ValueError(f"git {subcommand} is not allowed by the shared-worktree policy")


def validate_shell(command: str) -> Decision:
    """Validate all direct git calls inside a shell command string."""
    try:
        for tokens in _split_commands(command):
            git_argv = _git_command(tokens)
            if git_argv is not None:
                _validate_git(git_argv)
    except ValueError as exc:
        return Decision(False, str(exc))
    return Decision(True)


def main() -> int:
    parser = argparse.ArgumentParser(description="validate a shell command against shared git policy")
    parser.add_argument("--command", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    decision = validate_shell(args.command)
    if args.json:
        import json
        print(json.dumps({"allowed": decision.allowed, "reason": decision.reason}))
    elif not decision.allowed:
        print(decision.reason, file=sys.stderr)
    return 0 if decision.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
