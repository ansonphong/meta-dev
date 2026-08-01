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
    "blame", "describe", "diff", "log", "ls-files", "rev-list", "rev-parse",
    "show", "status",
}
PARAM_EXPANSION = "__META_PARAMETER_EXPANSION__"
COMMAND_SUBSTITUTION = "__META_COMMAND_SUBSTITUTION__"


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ""


class ShellShapeError(ValueError):
    """A shell form the splitter cannot break into simple commands.

    Distinct from the refusals raised once an executable is in hand: this one
    says only "I could not split this string", never "something is hiding a
    git call".  A command that never names git is therefore allowed through
    it, so an unrelated ``cat <(ls)`` is not denied on a git rule.
    """


def _command_substitution(command: str, start: int) -> tuple[str, int]:
    """Return one ``$(...)`` body and the index after its closing parenthesis."""
    index = start + 2
    quote: str | None = None
    parenthesis_depth = 0
    while index < len(command):
        char = command[index]
        if quote == "'":
            if char == "'":
                quote = None
        elif quote == '"':
            if char == "\\" and index + 1 < len(command):
                index += 1
            elif char == '"':
                quote = None
            elif command.startswith("$(", index):
                _, index = _command_substitution(command, index)
                continue
        elif char in {"'", '"'}:
            quote = char
        elif char == "\\" and index + 1 < len(command):
            index += 1
        elif command.startswith("$(", index):
            _, index = _command_substitution(command, index)
            continue
        elif char == "(":
            parenthesis_depth += 1
        elif char == ")":
            if parenthesis_depth:
                parenthesis_depth -= 1
            else:
                return command[start + 2 : index], index + 1
        index += 1
    raise ShellShapeError("unterminated command substitution cannot be inspected safely")


def _backtick_substitution(command: str, start: int) -> tuple[str, int]:
    """Return one legacy backtick body and the index after its closing mark."""
    index = start + 1
    while index < len(command):
        if command[index] == "\\" and index + 1 < len(command):
            index += 2
            continue
        if command[index] == "`":
            return command[start + 1 : index], index + 1
        index += 1
    raise ShellShapeError("unterminated command substitution cannot be inspected safely")


def _prepare_expansions(command: str) -> tuple[str, list[str]]:
    """Mark active expansions while retaining nested commands for inspection."""
    result: list[str] = []
    substitutions: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(command):
        char = command[index]
        if quote == "'":
            result.append(char)
            if char == "'":
                quote = None
            index += 1
            continue
        if char == "\\" and index + 1 < len(command):
            result.extend((char, command[index + 1]))
            index += 2
            continue
        if char == "'" and quote is None:
            quote = char
            result.append(char)
            index += 1
            continue
        if char == '"':
            quote = None if quote == '"' else '"'
            result.append(char)
            index += 1
            continue
        if command.startswith("$(", index):
            body, index = _command_substitution(command, index)
            if not body.strip():
                raise ShellShapeError("empty command substitution cannot be inspected safely")
            substitutions.append(body)
            result.append(COMMAND_SUBSTITUTION)
            continue
        if char == "`":
            body, index = _backtick_substitution(command, index)
            if not body.strip():
                raise ShellShapeError("empty command substitution cannot be inspected safely")
            substitutions.append(body)
            result.append(COMMAND_SUBSTITUTION)
            continue
        if char == "$":
            braced = re.match(r"\$\{[^}]*\}", command[index:])
            parameter = braced or re.match(r"\$(?:[A-Za-z_][A-Za-z0-9_]*|[0-9@*#?$!\-])", command[index:])
            if parameter:
                if braced:
                    _, nested = _prepare_expansions(braced.group(0)[2:-1])
                    substitutions.extend(nested)
                result.append(PARAM_EXPANSION)
                index += len(parameter.group(0))
                continue
        result.append(char)
        index += 1
    return "".join(result), substitutions


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
    prepared, substitutions = _prepare_expansions(command)
    if re.search(r"[<>]\(", prepared):
        raise ShellShapeError("shell substitution cannot be inspected safely")
    lexer = shlex.shlex(_separate_unquoted_newlines(prepared), posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)
    commands: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        # Any run of ';' '&' '|' is a command separator: '&&', ';', '|', '||',
        # '&', ';;', and the '&' shlex splits out of a '2>&1' redirect.  A
        # pipeline hides nothing — splitting on it keeps every git call in its
        # own segment, so inspection is strictly broader than refusing to parse.
        if token and not token.strip(";&|"):
            if current:
                commands.append(current)
            current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    for substitution in substitutions:
        commands.extend(_split_commands(substitution))
    return commands


def _is_git_executable(token: str) -> bool:
    """Recognize ``git`` and path-qualified git executables alike."""
    return token == "git" or ("/" in token and os.path.basename(token) == "git")


def _contains_expansion(token: str) -> bool:
    return PARAM_EXPANSION in token or COMMAND_SUBSTITUTION in token


def _contains_runtime_expansion(token: str) -> bool:
    """Recognize dynamic shell syntax even after outer quote removal."""
    if _contains_expansion(token) or "`" in token or "$(" in token:
        return True
    return re.search(
        r"\$\{|\$(?:[A-Za-z_][A-Za-z0-9_]*|[0-9@*#?$!\-])",
        token,
    ) is not None


def _is_assignment(token: str) -> bool:
    name, separator, _ = token.partition("=")
    return bool(separator and name and (name[0].isalpha() or name[0] == "_")
                and name.replace("_", "").isalnum())


def _executable_index(tokens: list[str]) -> int | None:
    """Locate an executable through assignments and supported command wrappers."""
    index = 0
    while index < len(tokens) and _is_assignment(tokens[index]):
        index += 1
    while index < len(tokens):
        token = tokens[index]
        if _contains_expansion(token):
            raise ValueError("shell expansion in executable position cannot be inspected safely")
        executable = os.path.basename(token)
        if executable == "env":
            index += 1
            while index < len(tokens):
                token = tokens[index]
                if token == "--":
                    index += 1
                    break
                if token in {"-u", "--unset"}:
                    index += 2
                    continue
                if token.startswith("-") or _is_assignment(token):
                    index += 1
                    continue
                if _contains_expansion(token):
                    raise ValueError("shell expansion in executable position cannot be inspected safely")
                break
            continue
        if executable in {"command", "exec", "nohup"}:
            index += 1
            while index < len(tokens) and tokens[index] == "--":
                index += 1
            continue
        if executable == "sudo":
            index += 1
            options_with_values = {
                "-C", "-D", "-g", "-h", "-p", "-R", "-r", "-T", "-t", "-u",
                "--chdir", "--chroot", "--command-timeout", "--group", "--host",
                "--prompt", "--role", "--type", "--user",
            }
            while index < len(tokens):
                token = tokens[index]
                if token == "--":
                    index += 1
                    break
                if token in options_with_values:
                    index += 2
                    continue
                if token.startswith("-"):
                    index += 1
                    continue
                if _contains_expansion(token):
                    raise ValueError("shell expansion in executable position cannot be inspected safely")
                break
            continue
        return index
    return None


def _git_command(tokens: list[str]) -> list[str] | None:
    """Return git argv only for an unambiguous direct git invocation."""
    index = _executable_index(tokens)
    if index is None:
        return None
    executable = os.path.basename(tokens[index])
    if executable in {"bash", "dash", "ksh", "sh", "zsh"}:
        for arg_index, token in enumerate(tokens[index + 1 :], index + 1):
            if token == "-c" or (token.startswith("-") and "c" in token[1:]):
                if (
                    arg_index + 1 < len(tokens)
                    and _contains_runtime_expansion(tokens[arg_index + 1])
                ):
                    raise ValueError("dynamic shell command cannot be inspected safely")
                break
    elif executable == "eval" and any(
        _contains_runtime_expansion(token) for token in tokens[index + 1 :]
    ):
        raise ValueError("dynamic shell command cannot be inspected safely")
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
        if _contains_runtime_expansion(path):
            raise ValueError(f"git {action} cannot use shell expansion in path {path!r}")
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


def _validate_branch(args: list[str]) -> None:
    """Allow only branch listing forms, never branch creation or deletion."""
    if args in ([], ["--show-current"], ["--list"], ["-l"]):
        return
    if len(args) == 2 and args[0] in {"--list", "-l"} and not args[1].startswith("-"):
        return
    raise ValueError("git branch is allowed only for exact read-only listing forms")


def _validate_config(args: list[str]) -> None:
    """Allow a single proven read-only config lookup."""
    if len(args) == 2 and args[0] == "--get" and args[1] and not args[1].startswith("-"):
        return
    raise ValueError("git config is allowed only as git config --get <key>")


def _validate_remote(args: list[str]) -> None:
    """Allow remote enumeration and one named URL lookup, not mutation."""
    if args in ([], ["-v"], ["--verbose"]):
        return
    if len(args) == 2 and args[0] == "get-url" and args[1] and not args[1].startswith("-"):
        return
    raise ValueError("git remote is allowed only for listing or get-url <name>")


def _validate_push(directory: str | None, args: list[str]) -> None:
    """Allow an ordinary rooted push; refuse every history-destroying form.

    The conductor pushes (CLAUDE.md), so push must work. What is refused is the
    subset that can destroy a peer's published work: any force variant, remote
    branch deletion, and the bulk refspec forms that move refs nobody named.
    """
    if directory is None:
        raise ValueError("git push must use git -C <absolute-repository>")
    for arg in args:
        if arg in {"-f", "--force", "--force-with-lease", "--force-if-includes"}:
            raise ValueError("git push --force is forbidden — it destroys published peer commits")
        if arg.startswith("--force"):
            raise ValueError(f"git push {arg} is forbidden — no force variant is allowed")
        if arg in {"-d", "--delete", "--mirror", "--prune", "--all"}:
            raise ValueError(f"git push {arg} is forbidden — it can delete or bulk-move remote refs")
        if arg.startswith("+"):
            raise ValueError(f"git push forced refspec {arg!r} is forbidden — '+' means force")


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
    elif subcommand == "push":
        _validate_push(directory, args)
    elif subcommand == "branch":
        _validate_branch(args)
    elif subcommand == "config":
        _validate_config(args)
    elif subcommand == "remote":
        _validate_remote(args)
    elif subcommand in READ_ONLY_SUBCOMMANDS:
        return
    elif subcommand in {"fetch", "tag"}:
        # These may be legitimate conductor operations but must still be rooted.
        if directory is None:
            raise ValueError(f"git {subcommand} must use git -C <absolute-repository>")
    else:
        # Deny-by-default fallthrough: this subcommand is UNRECOGNIZED, not
        # deliberately banned. Say so — the old wording read as a considered
        # policy decision and sent a debugging session hunting for a ban that
        # was never written (2026-07-26: `git push` was refused here purely
        # because nobody had added it, and the message hid that).
        raise ValueError(
            f"git {subcommand} is unrecognized by the shared-worktree policy "
            f"(deny-by-default). If it is legitimate, add a branch for it in "
            f"scripts/lib/git_policy.py — it was omitted, not forbidden."
        )


def _mentions_git(command: str) -> bool:
    """Report whether the raw command string names git at all."""
    return re.search(r"\bgit\b", command) is not None


def validate_shell(command: str) -> Decision:
    """Validate all direct git calls inside a shell command string."""
    try:
        for tokens in _split_commands(command):
            git_argv = _git_command(tokens)
            if git_argv is not None:
                _validate_git(git_argv)
    except ShellShapeError as exc:
        # The splitter could not break this string apart, but nothing in it
        # names git — an unrelated curl or grep must not be denied on a git
        # rule.  Refusals raised once an executable is in hand (an expansion
        # in executable position, a dynamic `bash -c`, an indirect git) are
        # plain ValueError and still deny below: those forms can hide git.
        if not _mentions_git(command):
            return Decision(True)
        return Decision(False, str(exc))
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
