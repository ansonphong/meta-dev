#!/usr/bin/env python3
"""Pure-function tests for the GLM proxy retry predicate.

No pytest — run directly:  python3 tests/test_glm_proxy_retry.py
Imports the proxy module by path (the script has a hyphenated filename).
"""
import importlib.util
import pathlib
import sys

_PROXY = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "glm-beta-strip-proxy.py"
_spec = importlib.util.spec_from_file_location("glm_beta_strip_proxy", _PROXY)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

should_retry = mod.should_retry_upstream
N = len(mod.BACKOFF_SCHEDULE_SEC)

# 529 (Z.AI [1305] overload) IS retried, across the whole schedule.
assert should_retry(529, 0) is True, "first 529 must retry"
assert should_retry(529, N - 1) is True, "last allowed 529 must retry"

# ...but NOT past the schedule (final attempt surfaces the 529).
assert should_retry(529, N) is False, "must stop retrying after schedule exhausted"
assert should_retry(529, N + 5) is False, "must never retry past the cap"

# No other status is retried (429=[1302] deterministic; 200/400/503 pass through).
for status in (200, 400, 401, 404, 429, 500, 502, 503):
    assert should_retry(status, 0) is False, f"status {status} must not retry"
    assert should_retry(status, N - 1) is False, f"status {status} must not retry at any attempt"

print(f"OK — {N} retries max, backoff {mod.BACKOFF_SCHEDULE_SEC} "
      f"(~{sum(mod.BACKOFF_SCHEDULE_SEC)}s ceiling)")
