#!/usr/bin/env python3
"""Validate rendered and legacy plans without executing their verification hooks."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import importlib.util
from pathlib import Path
import re
import shlex
import sys


TASK = re.compile(r"^#{2,3} Task T?([0-9a-z]+\.[0-9a-z]+)\b", re.I | re.M)
FIELD = re.compile(r"^(?:\*\*)?([A-Za-z][A-Za-z -]*):(?:\*\*)?\s*(.*)$")
CHECKBOX = re.compile(r"^\s*[-*] \[[ xX~!>-]\]", re.M)
HANDLE = re.compile(r"\bT([0-9a-z]+\.[0-9a-z]+)\b", re.I)


def outside_fences(text: str) -> str:
    lines = []
    fence = None
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            marker = match[1]
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            lines.append("")
        else:
            lines.append(line if fence is None else "")
    return "\n".join(lines)


def target_of(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    frontmatter = text.split("\n---", 1)[0]
    match = re.search(r"^target:\s*([^\n]+)", frontmatter, re.M)
    return match[1].strip().strip("\"'") if match else None


def fields(body: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    current = None
    for line in body.splitlines():
        match = FIELD.match(line)
        if match:
            current = match[1].lower()
            result[current].append(match[2])
        elif re.match(r"^#{1,6} ", line):
            current = None
        elif current:
            result[current][-1] += "\n" + line
    return result


def declared_paths(sections: dict[str, list[str]]) -> list[str]:
    paths = []
    for section in sections.get("files", []):
        for line in section.splitlines():
            # v1.0 bullets and v1.1 table rows. Do not include anchors/purpose.
            match = re.match(r"^\s*(?:[-*]\s+(?:(?:Modify|Create|Delete):\s*)?|\|\s*)`([^`]+)`", line)
            if match:
                paths.append(match[1])
    for action in ("modify", "create", "delete"):
        for value in sections.get(action, []):
            paths.extend(re.findall(r"`([^`]+)`", value.splitlines()[0]))
    return paths


def verify_commands(section: str) -> list[str]:
    commands = []
    for line in section.splitlines():
        line = re.sub(r"^\s*[-*]\s+(?:\[[ xX]\]\s*)?", "", line).strip()
        if not line or line.startswith(("From:", "Expected:")):
            continue
        match = re.match(r"(?:Run:\s*)?`([^`]+)`", line)
        if match:
            commands.append(match[1])
        elif re.match(r"(?:manual|by[ -](?:eye|hand))\b", line, re.I):
            commands.append(line)
    return commands


class Validator:
    def __init__(self) -> None:
        self.errors = 0
        self.warnings = 0
        spec = importlib.util.spec_from_file_location("planner_verify_scope", Path(__file__).with_name("verify-scope.py"))
        self.scope = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.scope
        spec.loader.exec_module(self.scope)

    def error(self, message: str) -> None:
        self.errors += 1
        print(f"ERR: {message}")

    def warn(self, message: str) -> None:
        self.warnings += 1
        print(f"WARN: {message}")

    def discover(self, path: Path) -> tuple[Path | None, list[Path]]:
        if not path.exists():
            self.error(f"plan does not exist: {path}")
            return None, []
        master = path / "00-master-plan.md" if path.is_dir() else path
        if master.is_file():
            text = outside_fences(master.read_text(encoding="utf-8"))
            phase_lines = re.findall(r"^#{2,3} Phase [^\n]+", text, re.M)
            links = [link for line in phase_lines for link in re.findall(r"\]\(([^)]+)\)", line)]
            if links:
                files = []
                for link in links:
                    member = (master.parent / link).resolve()
                    if not member.is_relative_to(master.parent.resolve()) or member.suffix != ".md":
                        self.error(f"{master.name}: unsafe phase link: {link}")
                    elif not member.is_file():
                        self.error(f"{master.name}: missing phase file: {link}")
                    elif member in files or member == master.resolve():
                        self.error(f"{master.name}: duplicate/self phase link: {link}")
                    else:
                        files.append(member)
                for member in master.parent.glob("*.md"):
                    if member.resolve() not in files and member.resolve() != master.resolve() and TASK.search(outside_fences(member.read_text(encoding="utf-8"))):
                        self.error(f"{member.name}: task detail file is not linked by the master")
                return master, files
            if TASK.search(text):
                return None, [master]
            self.error(f"{master.name}: no task details or linked phases")
            return master, []
        files = [member for member in sorted(path.glob("*.md")) if TASK.search(outside_fences(member.read_text(encoding="utf-8")))] if path.is_dir() else []
        return None, files

    def validate(self, path: Path) -> int:
        master, files = self.discover(path)
        master_text = outside_fences(master.read_text(encoding="utf-8")) if master else ""
        target = target_of(master_text) if master else None
        all_handles = []
        for file in files:
            text = outside_fences(file.read_text(encoding="utf-8"))
            local_target = target_of(text)
            if master and local_target and local_target != (target or "standard"):
                self.error(f"{file.name}: phase target conflicts with master target")
            effective_target = target or local_target or "standard"
            if effective_target not in {"lean", "standard", "explicit"}:
                self.error(f"{file.name}: unknown target {effective_target!r}")
            if master and CHECKBOX.search(text):
                self.error(f"{file.name}: phase checkboxes duplicate the master's sole ledger")
            if re.search(r"\b(?:TBD|TODO|coming soon|placeholder)\b", text, re.I):
                self.error(f"{file.name}: contains TBD/TODO/placeholder outside code blocks")
            for declared in re.findall(r"Modify:\s*`([^`]+)`", text):
                if not Path(declared).is_file() and not (file.parent.parent / declared).is_file():
                    self.warn(f"{file.name}: Modify file not found: {declared}")
            matches = list(TASK.finditer(text))
            if not matches:
                self.error(f"{file.name}: no task details found")
            phase_ids: dict[str, list[str]] = defaultdict(list)
            for index, match in enumerate(matches):
                handle = match[1]
                all_handles.append(handle)
                phase_ids[handle.split(".")[0]].append(handle.split(".")[1])
                label = f"{file.name}: T{handle}"
                body = text[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(text)]
                # Do not borrow verification or Files sections from plan-level appendices.
                boundary = re.search(r"^#{1,2} ", body, re.M)
                if boundary:
                    body = body[:boundary.start()]
                sections = fields(body)
                paths = declared_paths(sections)
                if len(sections.get("verify-after", [])) != 1:
                    self.error(f"{label}: requires exactly one Verify-After section")
                if len(sections.get("verify-before", [])) > 1:
                    self.error(f"{label}: duplicate Verify-Before section")
                for name in ("verify-before", "verify-after"):
                    for section in sections.get(name, []):
                        commands = verify_commands(section)
                        if not commands:
                            self.error(f"{label}: empty {name} hook")
                        for command in commands:
                            try:
                                classification = self.scope.classify(command, paths)
                                tokens = shlex.split(command)
                                if "-k" in tokens and re.search(r"\bpytest\b", command):
                                    self.error(f"{label}: pytest -k is forbidden; name an exact test file/node")
                                if classification.category not in {"focused", "scoped_check", "manual"}:
                                    self.error(f"{label}: {classification.category} Verify command: {command} ({classification.reason})")
                            except ValueError as exc:
                                self.error(f"{label}: invalid Verify command: {exc}")
            for phase, minors in phase_ids.items():
                cap = 6 if effective_target == "lean" else 3
                if len(minors) > cap:
                    self.warn(f"{file.name}: phase {phase} has {len(minors)} tasks (> {cap} for target {effective_target})")
                numeric = [int(minor) for minor in minors if minor.isdigit()]
                if len(numeric) == len(minors) and numeric != list(range(1, len(numeric) + 1)):
                    self.warn(f"{file.name}: non-sequential task numbering in phase {phase}")
            if not master:
                self.check_ledger(text, [match[1] for match in matches], file.name,
                                  required="## Task Checklist" in text)
        if not all_handles:
            self.error("no tasks scanned; supply a plan file or a directory containing a plan")
        for handle, count in Counter(all_handles).items():
            if count > 1:
                self.error(f"duplicate task detail T{handle} ({count} definitions)")
        if master:
            self.check_ledger(master_text, all_handles, master.name, required=True)
        print(f"Scanned {len(files)} task files, {len(all_handles)} tasks")
        print(f"=== planner-validate: {self.errors} errors, {self.warnings} warnings ===")
        return 2 if self.errors else 1 if self.warnings else 0

    def check_ledger(self, text: str, handles: list[str], label: str, required: bool = False) -> None:
        ledger = []
        for line in text.splitlines():
            if CHECKBOX.match(line):
                match = HANDLE.search(line)
                if match:
                    ledger.append(match[1])
        # Rich v1.1 single-file plans deliberately have no checkbox ledger.
        if required or ledger:
            if Counter(ledger) != Counter(handles) or len(ledger) != len(set(ledger)):
                self.error(f"{label}: checkbox ledger must match task details exactly once")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", nargs="?", default=".", type=Path)
    args = parser.parse_args()
    try:
        return Validator().validate(args.plan)
    except (OSError, UnicodeError) as exc:
        print(f"ERR: cannot read plan: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
