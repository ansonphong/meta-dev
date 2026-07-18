"""planctl — the unified state-layer CLI (single write door for plan/runbook state).

Python3 stdlib only. The package is invoked as ``python3 -m planctl <verb>``
(the bash shim ``scripts/planctl.sh`` resolves the scripts dir onto PYTHONPATH
and execs this). Verbs are wired in phases 0c–0e; 0a stands up only the
scaffold (package + shim + off-9p state dir + SQLite schema).
"""
