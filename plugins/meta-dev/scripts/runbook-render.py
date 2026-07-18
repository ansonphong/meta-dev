#!/usr/bin/env python3
"""Thin shim → planctl runbook render (M2b).  Delegates ALL render logic; kept for
backward compat with on-run-complete.sh, test-plugin.sh --check-runbook-gate, and
/meta-execute phase gates.  Content-compare skip is planctl's (R6).

CLI: runbook-render.py <runbook-file-path>
"""

import os, subprocess, sys

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <runbook-file-path>", file=sys.stderr)
        sys.exit(1)

    rb = sys.argv[1]
    if not os.path.isfile(rb):
        print(f"Warning: {rb} not found — skipping", file=sys.stderr)
        sys.exit(0)                        # W2B-4: never abort a batch

    planctl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "planctl.sh")
    res = subprocess.run(["bash", planctl, "runbook", "render", rb],
                         capture_output=True, text=True)

    if res.stdout: sys.stdout.write(res.stdout)
    if res.stderr: sys.stderr.write(res.stderr)

    if res.returncode != 0:
        if "not a runbook" in (res.stderr or ""):
            print(f"Warning: {rb} is not a runbook — skipping", file=sys.stderr)
            sys.exit(0)
        sys.exit(res.returncode)

if __name__ == "__main__":
    main()
