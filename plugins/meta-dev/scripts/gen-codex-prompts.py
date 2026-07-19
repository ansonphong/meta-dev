#!/usr/bin/env python3
"""Generate ~/.codex/prompts/*.md shims so meta-dev commands get real /name
autocomplete in Codex.

Each shim is a THIN REDIRECT into the command-router skill. It never copies
procedure — the command markdown stays the single source of truth.
"""
import argparse, os, pathlib, sys

# The commands worth a top-level slash entry. Deliberately NOT all 67 —
# a 67-item autocomplete list is noise, not discoverability.
CURATED = [
    "execute", "dev", "dashboard", "ship", "runbook", "sweep",
    "inbox", "auto-execute", "loop-gap", "probe", "security", "housekeeping",
]

TEMPLATE = """# /{name}

Run the meta-dev `{name}` command.

Use the `command-router` skill from the `meta-dev` plugin: read
`{catalog}/{name}.md` (falling back to `meta-{name}.md`) and follow that
procedure inline, translating Claude Code tools to your own shell.

Arguments, if any, follow this line.
"""


def plugin_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent


def resolve(catalog: pathlib.Path, name: str):
    for cand in (f"{name}.md", f"meta-{name}.md"):
        if (catalog / cand).is_file():
            return cand
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write the shims")
    ap.add_argument("--check", action="store_true", help="exit 1 if out of sync")
    ap.add_argument("--dest", default=os.path.expanduser("~/.codex/prompts"))
    args = ap.parse_args()

    catalog = plugin_root() / "commands"
    if not catalog.is_dir():
        print(f"ERROR: no command catalog at {catalog}", file=sys.stderr)
        return 2

    dest = pathlib.Path(args.dest)
    drift, missing_cmd = [], []

    for name in CURATED:
        if resolve(catalog, name) is None:
            missing_cmd.append(name)
            continue
        body = TEMPLATE.format(name=name, catalog=catalog)
        target = dest / f"{name}.md"
        current = target.read_text(encoding="utf-8") if target.is_file() else None
        if current != body:
            drift.append(name)
            if args.write:
                dest.mkdir(parents=True, exist_ok=True)
                target.write_text(body, encoding="utf-8")

    if missing_cmd:
        print(f"ERROR: curated names with no command file: {missing_cmd}", file=sys.stderr)
        return 2
    if args.check:
        print(f"out of sync: {drift}" if drift else f"in sync ({len(CURATED)} shims)")
        return 1 if drift else 0
    print(f"wrote/updated {len(drift)} shim(s) in {dest}" if args.write
          else f"would update {len(drift)} shim(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
