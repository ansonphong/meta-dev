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


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add(findings, level, code, path, message):
    findings.append({"level": level, "code": code, "path": path.as_posix(), "message": message})


def within(root: Path, candidate: Path) -> bool:
    return candidate == root or root in candidate.parents


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
    if (root / ".agents" / "skills").is_symlink():
        result["state"] = "conflict"
        result["reason"] = "skill_root_symlink"
        return result
    if canonical.is_symlink() or (canonical.exists() and not canonical.is_file()):
        result["state"] = "conflict"
        result["reason"] = "canonical_not_regular"
        return result
    if any(path.is_symlink() for path in legacy_present):
        result["state"] = "conflict"
        result["reason"] = "legacy_symlink"
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
        if not adapter.is_file() or adapter.is_symlink() or adapter.read_bytes() != b"@../AGENTS.md\n":
            add(findings, "error", "claude_adapter", adapter, "adapter must be exactly @../AGENTS.md")
        elif adapter.stat().st_size > 1024:
            add(findings, "error", "adapter_bytes", adapter, "adapter exceeds 1,024 bytes")
    if "context" in selected:
        context = root / "docs" / "agent-context"
        if context.exists() and context.is_symlink():
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
        if source.is_symlink():
            add(findings, "error", "skill_root_symlink", source, "canonical skill root must not be a symlink")
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
        manifest = root / ".claude" / "skills" / ".agent-skill-adapters.json"
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                source = root / ".agents" / "skills"
                canonical = {str(p.relative_to(source)): digest(p) for p in source.rglob("*") if p.is_file()} if source.exists() else {}
                if data.get("files", {}) != canonical:
                    add(findings, "error", "adapter_manifest", manifest, "adapter manifest differs from canonical source")
                for rel, expected in data.get("files", {}).items():
                    path = root / ".claude" / "skills" / rel
                    if not path.is_file() or path.is_symlink() or digest(path) != expected:
                        add(findings, "error", "adapter_mismatch", path, "generated adapter differs from manifest")
            except (json.JSONDecodeError, OSError):
                add(findings, "error", "adapter_manifest", manifest, "invalid adapter manifest")
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
    if "capabilities" in selected and manifest_data and not manifest_data.get("host_capability_matrix"):
        add(findings, "error", "capability_matrix", root, "manifest lacks host capability matrix")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--project-root")
    group.add_argument("--manifest")
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--check", choices=CHECKS, action="append")
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
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    findings = [f for project in report_projects for f in project["findings"]]
    if args.classify:
        print(json.dumps({"projects": report_projects}, sort_keys=True, separators=(",", ":")))
        return 0
    canonical = all(project["contract"]["state"] in {"canonical", "adapter"} for project in report_projects)
    ok = not any(f["level"] == "error" for f in findings) and (canonical or not args.require_canonical)
    print(json.dumps({"checks": list(selected), "ok": ok, "projects": report_projects}, sort_keys=True, separators=(",", ":")))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
