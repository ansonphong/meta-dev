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
from urllib.parse import unquote

import yaml

CHECKS = ("inventory", "instructions", "context", "skills", "adapters", "capabilities", "case-fold", "legacy-references")
ALLOWED_DISPOSITIONS = {
    "canonical",
    "generated_adapter",
    "host_runtime",
    "historical_artifact",
    "personal_local_overlay",
    "retired",
}
SKILL_FRONTMATTER_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
SKILL_RESOURCE_ROOTS = {"scripts", "references", "assets"}
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REFERENCE_DEFINITION_RE = re.compile(
    r"(?m)^[ \t]{0,3}\[(?:\\.|[^\]\\\n])+\]:[ \t]*(?:<(?P<angle>(?:\\.|[^>\n])*)>|(?P<plain>(?:\\.|[^\s])+))"
)
MARKDOWN_ESCAPE_RE = re.compile(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~])")


class DuplicateKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate keys at every mapping level."""


def construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise yaml.YAMLError("mapping keys must be strings")
        if key in mapping:
            raise yaml.YAMLError(f"duplicate mapping key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


DuplicateKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_unique_mapping
)


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


def skill_frontmatter_and_body(marker: Path) -> tuple[dict, str]:
    """Read one canonical SKILL.md with an explicit YAML frontmatter fence."""
    text = marker.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md requires YAML frontmatter starting on line one")
    closing = text.find("\n---\n", 4)
    if closing < 0:
        raise ValueError("SKILL.md requires a closing YAML frontmatter fence")
    frontmatter = text[4:closing]
    body = text[closing + 5:]
    data = yaml.load(frontmatter, Loader=DuplicateKeySafeLoader)
    if not isinstance(data, dict):
        raise ValueError("SKILL.md frontmatter must be a YAML mapping")
    return data, body


def unescaped_closing(text: str, start: int, opening: str, closing: str) -> int | None:
    """Find the matching Markdown delimiter while preserving escaped syntax."""
    depth = 1
    index = start + 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == opening:
            depth += 1
        elif text[index] == closing:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def inline_markdown_destinations(body: str):
    """Yield raw destinations from inline Markdown links and images."""
    index = 0
    while index < len(body):
        if body[index] != "[" or (index and body[index - 1] == "\\"):
            index += 1
            continue
        label_end = unescaped_closing(body, index, "[", "]")
        if label_end is None or label_end + 1 >= len(body) or body[label_end + 1] != "(":
            index += 1
            continue
        destination_end = unescaped_closing(body, label_end + 1, "(", ")")
        if destination_end is None:
            index = label_end + 1
            continue
        yield body[label_end + 2:destination_end]
        index = destination_end + 1


def markdown_destination(value: str) -> str | None:
    """Extract one destination, excluding an optional CommonMark title."""
    value = value.strip()
    if not value:
        return None
    if value.startswith("<"):
        index = 1
        while index < len(value):
            if value[index] == "\\":
                index += 2
                continue
            if value[index] == ">":
                return value[1:index]
            index += 1
        return None
    index = 0
    while index < len(value):
        if value[index] == "\\":
            index += 2
            continue
        if value[index].isspace():
            break
        index += 1
    return value[:index] or None


def local_markdown_path(destination: str) -> str | None:
    """Return a local filesystem path from one Markdown destination."""
    index = 0
    while index < len(destination):
        if destination[index] == "\\":
            index += 2
            continue
        if destination[index] in "#?":
            destination = destination[:index]
            break
        index += 1
    path = unquote(MARKDOWN_ESCAPE_RE.sub(r"\1", destination))
    if not path:
        return None
    if re.match(r"^[A-Za-z]:[\\/]", path):
        return path
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", path):
        return None
    return path


def local_markdown_targets(body: str):
    """Yield every local inline or reference-definition Markdown destination."""
    destinations = [markdown_destination(destination) for destination in inline_markdown_destinations(body)]
    for match in REFERENCE_DEFINITION_RE.finditer(body):
        destinations.append(match.group("angle") if match.group("angle") is not None else match.group("plain"))
    for destination in destinations:
        path = local_markdown_path(destination or "")
        if path is not None:
            yield path


def validate_skill_abi(root: Path, skill: Path, findings) -> None:
    """Validate the portable Agent Skills ABI for one canonical skill."""
    marker = skill / "SKILL.md"
    if not skill.is_dir() or skill.is_symlink() or not marker.is_file() or marker.is_symlink():
        add(findings, "error", "skill_abi", skill, "skill requires a regular SKILL.md")
        return

    entries = list(skill.iterdir())
    for entry in entries:
        if entry.name == "SKILL.md":
            continue
        if entry.name not in SKILL_RESOURCE_ROOTS or not entry.is_dir() or entry.is_symlink():
            add(findings, "error", "skill_abi", entry, "canonical skill entries must be SKILL.md, scripts/, references/, or assets/")

    try:
        frontmatter, body = skill_frontmatter_and_body(marker)
    except (OSError, UnicodeDecodeError, ValueError, yaml.YAMLError) as error:
        add(findings, "error", "skill_abi", marker, f"invalid portable SKILL.md frontmatter: {error}")
        frontmatter, body = None, ""

    if frontmatter is not None:
        unexpected = sorted(set(frontmatter) - SKILL_FRONTMATTER_FIELDS)
        if unexpected:
            add(findings, "error", "skill_abi", marker, f"canonical frontmatter has non-standard fields: {', '.join(unexpected)}")
        name = frontmatter.get("name")
        if not isinstance(name, str) or not (1 <= len(name) <= 64) or not SKILL_NAME_RE.fullmatch(name):
            add(findings, "error", "skill_abi", marker, "frontmatter name must be 1-64 lowercase letters, numbers, or single hyphens")
        elif name != skill.name:
            add(findings, "error", "skill_abi", marker, "frontmatter name must match the skill directory name")
        description = frontmatter.get("description")
        if not isinstance(description, str) or not (1 <= len(description) <= 1024):
            add(findings, "error", "skill_abi", marker, "frontmatter description must be a non-empty string no longer than 1,024 characters")
        license_value = frontmatter.get("license")
        if license_value is not None and (not isinstance(license_value, str) or not license_value.strip()):
            add(findings, "error", "skill_abi", marker, "frontmatter license must be a non-empty string when provided")
        compatibility = frontmatter.get("compatibility")
        if compatibility is not None and (not isinstance(compatibility, str) or not (1 <= len(compatibility) <= 500)):
            add(findings, "error", "skill_abi", marker, "frontmatter compatibility must be a 1-500 character string when provided")
        metadata = frontmatter.get("metadata")
        if metadata is not None and (
            not isinstance(metadata, dict)
            or not all(isinstance(key, str) and isinstance(value, str) for key, value in metadata.items())
        ):
            add(findings, "error", "skill_abi", marker, "frontmatter metadata must map string keys to string values")
        allowed_tools = frontmatter.get("allowed-tools")
        if allowed_tools is not None and (not isinstance(allowed_tools, str) or not allowed_tools.strip()):
            add(findings, "error", "skill_abi", marker, "frontmatter allowed-tools must be a non-empty string when provided")

        if not body.strip():
            add(findings, "error", "skill_abi", marker, "SKILL.md requires a non-empty Markdown body")
        arguments = re.search(r"(?m)^## Arguments\s*$", body)
        if not arguments:
            add(findings, "error", "skill_abi", marker, "SKILL.md body requires a portable ## Arguments section")
        else:
            section = body[arguments.end():]
            section = re.split(r"(?m)^##(?:\s|$)", section, maxsplit=1)[0]
            if not section.strip():
                add(findings, "error", "skill_abi", marker, "## Arguments must state accepted arguments or None")

        for target in local_markdown_targets(body):
            candidate = skill / target
            resolved = candidate.resolve()
            if re.match(r"^[A-Za-z]:[\\/]", target) or target.startswith("\\") or not within(skill.resolve(), resolved):
                add(findings, "error", "skill_abi", marker, f"local skill link escapes the skill root: {target}")
            elif not candidate.is_file() or candidate.is_symlink() or first_repository_symlink(root, candidate):
                add(findings, "error", "skill_abi", marker, f"local skill link must resolve to a regular in-skill resource: {target}")

    for item in tree_entries(skill):
        if item.is_symlink():
            add(findings, "error", "skill_symlink", item, "skill resources cannot be symlinks")


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
    if first_repository_symlink(root, root / "docs" / "agent-context"):
        result["state"] = "conflict"
        result["reason"] = "context_symlink"
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


LEGACY_REFERENCE_TREES = (".agents", ".claude", ".grok", "docs/agent-context")
LEGACY_NON_LIVE_DISPOSITIONS = {"historical_artifact", "personal_local_overlay", "retired"}


def live_legacy_targets(root: Path, repository, manifest_data, findings) -> list[Path]:
    """Return the live consumer files that must not reference retired context paths.

    Only the operational surface is live: the canonical contract, the adapter, the
    host-facing runtime trees, the neutral context, and manifest inventory entries
    that remain live and belong to this repository. The doctor's own source, tests,
    fixtures, historical plans, and migration documentation are not live consumers
    and must not be scanned. Inventory paths that are absolute, contain a `..`
    traversal component, escape the repository root, or pass through a symlink are
    reported as errors instead of being silently skipped.
    """
    seen: set[str] = set()
    targets: list[Path] = []

    def collect(path: Path) -> None:
        if path.is_file() and not path.is_symlink():
            key = path.as_posix()
            if key not in seen:
                seen.add(key)
                targets.append(path)

    for rel in ("AGENTS.md", ".claude/CLAUDE.md"):
        collect(root / rel)
    for rel in LEGACY_REFERENCE_TREES:
        base = root / rel
        if base.is_dir() and not first_repository_symlink(root, base):
            for path in tree_entries(base):
                collect(path)
    entries = (manifest_data or {}).get("entries")
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("disposition") in LEGACY_NON_LIVE_DISPOSITIONS:
                continue
            if entry.get("repository") != repository:
                continue
            rel = entry.get("path")
            if not isinstance(rel, str):
                continue
            candidate = root / rel
            if Path(rel).is_absolute():
                add(findings, "error", "inventory_absolute", candidate, "inventory entry path must be repository-relative")
                continue
            if ".." in Path(rel).parts:
                add(findings, "error", "inventory_escape", candidate, "inventory entry path must not contain a '..' traversal component")
                continue
            if not within(root, candidate.resolve()):
                add(findings, "error", "inventory_escape", candidate, "inventory entry path escapes the repository root")
                continue
            if first_repository_symlink(root, candidate):
                add(findings, "error", "inventory_symlink", candidate, "inventory entry path contains a symlink component")
                continue
            collect(candidate)
    return targets


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
                validate_skill_abi(root, skill, findings)
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
        for file in live_legacy_targets(root, name, manifest_data, findings):
            text = file.read_text(encoding="utf-8", errors="ignore")
            if ".claude/context" in text or ".claude/reference" in text:
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
