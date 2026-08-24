#!/usr/bin/env python3
"""Check a portable AGENTS-first project surface and emit stable JSON."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

CHECKS = ("inventory", "instructions", "context", "skills", "adapters", "capabilities", "case-fold", "legacy-references")
ALLOWED_DISPOSITIONS = {
    "canonical",
    "generated_adapter",
    "host_runtime",
    "historical_artifact",
    "personal_local_overlay",
    "retired",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add(findings, level, code, path, message):
    findings.append({"level": level, "code": code, "path": path.as_posix(), "message": message})


def within(root: Path, candidate: Path) -> bool:
    return candidate == root or root in candidate.parents


def first_repository_symlink(root: Path, path: Path) -> Path | None:
    """Return the first symlink from the repository root through path.

    ``root`` is already an explicitly selected, resolved project root. This
    deliberately ignores its filesystem ancestry: only repository-relative
    components are unsafe.
    """
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None
    current = root
    for component in relative.parts:
        current /= component
        if current.is_symlink():
            return current
    return None


def tree_entries(root: Path):
    """Yield every entry below root without traversing symlink directories."""
    for entry in sorted(root.iterdir(), key=lambda path: path.name):
        yield entry
        if entry.is_dir() and not entry.is_symlink():
            yield from tree_entries(entry)


def canonical_skill_tree(root: Path, source: Path) -> tuple[dict[str, str], set[str]]:
    """Return canonical adapter files and every descendant directory.

    The directory set intentionally includes empty resource directories.  It is
    relative to ``.agents/skills`` so it has the same stable shape as the
    generated ``.claude/skills`` mirror and its manifest.
    """
    if not source.is_dir() or first_repository_symlink(root, source):
        return {}, set()
    files = {}
    directories = set()
    for path in tree_entries(source):
        relative = path.relative_to(source).as_posix()
        if path.is_dir() and not path.is_symlink():
            directories.add(relative)
        elif path.is_file() and not path.is_symlink():
            files[relative] = digest(path)
    return files, directories


def resolve_workspace_manifest(workspace_root: str, manifest_value: str) -> tuple[Path, Path]:
    workspace = Path(workspace_root).resolve()
    manifest = Path(manifest_value)
    if manifest.is_absolute():
        raise ValueError("--manifest must be workspace-relative")
    target = (workspace / manifest).resolve()
    if not within(workspace, target):
        raise ValueError("--manifest resolves outside workspace root")
    return workspace, target


def classify_contract(root: Path) -> dict:
    """Classify discovery inputs once for doctor, wrappers, and initializer."""
    canonical = root / "AGENTS.md"
    candidates = [path for path in root.iterdir() if path.name.casefold() == "agents.md"] if root.is_dir() else []
    legacy_root = root / "CLAUDE.md"
    adapter = root / ".claude" / "CLAUDE.md"
    legacy_candidates = (legacy_root, adapter)
    legacy_present = [path for path in legacy_candidates if path.exists() or path.is_symlink()]
    compatibility = [path for path in legacy_present if path.is_file() and not path.is_symlink()]
    result = {"state": "missing", "compatibility_inputs": [path.as_posix() for path in compatibility]}
    if first_repository_symlink(root, root / ".agents" / "skills"):
        result["state"] = "conflict"
        result["reason"] = "skill_root_symlink"
        return result
    if canonical.is_symlink() or (canonical.exists() and not canonical.is_file()):
        result["state"] = "conflict"
        result["reason"] = "canonical_not_regular"
        return result
    if any(first_repository_symlink(root, path) for path in legacy_present):
        result["state"] = "conflict"
        result["reason"] = "legacy_symlink"
        return result
    if first_repository_symlink(root, adapter):
        result["state"] = "conflict"
        result["reason"] = "claude_adapter_symlink"
        return result
    if first_repository_symlink(root, root / ".claude" / "skills"):
        result["state"] = "conflict"
        result["reason"] = "adapter_root_symlink"
        return result
    if any(not path.is_file() for path in legacy_present):
        result["state"] = "conflict"
        result["reason"] = "legacy_not_regular"
        return result
    if canonical.is_file():
        others = [path for path in candidates if path != canonical]
        if others:
            canonical_stat = canonical.stat()
            hashes_match = True
            aliases = True
            for other in others:
                if other.is_symlink() or not other.is_file():
                    result["state"] = "conflict"; result["reason"] = "instruction_symlink"; return result
                other_stat = other.stat()
                aliases &= (canonical_stat.st_dev, canonical_stat.st_ino) == (other_stat.st_dev, other_stat.st_ino)
                hashes_match &= digest(canonical) == digest(other)
            result["state"] = "casefold_alias" if aliases else "duplicate_copy" if hashes_match else "conflict"
            return result
        if legacy_root in compatibility:
            result["state"] = "conflict"
            result["reason"] = "legacy_conflict"
        elif adapter in compatibility:
            if adapter.read_bytes() == b"@../AGENTS.md\n":
                result["state"] = "adapter"
            else:
                result["state"] = "conflict"
                result["reason"] = "adapter_content"
        else:
            result["state"] = "canonical"
        return result
    if compatibility:
        result["state"] = "compatibility"
    return result


def projects(args):
    if args.project_root:
        return [("project", Path(args.project_root).resolve())]
    workspace, manifest = resolve_workspace_manifest(args.workspace_root, args.manifest)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    repos = data.get("repositories", data.get("projects", {}))
    if not isinstance(repos, dict):
        raise ValueError("manifest repositories must be an object")
    result = []
    for name, relative in sorted(repos.items()):
        if not isinstance(relative, str):
            raise ValueError(f"manifest repository {name} must be a relative path")
        candidate = (workspace / relative).resolve()
        if Path(relative).is_absolute() or not within(workspace, candidate):
            raise ValueError(f"manifest repository escapes workspace: {name}")
        result.append((str(name), candidate))
    return result


def resolve_scope_files(args, report_projects) -> list[str]:
    """Resolve declared task files and bind them to selected project roots."""
    if not args.scope_file:
        return []
    anchor = Path(args.project_root).resolve() if args.project_root else Path(args.workspace_root).resolve()
    roots = [Path(project["root"]) for project in report_projects]
    resolved = []
    for value in args.scope_file:
        declared = (anchor / value) if not Path(value).is_absolute() else Path(value)
        candidate = declared.resolve()
        selected_root = next((root for root in roots if within(root, candidate)), None)
        if selected_root is None:
            raise ValueError(f"scope outside selected root: {value}")
        try:
            lexical = declared.relative_to(selected_root)
        except ValueError:
            # An absolute path may reach the selected root through an external
            # workspace alias. Do not reject that external ancestry.
            lexical = candidate.relative_to(selected_root)
        lexical = selected_root / lexical
        if first_repository_symlink(selected_root, lexical):
            raise ValueError(f"scope path contains a symlink component: {value}")
        if declared.is_symlink() or not declared.is_file():
            raise ValueError(f"scope must be an existing regular file: {value}")
        resolved.append(candidate.as_posix())
    return resolved


def nonempty_string(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_capability_matrix(manifest_data: dict, repository_ids) -> list[str]:
    """Validate the committed host-discovery contract without host probes."""
    errors = []
    matrix = manifest_data.get("host_capability_matrix")
    if not isinstance(matrix, dict):
        return ["manifest lacks a valid host capability matrix"]

    official = matrix.get("official_discovery_semantics")
    official_ok = isinstance(official, dict)
    if not official_ok:
        errors.append("official_discovery_semantics must be an object")
    else:
        for host in ("codex", "claude_code", "grok"):
            details = official.get(host)
            if not isinstance(details, dict) or not all(nonempty_string(details.get(field)) for field in ("source", "behavior")):
                errors.append(f"official_discovery_semantics.{host} requires non-empty source and behavior strings")

    live = matrix.get("live_grok_inspect")
    live_ok = isinstance(live, dict)
    live_valid = live_ok
    if not live_ok:
        errors.append("live_grok_inspect must be an object")
    else:
        for field in ("command", "version", "workspace_relative_cwd", "settings_source", "skills_summary", "observed_on"):
            if not nonempty_string(live.get(field)):
                errors.append(f"live_grok_inspect.{field} must be a non-empty string")
                live_valid = False
        instructions = live.get("project_instructions")
        if not isinstance(instructions, list) or not instructions or not all(nonempty_string(value) for value in instructions):
            errors.append("live_grok_inspect.project_instructions must be a non-empty string list")
            live_valid = False
        elif not any("AGENTS.md" in value for value in instructions) or not any("CLAUDE.md" in value for value in instructions):
            errors.append("live_grok_inspect.project_instructions must record AGENTS.md and CLAUDE.md compatibility")
            live_valid = False

    aliases = matrix.get("case_folded_aliases")
    expected_ids = {str(identifier) for identifier in repository_ids}
    if not isinstance(aliases, dict) or set(aliases) != expected_ids:
        errors.append("case_folded_aliases must contain exactly one entry per manifest repository")
    elif isinstance(aliases, dict):
        for identifier in sorted(expected_ids):
            alias = aliases[identifier]
            if not isinstance(alias, dict) or alias.get("case_fold") != identifier.casefold() or alias.get("classification") != "unique_ascii_lowercase":
                errors.append(f"case_folded_aliases.{identifier} must match its repository id")

    entries = manifest_data.get("entries")
    if not isinstance(entries, list):
        return errors + ["entries must be a list for capability validation"]
    settings_source = live.get("settings_source") if live_ok and nonempty_string(live.get("settings_source")) else None
    commands_visible = live_ok and nonempty_string(live.get("skills_summary")) and (
        ".claude/commands" in live["skills_summary"] and "visible" in live["skills_summary"].casefold()
    )
    grok_contract_ready = official_ok and isinstance(official.get("grok"), dict) and all(
        nonempty_string(official["grok"].get(field)) for field in ("source", "behavior")
    ) and live_valid
    observed_settings_found = False
    command_entries = []
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("inventory entry must be an object")
            continue
        if not entry:
            errors.append("inventory entry must not be empty")
        repository = entry.get("repository")
        repository_valid = nonempty_string(repository) and repository in expected_ids
        if not nonempty_string(repository):
            errors.append("inventory entry requires a non-empty repository string")
        elif repository not in expected_ids:
            errors.append(f"inventory entry repository {repository!r} is not a manifest repository id")
        path = entry.get("path")
        consumers = entry.get("consumers")
        grok_consumer = isinstance(consumers, list) and any(
            isinstance(consumer, str) and consumer.casefold() == "grok" for consumer in consumers
        )
        if path == settings_source and repository_valid and grok_consumer:
            observed_settings_found = True
        if isinstance(path, str) and path.startswith(".claude/commands/"):
            command_entries.append(entry)
        if grok_consumer and not grok_contract_ready:
            errors.append(f"inventory entry {path!r} claims Grok consumption without a valid Grok matrix")
        if not isinstance(path, str) or not path.startswith((".claude/", ".grok/", ".agents/")):
            continue
        grok_compatibility = entry.get("grok_compatibility")
        disposition = entry.get("disposition")
        if not nonempty_string(grok_compatibility):
            errors.append(f"vendor entry {path} requires grok_compatibility")
        if not isinstance(consumers, list) or not all(isinstance(consumer, str) for consumer in consumers):
            errors.append(f"vendor entry {path} requires a string-list consumers field")
            consumers = []
        if disposition not in ALLOWED_DISPOSITIONS:
            errors.append(f"vendor entry {path} has an invalid disposition")
        if entry.get("tracked") is True and (path == settings_source or path.startswith(".claude/commands/")) and not grok_consumer:
            errors.append(f"tracked Grok-discovered entry {path} must include Grok as a consumer")
    if settings_source and not observed_settings_found:
        errors.append("live_grok_inspect.settings_source requires an inventory entry with a valid repository and Grok consumer")
    if commands_visible and not command_entries:
        errors.append("live_grok_inspect.skills_summary claims visible .claude/commands but inventory has no command entries")
    return errors


def check_project(name, root, selected, manifest_data=None):
    findings = []
    contract = classify_contract(root)
    result = {"name": name, "root": str(root), "contract": contract, "findings": findings}
    agents = root / "AGENTS.md"
    for path in contract["compatibility_inputs"]:
        add(findings, "warning", "compatibility_input", Path(path), "legacy Claude compatibility input detected")
    if contract["state"] in {"casefold_alias", "duplicate_copy"}:
        add(findings, "warning", contract["state"], agents, f"contract classified as {contract['state']}")
    elif contract["state"] == "conflict":
        add(findings, "error", contract.get("reason", "conflict"), agents, "contract discovery conflict")
    if "instructions" in selected:
        if not agents.is_file() or agents.is_symlink():
            add(findings, "error", "missing_agents", agents, "root AGENTS.md must be a regular file")
        else:
            raw = agents.read_bytes()
            try:
                chars = len(raw.decode("utf-8"))
            except UnicodeDecodeError:
                chars = -1
                add(findings, "error", "agents_utf8", agents, "AGENTS.md must be UTF-8")
            result["agents"] = {"bytes": len(raw), "characters": chars}
            if len(raw) > 24000:
                add(findings, "error", "agents_bytes", agents, "AGENTS.md exceeds 24,000 UTF-8 bytes")
            if chars >= 40000:
                add(findings, "error", "agents_characters", agents, "AGENTS.md must be below 40,000 characters")
        root_claude = root / "CLAUDE.md"
        if root_claude.exists() or root_claude.is_symlink():
            add(findings, "error", "root_claude", root_claude, "root CLAUDE.md is forbidden")
        adapter = root / ".claude" / "CLAUDE.md"
        if first_repository_symlink(root, adapter):
            add(findings, "error", "claude_adapter_symlink", adapter, "adapter path cannot contain symlinks")
        elif not adapter.is_file() or adapter.is_symlink() or adapter.read_bytes() != b"@../AGENTS.md\n":
            add(findings, "error", "claude_adapter", adapter, "adapter must be exactly @../AGENTS.md")
        elif adapter.stat().st_size > 1024:
            add(findings, "error", "adapter_bytes", adapter, "adapter exceeds 1,024 bytes")
    if "context" in selected:
        context = root / "docs" / "agent-context"
        if first_repository_symlink(root, context):
            add(findings, "error", "context_symlink", context, "context must not be a symlink")
        for file in root.rglob("*.md"):
            if ".git" in file.parts or file.is_symlink():
                continue
            for target in re.findall(r"(?:docs/agent-context/|\.claude/context/)([^\s)`]+)", file.read_text(encoding="utf-8", errors="ignore")):
                candidate = (root / "docs" / "agent-context" / target)
                if not candidate.exists():
                    add(findings, "error", "context_link", file, f"missing context target {target}")
        for path in root.rglob("*"):
            if path.is_symlink() and (path.name.casefold() in {"agents.md", "claude.md"} or "agent-context" in path.parts):
                add(findings, "error", "instruction_symlink", path, "instruction and context symlinks are forbidden")
    if "case-fold" in selected:
        candidates = {p for p in root.iterdir() if p.name.casefold() == "agents.md"}
        if agents.exists():
            for alias_name in {agents.name.lower(), agents.name.upper()}:
                alias = agents.with_name(alias_name)
                if alias.is_file() and not alias.is_symlink():
                    candidates.add(alias)
            for other in candidates:
                if other == agents:
                    continue
                if other.is_symlink() or agents.is_symlink():
                    add(findings, "error", "instruction_symlink", other, "instruction symlinks are forbidden")
                    continue
                a, b = agents.stat(), other.stat()
                if (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino):
                    add(findings, "warning", "casefold_alias", other, "same inode case-fold alias")
                elif digest(agents) == digest(other):
                    add(findings, "warning", "duplicate_copy", other, "distinct same-hash duplicate")
                else:
                    add(findings, "error", "conflict", other, "case-folded instruction content conflicts")
    if "skills" in selected:
        source = root / ".agents" / "skills"
        if first_repository_symlink(root, source):
            add(findings, "error", "skill_root_symlink", source, "canonical skill root must not be a symlink")
        elif source.exists() and not source.is_dir():
            add(findings, "error", "skill_root", source, "canonical skill root must be a directory")
        elif source.exists():
            for skill in sorted(source.iterdir()):
                marker = skill / "SKILL.md"
                if not skill.is_dir() or skill.is_symlink() or not marker.is_file() or marker.is_symlink():
                    add(findings, "error", "skill_abi", skill, "skill requires a regular SKILL.md")
                    continue
                text = marker.read_text(encoding="utf-8", errors="ignore")
                if not text.startswith("---\n") or "\n---\n" not in text:
                    add(findings, "error", "skill_abi", marker, "SKILL.md requires YAML frontmatter")
                for item in skill.rglob("*"):
                    if item.is_symlink():
                        add(findings, "error", "skill_symlink", item, "skill resources cannot be symlinks")
    if "adapters" in selected:
        adapter_root = root / ".claude" / "skills"
        manifest = adapter_root / ".agent-skill-adapters.json"
        source = root / ".agents" / "skills"
        canonical_files, canonical_directories = canonical_skill_tree(root, source)
        if not first_repository_symlink(root, source) and source.exists() and not source.is_dir():
            add(findings, "error", "skill_root", source, "canonical skill root must be a directory")
        elif source.is_dir() and not first_repository_symlink(root, source):
            for path in tree_entries(source):
                if path.is_symlink():
                    add(findings, "error", "skill_symlink", path, "canonical skill tree cannot contain symlinks")
        if first_repository_symlink(root, adapter_root):
            add(findings, "error", "adapter_root_symlink", adapter_root, "generated adapter root must not be a symlink")
        elif adapter_root.exists() and not adapter_root.is_dir():
            add(findings, "error", "adapter_root", adapter_root, "generated adapter root must be a directory")
        else:
            if manifest.is_symlink() or (manifest.exists() and not manifest.is_file()):
                add(findings, "error", "adapter_manifest", manifest, "generated adapter manifest must be a regular file")
            elif adapter_root.is_dir() and not manifest.is_file():
                add(findings, "error", "adapter_manifest", manifest, "generated adapter root requires a manifest")
            elif canonical_files and not manifest.is_file():
                add(findings, "error", "adapter_manifest", manifest, "canonical skills require a generated adapter manifest")
            elif manifest.is_file():
                try:
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                    recorded_files = data.get("files") if isinstance(data, dict) else None
                    recorded_directories = data.get("directories") if isinstance(data, dict) else None
                    if (
                        not isinstance(recorded_files, dict)
                        or not isinstance(recorded_directories, list)
                        or not all(isinstance(path, str) for path in recorded_directories)
                        or recorded_files != canonical_files
                        or recorded_directories != sorted(canonical_directories)
                    ):
                        add(findings, "error", "adapter_manifest", manifest, "adapter manifest differs from canonical source")
                    for rel, expected in canonical_files.items():
                        path = adapter_root / rel
                        if not path.is_file() or path.is_symlink() or digest(path) != expected:
                            add(findings, "error", "adapter_mismatch", path, "generated adapter differs from manifest")
                    actual_directories = {
                        path.relative_to(adapter_root).as_posix()
                        for path in tree_entries(adapter_root)
                        if path.is_dir() and not path.is_symlink()
                    }
                    if actual_directories != canonical_directories:
                        add(findings, "error", "adapter_mismatch", adapter_root, "generated adapter directories differ from canonical source")
                except (json.JSONDecodeError, OSError):
                    add(findings, "error", "adapter_manifest", manifest, "invalid adapter manifest")
            if adapter_root.is_dir():
                allowed_files = set(canonical_files)
                allowed_directories = canonical_directories
                for path in tree_entries(adapter_root):
                    rel = path.relative_to(adapter_root).as_posix()
                    if path == manifest:
                        continue
                    if path.is_symlink():
                        add(findings, "error", "adapter_unexpected", path, "generated adapter tree cannot contain symlinks")
                    elif path.is_dir():
                        if rel not in allowed_directories:
                            add(findings, "error", "adapter_unexpected", path, "generated adapter tree contains an undeclared directory")
                    elif not path.is_file() or rel not in allowed_files:
                        add(findings, "error", "adapter_unexpected", path, "generated adapter tree contains an undeclared file")
    if "inventory" in selected and manifest_data:
        entries = manifest_data.get("entries", [])
        if any(not entry.get("disposition") for entry in entries):
            add(findings, "error", "inventory_disposition", root, "every inventory entry needs a disposition")
    if "legacy-references" in selected:
        for file in root.rglob("*"):
            if not file.is_file() or file.is_symlink() or ".git" in file.parts:
                continue
            if ".claude/context" in file.read_text(encoding="utf-8", errors="ignore") or ".claude/reference" in file.read_text(encoding="utf-8", errors="ignore"):
                add(findings, "error", "legacy_reference", file, "live file references retired Claude context path")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--project-root")
    group.add_argument("--manifest")
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--check", choices=CHECKS, action="append")
    parser.add_argument("--scope-file", action="append")
    parser.add_argument("--classify", action="store_true", help="emit only contract discovery state")
    parser.add_argument("--require-canonical", action="store_true", help="fail unless the target is canonical or a thin adapter")
    args = parser.parse_args(argv)
    selected = tuple(args.check or CHECKS)
    try:
        manifest_data = None
        if args.manifest:
            _, manifest = resolve_workspace_manifest(args.workspace_root, args.manifest)
            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        report_projects = [check_project(name, root, selected, manifest_data) for name, root in projects(args)]
        if "capabilities" in selected and manifest_data:
            capability_root = Path(report_projects[0]["root"]) if report_projects else Path(args.workspace_root).resolve()
            repositories = manifest_data.get("repositories", manifest_data.get("projects", {}))
            repository_ids = repositories.keys() if isinstance(repositories, dict) else []
            for message in validate_capability_matrix(manifest_data, repository_ids):
                add(report_projects[0]["findings"] if report_projects else [], "error", "capability_matrix", capability_root, message)
        scope_files = resolve_scope_files(args, report_projects)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    findings = [f for project in report_projects for f in project["findings"]]
    if args.classify:
        print(json.dumps({"projects": report_projects, "scope_files": scope_files}, sort_keys=True, separators=(",", ":")))
        return 0
    canonical = all(project["contract"]["state"] in {"canonical", "adapter"} for project in report_projects)
    ok = not any(f["level"] == "error" for f in findings) and (canonical or not args.require_canonical)
    print(json.dumps({"checks": list(selected), "ok": ok, "projects": report_projects, "scope_files": scope_files}, sort_keys=True, separators=(",", ":")))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
