#!/usr/bin/env python3
"""Destructive-command policy for git in a shared worktree.

ALLOW BY DEFAULT.  This module blocks the small set of git operations that can
destroy work someone else has not committed yet, and gets out of the way of
everything else.

It used to be the opposite — a deny-by-default allowlist that enumerated a
handful of blessed forms and refused every subcommand nobody had gotten around
to adding.  That shape produced a steady stream of absurd refusals:
``git merge --ff-only origin/main`` was denied because the allowlist matched
``["--ff-only"]`` exactly and naming the ref you want to fast-forward to was
"unrecognized"; ``git config --list``, ``git cat-file``, ``git grep``,
``git worktree list``, ``git branch -a`` and ``git restore --staged`` were all
denied for the same reason.  None of those can lose a byte of anyone's work.
Meanwhile the rule that actually mattered — do not sweep or destroy a peer's
in-flight edits — was buried under the noise, so the guard read as breakage
rather than protection and the real bans lost their force.

What is blocked, and why (these are the incidents, not a wish list):

* ``stash`` — worktree-GLOBAL.  On a tree with many concurrent agents it rips
  out every peer's in-flight work at once, and ``pop`` can silently lose it.
* ``reset --hard/--merge/--keep`` — overwrites the working tree.
* broad ``checkout``/``restore`` pathspecs (``.``, ``..``, a directory) —
  same, by another name.  Targeted single-file forms are allowed.
* ``clean -f/-x/-d`` — permanently deletes untracked files.
* ``rebase`` and non-fast-forward ``merge``/``pull`` — concurrent history
  rewrite on a 9p mount is this project's #1 corruption trigger.
* ``push --force``/``+refspec``/``--delete``/``--mirror`` — destroys published
  peer commits.  ``--force-with-lease`` is the safe form and is allowed.
* tree-wide staging (``add -A/-u/./<dir>``, ``commit -a``) — the 2026-07-05
  commit-sweep: stages EVERY dirty file under a path, including another live
  session's edits.
* ``commit --amend``, ``filter-branch``, ``filter-repo``, ``reflog expire``,
  ``update-ref -d``, ``branch -D``, ``gc --prune=now``, ``worktree remove
  --force`` — history and ref destruction.

Everything else — including ordinary ``add``, ``commit``, ``push``, ``fetch``,
``merge --ff-only <ref>``, and every subcommand not named above — is allowed
with no required flag shape and no mandatory ``-C``.

The parser is shell-aware: it walks ``&&`` chains, pipelines, newlines and
command substitutions so a destructive call cannot hide inside one.  When a
string genuinely cannot be parsed (dynamic ``bash -c "$cmd"``, an indirect
``$g``), it is NOT denied outright — the raw text is scanned for the
destructive forms above instead.  Refusing to run an uninspectable command is
what made the old policy feel like sabotage; scanning it keeps the real
protection without the collateral damage.
"""
from __future__ import annotations

import argparse
import os
import re
import shlex
import sys
from dataclasses import dataclass


PARAM_EXPANSION = "__META_PARAMETER_EXPANSION__"
COMMAND_SUBSTITUTION = "__META_COMMAND_SUBSTITUTION__"

# git global options that consume the following token, so the subcommand is not
# mistaken for their value.
GLOBAL_OPTIONS_WITH_VALUE = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
    "--super-prefix", "--config-env",
}

# Executables that re-execute one of their arguments as a shell command, so a
# git call can genuinely hide inside a string they are handed.  Anything not in
# this set receives its arguments as DATA.
SHELL_WRAPPERS = {
    "bash", "dash", "ksh", "sh", "zsh", "eval", "xargs", "timeout", "watch",
    "nice", "ionice", "flock", "ssh", "su", "script",
}


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ""


class ShellShapeError(ValueError):
    """A shell form the splitter cannot break into simple commands."""


class UninspectableError(ValueError):
    """A command that could hide a git call behind runtime expansion."""


# ---------------------------------------------------------------------------
# Shell splitting — unchanged in behavior, it was the part that worked.
# ---------------------------------------------------------------------------

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
    """Split simple commands so every git call lands in its own segment."""
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
    return re.search(r"\$\{|\$(?:[A-Za-z_][A-Za-z0-9_]*|[0-9@*#?$!\-])", token) is not None


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
            raise UninspectableError("shell expansion in executable position")
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
                    raise UninspectableError("shell expansion in executable position")
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
                    raise UninspectableError("shell expansion in executable position")
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
                    raise UninspectableError("dynamic shell command")
                break
    elif executable == "eval" and any(
        _contains_runtime_expansion(token) for token in tokens[index + 1 :]
    ):
        raise UninspectableError("dynamic shell command")
    if not _is_git_executable(tokens[index]):
        # Only a SHELL WRAPPER can turn an argument string back into a command.
        # This check used to run for every executable, so any argument that
        # merely contained the text "git " was treated as a hidden git call --
        # `python3 - <<'PY'` with "git reset --hard" in a string literal, a
        # grep for a git command, a commit message mentioning one, all denied.
        # Data is not a command; only wrappers re-execute their arguments.
        if executable in SHELL_WRAPPERS and any(
            _is_git_executable(token) or re.search(r"\bgit\s", token)
            for token in tokens[index + 1 :]
        ):
            raise UninspectableError("indirect git invocation")
        return None
    return tokens[index + 1 :]


def _parse_git(argv: list[str]) -> tuple[str | None, list[str]]:
    """Return the subcommand and its arguments, skipping git global options.

    Global options are skipped, never judged.  ``-C`` no longer has to be
    present or absolute: requiring it turned every ordinary ``git status`` in
    the right directory into a policy violation.  Directory discipline is a
    doctrine matter for CLAUDE.md, not something worth denying a command over.
    """
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in GLOBAL_OPTIONS_WITH_VALUE:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        return token, argv[index + 1 :]
    return None, []


# ---------------------------------------------------------------------------
# The destructive rules — the entire policy surface.
# ---------------------------------------------------------------------------

def _short_flags(args: list[str]) -> set[str]:
    """Collect letters from clustered short flags, e.g. ``-am`` -> {a, m}."""
    letters: set[str] = set()
    for arg in args:
        if re.fullmatch(r"-[A-Za-z]+", arg):
            letters.update(arg[1:])
    return letters


def _positional(args: list[str]) -> list[str]:
    """Positional arguments, honoring an explicit ``--`` pathspec separator."""
    if "--" in args:
        return args[args.index("--") + 1 :]
    return [arg for arg in args if not arg.startswith("-")]


def _is_broad_path(path: str) -> bool:
    """A pathspec that can reach files this command never named."""
    if path in {".", "..", "*", "./", "../", ":/"}:
        return True
    if path.startswith(":/") or path.startswith(":("):
        return True  # magic pathspecs like :/ (whole tree) or :(exclude)
    return path.endswith("/")


def _check_reset(args: list[str]) -> None:
    for mode in ("--hard", "--merge", "--keep"):
        if mode in args:
            raise ValueError(
                f"git reset {mode} overwrites the working tree and destroys uncommitted "
                f"changes. Commit first — committing is always recoverable."
            )


def _check_stash(args: list[str]) -> None:
    if args and args[0] in {"list", "show"}:
        return
    raise ValueError(
        "git stash is worktree-GLOBAL — on a tree with concurrent agents it rips out "
        "every peer's in-flight work at once, and 'pop' can silently lose it. "
        "Commit instead: 'git -C <abs-repo> commit -m <msg> -- <files>'."
    )


def _check_worktree_overwrite(subcommand: str, args: list[str]) -> None:
    if subcommand == "restore" and ("--staged" in args or "-S" in args) and "--worktree" not in args:
        return  # index-only; the working tree is untouched
    broad = [path for path in _positional(args) if _is_broad_path(path)]
    if broad:
        raise ValueError(
            f"git {subcommand} {broad[0]!r} overwrites every uncommitted change under that "
            f"path — in a shared tree that is a peer's work too. Name the exact files."
        )
    if subcommand == "restore" and not _positional(args):
        raise ValueError("git restore with no pathspec overwrites the whole working tree.")


def _check_clean(args: list[str]) -> None:
    if "-n" in args or "--dry-run" in args:
        return
    if _short_flags(args) & {"f", "x", "d"} or {"--force"} & set(args):
        raise ValueError("git clean permanently deletes untracked files. Use -n to preview.")


def _check_rebase(args: list[str]) -> None:
    if args and args[0] in {"--abort", "--quit"}:
        return  # pure recovery from a rebase already in progress
    raise ValueError(
        "git rebase is this project's #1 corruption trigger — concurrent history rewrite "
        "on a 9p mount caused a phantom mass-deletion. Use 'git fetch' then "
        "'git merge --ff-only'."
    )


def _check_sync(subcommand: str, args: list[str]) -> None:
    if args and args[0] in {"--abort", "--quit", "--continue"}:
        return
    if "--ff-only" in args:
        return
    raise ValueError(
        f"git {subcommand} without --ff-only can rewrite the working tree or start a "
        f"rebase. Use 'git {subcommand} --ff-only <remote> <branch>'; if the branches "
        f"have truly diverged, that is a decision for a human."
    )


def _check_push(args: list[str]) -> None:
    for arg in args:
        if arg in {"-f", "--force"} or (arg.startswith("--force") and not arg.startswith(
            ("--force-with-lease", "--force-if-includes")
        )):
            raise ValueError(
                "git push --force destroys published peer commits. Use "
                "--force-with-lease if you must."
            )
        if arg in {"-d", "--delete", "--mirror", "--prune"}:
            raise ValueError(f"git push {arg} deletes or bulk-moves remote refs.")
        if arg.startswith("+") and "/" in arg or arg.startswith("+refs"):
            raise ValueError(f"git push forced refspec {arg!r} is a force push ('+' means force).")
    if "f" in _short_flags(args):
        raise ValueError("git push -f destroys published peer commits. Use --force-with-lease.")


def _check_add(args: list[str]) -> None:
    if {"-A", "--all", "-u", "--update", "--no-ignore-removal"} & set(args) or _short_flags(args) & {"A", "u"}:
        raise ValueError(
            "git add -A/-u stages EVERY dirty file — in a shared tree that sweeps another "
            "session's in-flight edits into your commit (commit-sweep, 2026-07-05). "
            "Stage explicit paths: 'git -C <abs-repo> add -- <file> <file>'."
        )
    broad = [path for path in _positional(args) if _is_broad_path(path)]
    if broad:
        raise ValueError(
            f"git add {broad[0]!r} stages every dirty file under that path — same "
            f"commit-sweep. Stage explicit file paths."
        )


def _check_commit(args: list[str]) -> None:
    if "--amend" in args:
        raise ValueError(
            "git commit --amend rewrites a commit that may already be published or "
            "may be a peer's. Make a new commit instead."
        )
    if {"-a", "--all"} & set(args) or "a" in _short_flags(args):
        raise ValueError(
            "git commit -a stages every tracked modification — in a shared tree that "
            "absorbs a peer's in-flight edits. Name the paths: "
            "'git -C <abs-repo> commit -m <msg> -- <files>'."
        )


def _check_branch(args: list[str]) -> None:
    if "-D" in args or ({"-d", "--delete"} & set(args) and {"-f", "--force"} & set(args)):
        raise ValueError("git branch -D force-deletes a branch with no merge check.")


def _check_reflog(args: list[str]) -> None:
    if args and args[0] in {"expire", "delete"}:
        raise ValueError("git reflog expire/delete destroys the recovery log for lost commits.")


def _check_update_ref(args: list[str]) -> None:
    if "-d" in args or "--delete" in args or "--stdin" in args:
        raise ValueError("git update-ref -d deletes refs directly, bypassing every safety net.")


def _check_gc(args: list[str]) -> None:
    if any(arg.startswith("--prune=") and arg != "--prune=never" for arg in args):
        raise ValueError("git gc --prune=<now> drops unreachable objects a peer may still need.")


def _check_worktree(args: list[str]) -> None:
    if args and args[0] == "remove" and ({"-f", "--force"} & set(args)):
        raise ValueError("git worktree remove --force discards uncommitted work in that worktree.")


def _forbidden(name: str, why: str):
    def check(_args: list[str]) -> None:
        raise ValueError(f"git {name} {why}")
    return check


RULES = {
    "reset": _check_reset,
    "stash": _check_stash,
    "checkout": lambda args: _check_worktree_overwrite("checkout", args),
    "restore": lambda args: _check_worktree_overwrite("restore", args),
    "clean": _check_clean,
    "rebase": _check_rebase,
    "merge": lambda args: _check_sync("merge", args),
    "pull": lambda args: _check_sync("pull", args),
    "push": _check_push,
    "add": _check_add,
    "commit": _check_commit,
    "branch": _check_branch,
    "reflog": _check_reflog,
    "update-ref": _check_update_ref,
    "gc": _check_gc,
    "worktree": _check_worktree,
    "filter-branch": _forbidden("filter-branch", "rewrites every commit in the repository."),
    "filter-repo": _forbidden("filter-repo", "rewrites every commit in the repository."),
}


def _validate_git(argv: list[str]) -> None:
    """Raise ValueError only for a destructive form; everything else is allowed."""
    subcommand, args = _parse_git(argv)
    if subcommand is None:
        return  # bare `git`, `git --version`, `git --help` — harmless
    check = RULES.get(subcommand)
    if check is not None:
        check(args)


# ---------------------------------------------------------------------------
# Raw-text fallback for strings the parser cannot break apart.
# ---------------------------------------------------------------------------

# Each pattern names a destructive form directly.  `[^;&|]*` keeps a match
# inside one simple command so `git status; rm -rf x` cannot borrow the git
# from an earlier segment.
_SEGMENT = r"[^;&|]*"
RAW_DESTRUCTIVE: tuple[tuple[str, str], ...] = (
    (rf"\bgit\b{_SEGMENT}\breset\b{_SEGMENT}--(hard|merge|keep)\b", "git reset --hard destroys uncommitted changes"),
    (rf"\bgit\b{_SEGMENT}\bstash\b(?!\s+(list|show))", "git stash is worktree-global and destroys peer work"),
    (rf"\bgit\b{_SEGMENT}\bclean\b{_SEGMENT}-[A-Za-z]*[fxd]", "git clean deletes untracked files permanently"),
    (rf"\bgit\b{_SEGMENT}\brebase\b(?!\s+--(abort|quit))", "git rebase is the #1 9p corruption trigger"),
    (rf"\bgit\b{_SEGMENT}\bpush\b{_SEGMENT}(--force(?!-with-lease|-if-includes)|\s-f\b|--mirror\b|--delete\b)", "git push --force destroys published peer commits"),
    (rf"\bgit\b{_SEGMENT}\badd\b{_SEGMENT}(\s-[A-Za-z]*[Au]\b|--all\b|--update\b)", "git add -A/-u is a commit-sweep in a shared tree"),
    (rf"\bgit\b{_SEGMENT}\bcommit\b{_SEGMENT}(--amend\b|--all\b|\s-[A-Za-z]*a\b)", "git commit --amend/-a rewrites or sweeps shared work"),
    (rf"\bgit\b{_SEGMENT}\b(checkout|restore)\b{_SEGMENT}(--\s+)?\.(\s|$)", "broad git checkout/restore overwrites the working tree"),
    (rf"\bgit\b{_SEGMENT}\bfilter-(branch|repo)\b", "git filter-branch/filter-repo rewrites every commit"),
    (rf"\bgit\b{_SEGMENT}\bbranch\b{_SEGMENT}\s-D\b", "git branch -D force-deletes a branch"),
    (rf"\bgit\b{_SEGMENT}\breflog\b{_SEGMENT}\bexpire\b", "git reflog expire destroys the recovery log"),
    (rf"\bgit\b{_SEGMENT}\bupdate-ref\b{_SEGMENT}\s-d\b", "git update-ref -d deletes refs directly"),
    (rf"\bgit\b{_SEGMENT}\b(merge|pull)\b(?![^;&|]*--ff-only)(?![^;&|]*--abort)", "git merge/pull without --ff-only can rewrite the tree"),
)
RAW_COMPILED = tuple((re.compile(pattern), reason) for pattern, reason in RAW_DESTRUCTIVE)

# The same forms with the literal ``git`` dropped.  Only ever applied once the
# parser has already concluded a git call is hiding behind indirection —
# ``env MODE=safe $g -C /repo add -A`` never spells "git" anywhere, so the
# patterns above cannot see it.  Never applied to a command that parsed cleanly.
BARE_DESTRUCTIVE: tuple[tuple[str, str], ...] = (
    (rf"\breset\b{_SEGMENT}--(hard|merge|keep)\b", "git reset --hard destroys uncommitted changes"),
    (rf"\bstash\b(?!\s+(list|show))", "git stash is worktree-global and destroys peer work"),
    (rf"\bclean\b{_SEGMENT}\s-[A-Za-z]*[fxd]\b", "git clean deletes untracked files permanently"),
    (rf"\brebase\b(?!\s+--(abort|quit))", "git rebase is the #1 9p corruption trigger"),
    (rf"\bpush\b{_SEGMENT}(--force(?!-with-lease|-if-includes)|\s-f\b|--mirror\b)", "git push --force destroys published peer commits"),
    (rf"\badd\b{_SEGMENT}(\s-[A-Za-z]*[Au]\b|--all\b|--update\b)", "git add -A/-u is a commit-sweep in a shared tree"),
    (rf"\bcommit\b{_SEGMENT}(--amend\b|--all\b|\s-[A-Za-z]*a\b)", "git commit --amend/-a rewrites or sweeps shared work"),
    (rf"\bfilter-(branch|repo)\b", "git filter-branch/filter-repo rewrites every commit"),
    (rf"\bbranch\b{_SEGMENT}\s-D\b", "git branch -D force-deletes a branch"),
)
BARE_COMPILED = tuple((re.compile(pattern), reason) for pattern, reason in BARE_DESTRUCTIVE)


def _mentions_git(command: str) -> bool:
    """Report whether the raw command string names git at all."""
    return re.search(r"\bgit\b", command) is not None


def _scan_raw(command: str, *, context: str, bare: bool = False) -> Decision:
    """Text-scan a command the parser could not inspect structurally.

    The old policy denied these outright, which meant an ordinary
    ``bash -c "$build_cmd"`` was refused on a git rule.  Scanning instead
    keeps the destructive forms blocked while letting everything else run.
    """
    patterns = RAW_COMPILED + BARE_COMPILED if bare else RAW_COMPILED
    for pattern, reason in patterns:
        if pattern.search(command):
            return Decision(False, f"{reason} (seen in {context})")
    return Decision(True)


def validate_shell(command: str) -> Decision:
    """Allow the command unless it performs a destructive git operation."""
    try:
        segments = _split_commands(command)
    except ShellShapeError:
        if not _mentions_git(command):
            return Decision(True)
        return _scan_raw(command, context="an unparseable shell form")
    uninspected = ""
    for tokens in segments:
        try:
            git_argv = _git_command(tokens)
        except UninspectableError as exc:
            uninspected = str(exc)
            continue
        if git_argv is None:
            continue
        try:
            _validate_git(git_argv)
        except ValueError as exc:
            return Decision(False, str(exc))
    if uninspected:
        # A git call is hiding behind indirection. Scan the bare forms too —
        # the text may never spell "git" at all.
        return _scan_raw(command, context=uninspected, bare=True)
    return Decision(True)


# ---------------------------------------------------------------------------
# Non-git destructive commands.
#
# These live here, next to the shell splitter, for one reason: the hook used to
# grep for them and grep cannot tell a command from a string.  Writing a commit
# message that mentions ``rm -rf`` was denied as if it were one.  Checking the
# EXECUTABLE of each simple command instead makes the rule exact — and keeps the
# temp-path carve-out working, because the path is a real token rather than
# something a de-quoting pass has to guess at.
# ---------------------------------------------------------------------------

TEMP_PREFIXES = ("/tmp/", "/var/tmp/", "/dev/shm/")
TEMP_BASENAMES = {"tmp", ".tmp", "node_modules", "dist", "build", ".cache", "target", ".venv"}
DB_CLIENTS = {
    "psql", "mysql", "mariadb", "sqlite3", "mongo", "mongosh", "duckdb",
    "clickhouse-client", "cockroach", "pgcli", "mycli", "sqlcmd",
}
SQL_DESTRUCTIVE = (
    (re.compile(r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b", re.I), "DROP TABLE/DATABASE is irreversible data destruction."),
    (re.compile(r"\bTRUNCATE\s+TABLE\b", re.I), "TRUNCATE TABLE deletes every row irreversibly."),
    (re.compile(r"\bDELETE\s+FROM\s+[A-Za-z_][\w.\"]*\s*;?\s*$", re.I), "DELETE FROM with no WHERE clause deletes every row. Add a WHERE filter."),
)


def _is_temp_path(path: str) -> bool:
    normalized = path.strip("'\"")
    if normalized.startswith(TEMP_PREFIXES) or normalized.startswith("$TMPDIR"):
        return True
    if PARAM_EXPANSION in normalized and "TMP" in normalized:
        return True
    parts = [part for part in normalized.replace("\\", "/").split("/") if part not in {"", "."}]
    return any(part in TEMP_BASENAMES for part in parts)


def _check_rm(args: list[str]) -> str | None:
    """Flag a recursive delete whose targets are not all temp/build paths."""
    recursive = bool(_short_flags(args) & {"r", "R"}) or "--recursive" in args
    targets = [arg for arg in args if not arg.startswith("-")]
    if any(target.strip("'\"").endswith(".git/index") for target in targets):
        return (
            "rm .git/index destroys the git index — NEVER do this. Remove only "
            ".git/index.lock, then stage explicit paths."
        )
    if not recursive:
        return None
    if targets and all(_is_temp_path(target) for target in targets):
        return None
    return (
        "Recursive delete (rm -rf) outside a temp/build path. Verify the target "
        "carefully — this is irreversible."
    )


def _check_sql(segments: list[list[str]]) -> str | None:
    """Flag destructive SQL on a database command line, or typed bare as one.

    The gate matters: without it, ``git commit -m 'why DROP TABLE is blocked'``
    reads as a DROP because the words appear in the string.  A statement in
    EXECUTABLE position is unambiguous, and so is any line invoking a client.
    """
    for tokens in segments:
        if tokens and tokens[0].strip("'\"").upper() in {"DROP", "TRUNCATE", "DELETE"}:
            statement = " ".join(tokens)
            for pattern, reason in SQL_DESTRUCTIVE:
                if pattern.search(statement):
                    return reason
    involves_db = any(
        os.path.basename(token.strip("'\"")) in DB_CLIENTS
        for tokens in segments for token in tokens
    )
    if not involves_db:
        return None
    for tokens in segments:
        for token in tokens:
            for pattern, reason in SQL_DESTRUCTIVE:
                if pattern.search(token):
                    return reason
    return None


def validate_destructive(command: str) -> tuple[Decision, str]:
    """Check the non-git destructive rules. Returns (decision, config category)."""
    try:
        segments = _split_commands(command)
    except ShellShapeError:
        return Decision(True), ""
    for tokens in segments:
        try:
            index = _executable_index(tokens)
        except UninspectableError:
            continue
        if index is None:
            continue
        if os.path.basename(tokens[index].strip("'\"")) == "rm":
            reason = _check_rm(tokens[index + 1 :])
            if reason:
                category = "rm_git_index" if ".git/index" in reason else "rm_rf_non_temp"
                return Decision(False, reason), category
    reason = _check_sql(segments)
    if reason:
        return Decision(False, reason), "drop_table"
    return Decision(True), ""


def main() -> int:
    parser = argparse.ArgumentParser(description="validate a shell command against the destructive-command policy")
    parser.add_argument("--command", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--guard", action="store_true",
                        help="also apply the non-git rules and report the config category as JSON")
    args = parser.parse_args()
    if args.guard:
        import json
        decision = validate_shell(args.command)
        category = "git"
        if decision.allowed:
            decision, category = validate_destructive(args.command)
        print(json.dumps({
            "allowed": decision.allowed,
            "reason": decision.reason,
            "category": category if not decision.allowed else "",
        }))
        return 0
    decision = validate_shell(args.command)
    if args.json:
        import json
        print(json.dumps({"allowed": decision.allowed, "reason": decision.reason}))
    elif not decision.allowed:
        print(decision.reason, file=sys.stderr)
    return 0 if decision.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
