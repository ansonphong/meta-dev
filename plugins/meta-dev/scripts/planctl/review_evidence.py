"""Content-bound review evidence; unrelated and ledger-only commits stay valid."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

from planctl import parse


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if result.returncode:
        raise ValueError("git review evidence failed: " + result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def _normalize_contract(text):
    lines = text.splitlines()
    in_frontmatter = bool(lines and lines[0] == "---")
    result = []
    for index, line in enumerate(lines):
        if in_frontmatter and index and line == "---":
            in_frontmatter = False
        if in_frontmatter and re.match(r"^(?:stage|stage_state|status|updated):", line):
            continue
        result.append(re.sub(r"^(\s*[-*]\s+)\[[ xX]\]", r"\1[ ]", line))
    return "\n".join(result).encode("utf-8")


def contract_evidence(plan_path):
    plan = Path(plan_path).resolve(strict=True)
    content = plan.read_text(encoding="utf-8")
    files = {plan: content}
    for line in content.splitlines():
        if re.match(r"^#{2,3} Phase ", line):
            for link in re.findall(r"\]\(([^)]+)\)", line):
                child = (plan.parent / link).resolve(strict=True)
                if child.suffix != ".md" or not child.is_relative_to(plan.parent):
                    raise ValueError("review phase link must remain inside its plan directory")
                files[child] = child.read_text(encoding="utf-8")
    contracts = []
    inventory = []
    for path, text in sorted(files.items()):
        contracts.append((path.name, _digest(_normalize_contract(text))))
        tasks, error = parse.parse_tasks(text)
        if error:
            raise ValueError("ambiguous plan task inventory: " + error)
        inventory.extend((path.name, task.tid, task.alias, task.section, task.text) for task in tasks)
    if not inventory:
        raise ValueError("review PASS requires a canonical task ledger; re-render legacy plans first")
    return {
        "contract_digest": _digest(json.dumps(contracts, sort_keys=True).encode()),
        "task_inventory_digest": _digest(json.dumps(inventory, sort_keys=True).encode()),
    }, set(files)


def _scope_path(root, raw):
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or ".." in path.parts or "\\" in raw or str(path) != raw or raw == ".":
        raise ValueError("review scope requires exact repository-relative file paths without traversal")
    absolute = root / raw
    if not absolute.parent.resolve().is_relative_to(root):
        raise ValueError("review scope has an ancestor outside its repository")
    if absolute.is_dir():
        raise ValueError("review scope cannot be a directory: " + raw)
    return absolute


def _content_record(mode, content, normalize=False):
    if normalize and mode != "missing":
        content = _normalize_contract(content.decode("utf-8"))
    return {"mode": mode, "digest": _digest(content)}


def _working_file(path, normalize=False, expected_mode=None, track_filemode=True, symlinks=True):
    if path.is_symlink():
        return _content_record("120000", os.readlink(path).encode(), normalize)
    if not path.exists():
        return _content_record("missing", b"")
    if not path.is_file():
        raise ValueError("review scope is not a regular file: " + str(path))
    mode = "100755" if path.stat().st_mode & 0o111 else "100644"
    if not track_filemode and expected_mode in {"100644", "100755"}:
        mode = expected_mode
    if not symlinks and expected_mode == "120000":
        mode = "120000"  # Git's regular-file representation of a symlink.
    return _content_record(mode, path.read_bytes(), normalize)


def _committed_file(root, ref, path, normalize=False):
    tree = _git(root, "ls-tree", "-z", ref, "--", ":(literal)" + path)
    if not tree:
        return _content_record("missing", b"")
    metadata = tree.split(b"\t", 1)[0].decode().split()
    mode, kind, oid = metadata
    if kind != "blob":
        raise ValueError("review scope must name a file, not a tree/submodule: " + path)
    return _content_record(mode, _git(root, "cat-file", "blob", oid), normalize)


def capture(plan_path, repo_root, scope, base_ref, target_ref):
    if not scope or not base_ref or not target_ref:
        raise ValueError("review PASS requires --scope files, --base-ref, and --target-ref; legacy unbound PASS cannot close a plan")
    root = Path(repo_root).resolve(strict=True)
    actual_root = Path(_git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if actual_root != root:
        raise ValueError("--repo-root must be the exact source repository root")
    base = _git(root, "rev-parse", "--verify", "--end-of-options", base_ref + "^{commit}").decode().strip()
    target = _git(root, "rev-parse", "--verify", "--end-of-options", target_ref + "^{commit}").decode().strip()
    track_filemode = _git(root, "config", "--bool", "--default", "true", "core.filemode").strip() == b"true"
    symlinks = _git(root, "config", "--bool", "--default", "true", "core.symlinks").strip() == b"true"
    contract, plan_files = contract_evidence(plan_path)
    scoped = []
    for raw in sorted(set(scope)):
        absolute = _scope_path(root, raw)
        normalize = absolute.resolve() in plan_files
        reviewed = _committed_file(root, target, raw, normalize)
        if reviewed["mode"] == "missing" and _committed_file(root, base, raw)["mode"] == "missing":
            raise ValueError("review scope is absent at both refs: " + raw)
        current = _working_file(absolute, normalize, reviewed["mode"], track_filemode, symlinks)
        if current != reviewed:
            raise ValueError("review scope differs from --target-ref; commit/re-review first: " + raw)
        scoped.append({"path": raw, **reviewed})
    return {"version": 1, "repo_root": str(root), "base_ref": base,
            "target_ref": target, "scope": scoped, "track_filemode": track_filemode,
            "symlinks": symlinks, **contract}


def is_current(plan_path, evidence):
    if not isinstance(evidence, dict) or evidence.get("version") != 1 or not evidence.get("scope"):
        return False
    try:
        contract, plan_files = contract_evidence(plan_path)
        if any(evidence.get(key) != value for key, value in contract.items()):
            return False
        root = Path(evidence["repo_root"]).resolve(strict=True)
        for record in evidence["scope"]:
            path = _scope_path(root, record["path"])
            current = _working_file(path, path.resolve() in plan_files, record["mode"],
                                    evidence.get("track_filemode", True), evidence.get("symlinks", True))
            if current != {"mode": record["mode"], "digest": record["digest"]}:
                return False
        return True
    except (KeyError, TypeError, ValueError, OSError, UnicodeError):
        return False
