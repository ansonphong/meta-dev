# Auto-Execute Worker Routing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/auto-execute` project-configurable and capability-aware — route each chunk to the best *available* headless backend (DeepSeek / Grok / GLM / Codex / Sonnet…) based on per-project settings, auth/credits access, and what the chunk actually needs (slash harness vs direct write vs review).

**Architecture:** A deterministic resolver script (`worker-resolve.py`) is the single source of truth for routing. It merges the existing 3-layer settings cascade, probes which backends are authenticated on this machine, filters by chunk capability (`slash`, `write`, `review`), and walks the active profile’s role ladders. `/auto-execute` stops hardcoding DeepSeek→GLM and instead runs the resolver per chunk (and on escalation). Grok is a first-class execution + review backend, not a side command.

**Tech Stack:** Python 3 (resolver + tests), JSON Schema (settings), bash (`config-get` / existing headless scripts), markdown command doctrine (`auto-execute.md`).

**Repo (ONLY edit target):** `/mnt/d/Projects/360-HEXTILE/meta-dev`  
Windows path: `D:\Projects\360-HEXTILE\meta-dev`  
All relative paths in this plan are under that root (e.g. `plugins/meta-dev/commands/auto-execute.md`).

After ship: bump `plugins/meta-dev/.claude-plugin/plugin.json` patch version, push origin, then user reloads via `/plugin marketplace update` so the **install/cache** picks up changes. Never edit the cache in place.

## Global Constraints

- **⛔ EDIT THE SOURCE REPO ONLY — NEVER THE CACHED PLUGIN**
  - **DO edit:** `/mnt/d/Projects/360-HEXTILE/meta-dev/**` (`D:\Projects\360-HEXTILE\meta-dev\**`)
  - **DO NOT edit / DO NOT commit into:**
    - `~/.claude/plugins/marketplaces/meta-dev-marketplace/**`
    - `~/.claude/plugins/cache/**/meta-dev/**`
    - any other installed/mirrored copy of the plugin
  - Those trees are **read-only references** at most (to compare installed vs source). Claude Code loads the version-keyed cache; changes there are wiped on update and never become the git source of truth.
  - Every task step: `cd /mnt/d/Projects/360-HEXTILE/meta-dev` (or `cd "$(git rev-parse --show-toplevel)"` from inside that clone) **before** any Edit/Write/git.
  - `CLAUDE_PLUGIN_ROOT` during local smoke tests may point at  
    `/mnt/d/Projects/360-HEXTILE/meta-dev/plugins/meta-dev`  
    so scripts resolve from **source**, not the marketplace install.
- **Config cascade only** — defaults (`templates/settings.json`) → project (`plans/_dashboard/settings.json`) → local (`plans/_dashboard/settings.local.json`). No new config file formats.
- **Deterministic routing** — LLM conductor may *not* freestyle backend choice when a resolver answer exists. Override only via CLI force flags (`--deep|--glm|--grok|--sonnet|--codex|--opus|--fable`).
- **Two harness families** — `claude-code` backends can run project slash commands (`/meta-execute`, `/loop-gap`, …). `own` harnesses (grok, codex) get **direct tasks only**. Resolver enforces this via `needs_slash`.
- **Codex stays review-primary** — `write: false` by doctrine; never on farm/escalation ladders for code-writing.
- **Grok is not a bulk farm** — default `fanout: low`; conductor must not parallel-fan Grok the way it fans DeepSeek.
- **Availability = config ∩ probe** — disabled backends never win; missing auth/key never wins when `probe_auth: true` (default).
- **Critical-breakage tests only** for new code — unit tests for resolver pure logic + schema validation; no e2e headless API calls in CI.
- **Version bump on push** — every push that lands plugin changes increments `plugin.json` patch.

---

## File map

| Path | Responsibility |
|------|----------------|
| `plugins/meta-dev/schemas/settings.schema.json` | Validate `meta_dev.workers` block |
| `plugins/meta-dev/templates/settings.json` | Shipped defaults (DeepSeek farm, GLM escalate; Grok on review_lens) |
| `plugins/meta-dev/scripts/worker-resolve.py` | **Core:** merge config, probe auth, route chunk → backend dispatch plan |
| `plugins/meta-dev/tests/test_worker_resolve.py` | Unit tests for probe + route |
| `plugins/meta-dev/references/worker-routing.md` | Human doctrine: roles, capabilities, profiles, how to retune for credits |
| `plugins/meta-dev/references/config-cascade.md` | Document `workers` keys + layer guidance |
| `plugins/meta-dev/commands/auto-execute.md` | Conductor loop reads resolver; wire `--grok`; capability chunking |
| `plugins/meta-dev/commands/grok-execute.md` | Cross-link: Grok is on auto-execute ladder now |
| `plugins/meta-dev/.claude-plugin/plugin.json` | Patch version bump on ship |

**Out of scope for this plan (follow-ups):** wiring the same resolver into `/meta-execute` / agentic-exec-loop fix ladder; dashboard UI for profile picker; live credit-balance API polling (credits are human-tuned via profiles + disabled flags, not scraped from vendors).

---

## Design lock (implement exactly this)

### Backend registry (built into resolver defaults; overridable in settings)

```json
{
  "deep":   { "family": "claude-code", "write": true,  "slash": true,  "fanout": "high", "cost": "low",  "script": "claude-headless-exec", "dispatch": ["--backend", "deep"] },
  "glm":    { "family": "claude-code", "write": true,  "slash": true,  "fanout": "low",  "cost": "mid",  "script": "claude-headless-exec", "dispatch": ["--backend", "glm"], "concurrency_cap": 3 },
  "sonnet": { "family": "claude-code", "write": true,  "slash": true,  "fanout": "mid",  "cost": "high", "script": "claude-headless-exec", "dispatch": ["--backend", "sonnet"] },
  "opus":   { "family": "claude-code", "write": true,  "slash": true,  "fanout": "low",  "cost": "high", "script": "claude-headless-exec", "dispatch": ["--backend", "opus"] },
  "fable":  { "family": "claude-code", "write": true,  "slash": true,  "fanout": "low",  "cost": "high", "script": "claude-headless-exec", "dispatch": ["--backend", "fable"] },
  "grok":   { "family": "own",         "write": true,  "slash": false, "fanout": "low",  "cost": "high", "script": "grok-headless-exec",    "dispatch": [] },
  "codex":  { "family": "own",         "write": false, "slash": false, "fanout": "low",  "cost": "high", "script": "codex-headless-exec",   "dispatch": [], "roles_only": ["review_lens"] }
}
```

### Roles (profile ladders)

| Role | When conductor uses it |
|------|------------------------|
| `farm` | Default mechanical / bounded chunk |
| `stateful` | Long-horizon keep-it-whole, multi-file judgment |
| `escalation` | Previous backend failed review; walk next |
| `plan_write` | Plan markdown / meta-planner bulk prose |
| `review_lens` | Cross-family code/plan review (read-only) |

### Capability flags (chunk → filter)

| Flag | Meaning |
|------|---------|
| `needs_slash` | Worker must run `/meta-execute`, `/loop-gap`, etc. → only `slash: true` |
| `needs_write` | Will edit files → only `write: true` |
| `readonly` | Review/audit → prefer review_lens; allow write backends with `--readonly` |

### Routing algorithm

```
1. force flag? → that backend if enabled+available+capable, else error
2. pick ladder = profile[role]  (default role=farm)
3. if role == escalation AND failed_backend is on that ladder:
     start after that entry; else start at 0
     (failed_backend ignored for non-escalation roles)
4. for each candidate in ladder[start:]:
     skip if in profile.disabled or backend.enabled == false
     skip if probe_auth and not available
     skip if needs_slash and not backend.slash
     skip if needs_write and not backend.write
     skip if backend has roles_only and current role not in it
     → first match wins
5. no match → error with skipped[] reasons
```

**`resolve_route` probe default:** when `available is None` and `probe_auth` is true, call `probe_availability()` — never default to all-true (that would ignore missing keys).

### Shipped profiles

Farm ladders include a **capability-preserving fallback** after `deep` so a missing `DEEPSEEK_API_KEY` does not hard-kill every mechanical chunk. Prefer the cheapest remaining backend that can still do the work.

```json
{
  "profiles": {
    "default": {
      "farm":        ["deep", "glm"],
      "stateful":    ["glm", "grok"],
      "escalation":  ["glm", "grok"],
      "plan_write":  ["glm", "deep"],
      "review_lens": ["codex", "grok"],
      "disabled":    []
    },
    "grok-first": {
      "farm":        ["deep", "sonnet"],
      "stateful":    ["grok", "glm"],
      "escalation":  ["grok", "glm"],
      "plan_write":  ["grok", "glm", "deep"],
      "review_lens": ["grok", "codex"],
      "disabled":    []
    },
    "no-glm": {
      "farm":        ["deep", "sonnet"],
      "stateful":    ["grok", "sonnet"],
      "escalation":  ["grok", "sonnet"],
      "plan_write":  ["grok", "deep", "sonnet"],
      "review_lens": ["grok", "codex"],
      "disabled":    ["glm"]
    },
    "budget": {
      "farm":        ["deep", "glm"],
      "stateful":    ["deep", "glm"],
      "escalation":  ["glm", "deep"],
      "plan_write":  ["deep", "glm"],
      "review_lens": ["codex"],
      "disabled":    ["grok", "sonnet", "opus", "fable"]
    }
  }
}
```

### Auth probes (no network, filesystem/env only)

| Backend | Available when |
|---------|----------------|
| `deep` | `os.environ.get("DEEPSEEK_API_KEY")` non-empty |
| `glm` | `os.environ.get("GLM_API_KEY")` non-empty |
| `sonnet` / `opus` / `fable` | always `true` if `shutil.which("claude")` else `false` (ambient login assumed when CLI present) |
| `grok` | `which("grok")` and `Path.home() / ".grok/auth.json"` exists |
| `codex` | `which("codex")` and (`Path.home() / ".codex/auth.json"` exists OR `OPENAI_API_KEY` non-empty) |

Credits are **not** auto-read from vendors. When a user is out of GLM credits they set:

```bash
# project (team) — third arg is layer: project|local
bash ${CLAUDE_PLUGIN_ROOT}/scripts/config-set.sh meta_dev.workers.active_profile no-glm project
# this machine only (personal credits)
bash ${CLAUDE_PLUGIN_ROOT}/scripts/config-set.sh meta_dev.workers.active_profile no-glm local
# one-shot for a single route call (does not write settings)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/worker-resolve.py route --profile no-glm --role farm --needs-write
```

### CLI of `worker-resolve.py`

```
worker-resolve.py show
worker-resolve.py probe
worker-resolve.py route --role farm|stateful|escalation|plan_write|review_lens
                         [--needs-slash] [--needs-write] [--readonly]
                         [--failed-backend NAME]
                         [--force NAME]
                         [--profile NAME]      # one-shot override of active_profile (no file write)
                         [--project-root DIR]   # default: cwd
                         [--plugin-root DIR]    # default: CLAUDE_PLUGIN_ROOT
```

**Stdout always one JSON object** (no chatter). Exit 0 on success; exit 2 on no eligible backend; exit 1 on usage/config error.

**`route` success shape:**

```json
{
  "backend": "grok",
  "family": "own",
  "script": "grok-headless-exec",
  "dispatch": [],
  "readonly_flag": "--readonly",
  "role": "stateful",
  "profile": "grok-first",
  "reason": "first eligible on stateful ladder",
  "ladder": ["grok", "glm"],
  "skipped": [{"backend": "glm", "reason": "disabled"}],
  "available": {"deep": true, "glm": false, "grok": true, "codex": true, "sonnet": true},
  "fanout": "low",
  "slash": false,
  "write": true
}
```

Conductor builds the bash line (use a bash array for `dispatch` — it may be empty for grok/codex):

```bash
# After jq/python parse of route JSON into SCRIPT, DISPATCH_JSON, RO_FLAG:
mapfile -t DISPATCH_ARR < <(python3 -c "import json,sys; print('\n'.join(json.loads(sys.argv[1])))" "$DISPATCH_JSON")
cmd=( "${CLAUDE_PLUGIN_ROOT}/scripts/${SCRIPT}" )
# shellcheck: empty array is fine
((${#DISPATCH_ARR[@]})) && cmd+=( "${DISPATCH_ARR[@]}" )
[[ -n "$RO_FLAG" ]] && cmd+=( "$RO_FLAG" )
# optional shared flags when the script supports them:
# [[ -n "$EFFORT" ]] && cmd+=( --effort "$EFFORT" )
# [[ -n "$REPO" ]] && cmd+=( --repo "$REPO" )
cmd+=( -- "<self-contained chunk spec>" )
"${cmd[@]}"
```

If `slash: false`, chunk spec must be a **direct task**, never `run /meta-execute …`.

**`plan_write` + harness commands:** if the chunk is `run /meta-planner …` (or any slash command), always pass `--needs-slash` — Grok will be skipped and a Claude-family backend wins.

---

### Task 1: Schema + template defaults for `meta_dev.workers`

**Files:**
- Modify: `plugins/meta-dev/schemas/settings.schema.json` (add `workers` under `meta_dev.properties`)
- Modify: `plugins/meta-dev/templates/settings.json` (add `workers` block after `execute`)

**Interfaces:**
- Produces: schema-valid `meta_dev.workers` with `active_profile`, `probe_auth`, `backends` (optional overrides), `profiles`

- [ ] **Step 1: Add `workers` to the schema**

Inside `meta_dev.properties`, after the existing `"execute"` property block, add:

```json
"workers": {
  "type": "object",
  "description": "Headless worker routing for /auto-execute (and future loop consumers).",
  "properties": {
    "active_profile": {
      "type": "string",
      "default": "default",
      "description": "Name of profiles.* entry to use"
    },
    "probe_auth": {
      "type": "boolean",
      "default": true,
      "description": "If true, skip backends whose local auth/key probe fails"
    },
    "backends": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "enabled": { "type": "boolean" },
          "family": { "type": "string", "enum": ["claude-code", "own"] },
          "write": { "type": "boolean" },
          "slash": { "type": "boolean" },
          "fanout": { "type": "string", "enum": ["high", "mid", "low"] },
          "cost": { "type": "string", "enum": ["low", "mid", "high"] },
          "script": { "type": "string" },
          "dispatch": {
            "type": "array",
            "items": { "type": "string" }
          },
          "concurrency_cap": { "type": "integer", "minimum": 1 },
          "roles_only": {
            "type": "array",
            "items": { "type": "string" }
          }
        },
        "additionalProperties": false
      }
    },
    "profiles": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "farm": { "type": "array", "items": { "type": "string" } },
          "stateful": { "type": "array", "items": { "type": "string" } },
          "escalation": { "type": "array", "items": { "type": "string" } },
          "plan_write": { "type": "array", "items": { "type": "string" } },
          "review_lens": { "type": "array", "items": { "type": "string" } },
          "disabled": { "type": "array", "items": { "type": "string" } }
        },
        "additionalProperties": false
      }
    }
  },
  "additionalProperties": false
}
```

- [ ] **Step 2: Add defaults to `templates/settings.json`**

Under `meta_dev`, add (after `"execute": { ... }`):

```json
"workers": {
  "active_profile": "default",
  "probe_auth": true,
  "backends": {},
  "profiles": {
    "default": {
      "farm": ["deep", "glm"],
      "stateful": ["glm", "grok"],
      "escalation": ["glm", "grok"],
      "plan_write": ["glm", "deep"],
      "review_lens": ["codex", "grok"],
      "disabled": []
    },
    "grok-first": {
      "farm": ["deep", "sonnet"],
      "stateful": ["grok", "glm"],
      "escalation": ["grok", "glm"],
      "plan_write": ["grok", "glm", "deep"],
      "review_lens": ["grok", "codex"],
      "disabled": []
    },
    "no-glm": {
      "farm": ["deep", "sonnet"],
      "stateful": ["grok", "sonnet"],
      "escalation": ["grok", "sonnet"],
      "plan_write": ["grok", "deep", "sonnet"],
      "review_lens": ["grok", "codex"],
      "disabled": ["glm"]
    },
    "budget": {
      "farm": ["deep", "glm"],
      "stateful": ["deep", "glm"],
      "escalation": ["glm", "deep"],
      "plan_write": ["deep", "glm"],
      "review_lens": ["codex"],
      "disabled": ["grok", "sonnet", "opus", "fable"]
    }
  }
}
```

- [ ] **Step 3: Validate template against schema**

```bash
cd /mnt/d/Projects/360-HEXTILE/meta-dev
export CLAUDE_PLUGIN_ROOT="$(pwd)/plugins/meta-dev"
python3 -c "
import json, jsonschema
s=json.load(open('plugins/meta-dev/schemas/settings.schema.json'))
t=json.load(open('plugins/meta-dev/templates/settings.json'))
jsonschema.validate(t, s)
print('OK')
"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd /mnt/d/Projects/360-HEXTILE/meta-dev
git add plugins/meta-dev/schemas/settings.schema.json plugins/meta-dev/templates/settings.json
git commit -m "$(cat <<'EOF'
feat(workers): schema + default profiles for headless routing

Add meta_dev.workers (active_profile, probe_auth, profiles) so projects
can tune /auto-execute ladders without forking command docs.
EOF
)"
```

---

### Task 2: `worker-resolve.py` — registry, merge, probe, route

**Files:**
- Create: `plugins/meta-dev/scripts/worker-resolve.py`
- Test: `plugins/meta-dev/tests/test_worker_resolve.py`

**Interfaces:**
- Consumes: cascade files via same paths as `config-merge.py`; env + home for probes
- Produces: CLI `show|probe|route` → JSON on stdout; exit codes 0/1/2 as designed above
- Key functions (importable by tests):
  - `BUILTIN_BACKENDS: dict`
  - `BUILTIN_PROFILES: dict`
  - `deep_merge(base, override) -> dict`
  - `load_merged_settings(project_root, plugin_root) -> dict`
  - `probe_availability(env=None, home=None, which=None) -> dict[str, bool]`
  - `resolve_route(*, settings, role, needs_slash=False, needs_write=False, readonly=False, failed_backend=None, force=None, available=None, profile_override=None) -> dict`

- [ ] **Step 1: Write failing unit tests**

Create `plugins/meta-dev/tests/test_worker_resolve.py`:

```python
#!/usr/bin/env python3
"""Unit tests for worker-resolve routing (no live API calls)."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "worker-resolve.py"


def _load():
    spec = importlib.util.spec_from_file_location("worker_resolve", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def wr():
    if not SCRIPT.is_file():
        pytest.skip("worker-resolve.py not written yet")
    return _load()


def _settings(profile="default", disabled=None, probe_auth=True, backend_overrides=None):
    wr = _load()
    profiles = {k: dict(v) for k, v in wr.BUILTIN_PROFILES.items()}
    if disabled is not None:
        profiles[profile] = dict(profiles[profile], disabled=list(disabled))
    return {
        "meta_dev": {
            "workers": {
                "active_profile": profile,
                "probe_auth": probe_auth,
                "backends": backend_overrides or {},
                "profiles": profiles,
            }
        }
    }


def test_farm_defaults_to_deep(wr):
    avail = {b: True for b in wr.BUILTIN_BACKENDS}
    r = wr.resolve_route(settings=_settings(), role="farm", needs_write=True, available=avail)
    assert r["backend"] == "deep"
    assert r["script"] == "claude-headless-exec"
    assert r["dispatch"] == ["--backend", "deep"]


def test_needs_slash_skips_grok_on_stateful_grok_first(wr):
    avail = {b: True for b in wr.BUILTIN_BACKENDS}
    r = wr.resolve_route(
        settings=_settings("grok-first"),
        role="stateful",
        needs_slash=True,
        needs_write=True,
        available=avail,
    )
    # grok has slash=false → skip → glm
    assert r["backend"] == "glm"
    assert any(s["backend"] == "grok" for s in r["skipped"])


def test_escalation_after_deep_failure_uses_next(wr):
    avail = {b: True for b in wr.BUILTIN_BACKENDS}
    r = wr.resolve_route(
        settings=_settings("grok-first"),
        role="escalation",
        needs_write=True,
        failed_backend="deep",  # not on escalation ladder; still start from full ladder
        available=avail,
    )
    assert r["backend"] == "grok"


def test_escalation_skips_failed_backend_when_on_ladder(wr):
    avail = {b: True for b in wr.BUILTIN_BACKENDS}
    r = wr.resolve_route(
        settings=_settings("grok-first"),
        role="escalation",
        needs_write=True,
        failed_backend="grok",
        available=avail,
    )
    assert r["backend"] == "glm"


def test_disabled_glm_profile(wr):
    avail = {b: True for b in wr.BUILTIN_BACKENDS}
    r = wr.resolve_route(
        settings=_settings("no-glm"),
        role="stateful",
        needs_write=True,
        available=avail,
    )
    assert r["backend"] == "grok"
    assert any(s["backend"] == "glm" for s in r["skipped"]) or "glm" in (
        wr.BUILTIN_PROFILES["no-glm"]["disabled"]
    )


def test_probe_auth_filters_missing_key(wr):
    """When farm's primary is unavailable, fall through or raise if ladder exhausted."""
    avail = {b: True for b in wr.BUILTIN_BACKENDS}
    avail["deep"] = False
    # default farm is ["deep", "glm"] → glm wins when deep auth fails
    r = wr.resolve_route(
        settings=_settings("default"),
        role="farm",
        needs_write=True,
        available=avail,
    )
    assert r["backend"] == "glm"
    assert any(s["backend"] == "deep" for s in r["skipped"])


def test_probe_auth_exhausted_raises(wr):
    avail = {b: False for b in wr.BUILTIN_BACKENDS}
    with pytest.raises(wr.NoBackendError) as ei:
        wr.resolve_route(
            settings=_settings("default"),
            role="farm",
            needs_write=True,
            available=avail,
        )
    assert ei.value.payload["skipped"]


def test_force_grok_review_readonly(wr):
    avail = {b: True for b in wr.BUILTIN_BACKENDS}
    r = wr.resolve_route(
        settings=_settings(),
        role="review_lens",
        force="grok",
        readonly=True,
        available=avail,
    )
    assert r["backend"] == "grok"
    assert r["readonly_flag"] == "--readonly"
    assert r["slash"] is False


def test_codex_not_eligible_for_farm_write(wr):
    avail = {b: True for b in wr.BUILTIN_BACKENDS}
    with pytest.raises(wr.NoBackendError):
        wr.resolve_route(
            settings=_settings(disabled=["deep", "glm", "grok", "sonnet", "opus", "fable"]),
            role="farm",
            needs_write=True,
            force="codex",
            available=avail,
        )


def test_probe_deep_key(wr, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.delenv("GLM_API_KEY", raising=False)
    avail = wr.probe_availability(
        env=os.environ,
        home=Path("/tmp/no-such-home-worker-resolve"),
        which=lambda n: "/usr/bin/claude" if n == "claude" else None,
    )
    assert avail["deep"] is True
    assert avail["glm"] is False
    assert avail["grok"] is False
```

**Contract:** `resolve_route` **raises** `NoBackendError` (subclass of Exception) with a `.payload` dict containing `skipped` when nothing matches. Do not return an error dict.

- [ ] **Step 2: Run tests — expect fail / skip**

```bash
cd /mnt/d/Projects/360-HEXTILE/meta-dev
python3 -m pytest plugins/meta-dev/tests/test_worker_resolve.py -q
```

Expected: FAIL (import/file missing) or skip, not silent pass.

- [ ] **Step 3: Implement `worker-resolve.py`**

Create `plugins/meta-dev/scripts/worker-resolve.py` with this full implementation:

```python
#!/usr/bin/env python3
"""Resolve which headless backend /auto-execute should use for a chunk.

Deterministic. No network. Config cascade: plugin defaults → project → local.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

BUILTIN_BACKENDS: dict[str, dict[str, Any]] = {
    "deep": {
        "family": "claude-code",
        "write": True,
        "slash": True,
        "fanout": "high",
        "cost": "low",
        "script": "claude-headless-exec",
        "dispatch": ["--backend", "deep"],
    },
    "glm": {
        "family": "claude-code",
        "write": True,
        "slash": True,
        "fanout": "low",
        "cost": "mid",
        "script": "claude-headless-exec",
        "dispatch": ["--backend", "glm"],
        "concurrency_cap": 3,
    },
    "sonnet": {
        "family": "claude-code",
        "write": True,
        "slash": True,
        "fanout": "mid",
        "cost": "high",
        "script": "claude-headless-exec",
        "dispatch": ["--backend", "sonnet"],
    },
    "opus": {
        "family": "claude-code",
        "write": True,
        "slash": True,
        "fanout": "low",
        "cost": "high",
        "script": "claude-headless-exec",
        "dispatch": ["--backend", "opus"],
    },
    "fable": {
        "family": "claude-code",
        "write": True,
        "slash": True,
        "fanout": "low",
        "cost": "high",
        "script": "claude-headless-exec",
        "dispatch": ["--backend", "fable"],
    },
    "grok": {
        "family": "own",
        "write": True,
        "slash": False,
        "fanout": "low",
        "cost": "high",
        "script": "grok-headless-exec",
        "dispatch": [],
    },
    "codex": {
        "family": "own",
        "write": False,
        "slash": False,
        "fanout": "low",
        "cost": "high",
        "script": "codex-headless-exec",
        "dispatch": [],
        "roles_only": ["review_lens"],
    },
}

BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "default": {
        "farm": ["deep", "glm"],
        "stateful": ["glm", "grok"],
        "escalation": ["glm", "grok"],
        "plan_write": ["glm", "deep"],
        "review_lens": ["codex", "grok"],
        "disabled": [],
    },
    "grok-first": {
        "farm": ["deep", "sonnet"],
        "stateful": ["grok", "glm"],
        "escalation": ["grok", "glm"],
        "plan_write": ["grok", "glm", "deep"],
        "review_lens": ["grok", "codex"],
        "disabled": [],
    },
    "no-glm": {
        "farm": ["deep", "sonnet"],
        "stateful": ["grok", "sonnet"],
        "escalation": ["grok", "sonnet"],
        "plan_write": ["grok", "deep", "sonnet"],
        "review_lens": ["grok", "codex"],
        "disabled": ["glm"],
    },
    "budget": {
        "farm": ["deep", "glm"],
        "stateful": ["deep", "glm"],
        "escalation": ["glm", "deep"],
        "plan_write": ["deep", "glm"],
        "review_lens": ["codex"],
        "disabled": ["grok", "sonnet", "opus", "fable"],
    },
}

ROLES = ("farm", "stateful", "escalation", "plan_write", "review_lens")


class NoBackendError(Exception):
    def __init__(self, payload: dict[str, Any]):
        super().__init__(payload.get("error", "no backend"))
        self.payload = payload


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_merged_settings(project_root: str | Path, plugin_root: str | Path) -> dict:
    project_root = Path(project_root)
    plugin_root = Path(plugin_root)
    layers = [
        plugin_root / "templates" / "settings.json",
        project_root / "plans" / "_dashboard" / "settings.json",
        project_root / "plans" / "_dashboard" / "settings.local.json",
    ]
    # Seed with builtin workers so projects without template update still work
    merged: dict = {
        "meta_dev": {
            "workers": {
                "active_profile": "default",
                "probe_auth": True,
                "backends": {},
                "profiles": BUILTIN_PROFILES,
            }
        }
    }
    for path in layers:
        if path.is_file():
            with open(path, encoding="utf-8") as f:
                layer = json.load(f)
            merged = deep_merge(merged, layer)
    # Ensure builtin profiles exist unless fully replaced
    workers = merged.setdefault("meta_dev", {}).setdefault("workers", {})
    profiles = workers.setdefault("profiles", {})
    for name, prof in BUILTIN_PROFILES.items():
        if name not in profiles:
            profiles[name] = prof
    return merged


def probe_availability(
    env: dict | None = None,
    home: Path | None = None,
    which: Callable[[str], str | None] | None = None,
) -> dict[str, bool]:
    env = env if env is not None else os.environ
    home = Path(home) if home is not None else Path.home()
    which = which or shutil.which

    claude_ok = which("claude") is not None
    grok_ok = which("grok") is not None and (home / ".grok" / "auth.json").is_file()
    codex_ok = which("codex") is not None and (
        (home / ".codex" / "auth.json").is_file()
        or bool(env.get("OPENAI_API_KEY"))
    )
    return {
        "deep": bool(env.get("DEEPSEEK_API_KEY")),
        "glm": bool(env.get("GLM_API_KEY")),
        "sonnet": claude_ok,
        "opus": claude_ok,
        "fable": claude_ok,
        "grok": grok_ok,
        "codex": codex_ok,
    }


def _merged_backends(settings: dict) -> dict[str, dict[str, Any]]:
    out = {k: dict(v) for k, v in BUILTIN_BACKENDS.items()}
    overrides = (
        settings.get("meta_dev", {}).get("workers", {}).get("backends") or {}
    )
    for name, ov in overrides.items():
        if name in out:
            out[name] = deep_merge(out[name], ov)
        else:
            out[name] = dict(ov)
    return out


def _active_profile(settings: dict) -> tuple[str, dict[str, Any]]:
    workers = settings.get("meta_dev", {}).get("workers", {})
    name = workers.get("active_profile") or "default"
    profiles = workers.get("profiles") or BUILTIN_PROFILES
    if name not in profiles:
        raise ValueError(f"unknown workers.active_profile: {name!r}")
    return name, profiles[name]


def resolve_route(
    *,
    settings: dict,
    role: str,
    needs_slash: bool = False,
    needs_write: bool = False,
    readonly: bool = False,
    failed_backend: str | None = None,
    force: str | None = None,
    available: dict[str, bool] | None = None,
    profile_override: str | None = None,
) -> dict[str, Any]:
    if role not in ROLES:
        raise ValueError(f"invalid role {role!r}; expected one of {ROLES}")

    workers = settings.get("meta_dev", {}).get("workers", {})
    if profile_override:
        workers = dict(workers)
        workers["active_profile"] = profile_override
        settings = deep_merge(settings, {"meta_dev": {"workers": workers}})
    probe_auth = workers.get("probe_auth", True)
    profile_name, profile = _active_profile(settings)
    backends = _merged_backends(settings)
    disabled = set(profile.get("disabled") or [])
    if available is not None:
        avail = available
    elif probe_auth:
        avail = probe_availability()
    else:
        avail = {b: True for b in backends}

    def is_enabled(name: str) -> bool:
        if name in disabled:
            return False
        b = backends.get(name) or {}
        if b.get("enabled") is False:
            return False
        return True

    def eligible(name: str, for_role: str) -> tuple[bool, str]:
        if name not in backends:
            return False, "unknown backend"
        if not is_enabled(name):
            return False, "disabled"
        if probe_auth and not avail.get(name, False):
            return False, "auth probe failed"
        b = backends[name]
        roles_only = b.get("roles_only")
        if roles_only is not None and for_role not in roles_only:
            return False, f"roles_only={roles_only}"
        if needs_slash and not b.get("slash", False):
            return False, "needs_slash but backend.slash=false"
        if needs_write and not b.get("write", False):
            return False, "needs_write but backend.write=false"
        return True, "ok"

    skipped: list[dict[str, str]] = []

    if force:
        ok, reason = eligible(force, role)
        if not ok:
            raise NoBackendError(
                {
                    "error": f"forced backend {force!r} not eligible",
                    "reason": reason,
                    "skipped": [{"backend": force, "reason": reason}],
                    "profile": profile_name,
                    "role": role,
                }
            )
        b = backends[force]
        return _result(
            force, b, role, profile_name, [force], skipped, avail, readonly, "forced"
        )

    ladder = list(profile.get(role) or [])
    if not ladder:
        raise NoBackendError(
            {
                "error": f"profile {profile_name!r} has empty ladder for role {role!r}",
                "skipped": [],
                "profile": profile_name,
                "role": role,
            }
        )

    # Escalation: if failed_backend is on the ladder, start after it
    start = 0
    if failed_backend and role == "escalation" and failed_backend in ladder:
        start = ladder.index(failed_backend) + 1

    for name in ladder[start:]:
        ok, reason = eligible(name, role)
        if not ok:
            skipped.append({"backend": name, "reason": reason})
            continue
        b = backends[name]
        return _result(
            name,
            b,
            role,
            profile_name,
            ladder,
            skipped,
            avail,
            readonly,
            "first eligible on ladder",
        )

    raise NoBackendError(
        {
            "error": "no eligible backend",
            "skipped": skipped,
            "ladder": ladder,
            "profile": profile_name,
            "role": role,
            "available": avail,
        }
    )


def _result(
    name: str,
    b: dict[str, Any],
    role: str,
    profile_name: str,
    ladder: list[str],
    skipped: list[dict[str, str]],
    avail: dict[str, bool],
    readonly: bool,
    reason: str,
) -> dict[str, Any]:
    return {
        "backend": name,
        "family": b.get("family"),
        "script": b.get("script"),
        "dispatch": list(b.get("dispatch") or []),
        "readonly_flag": "--readonly" if readonly or role == "review_lens" else "",
        "role": role,
        "profile": profile_name,
        "reason": reason,
        "ladder": ladder,
        "skipped": skipped,
        "available": avail,
        "fanout": b.get("fanout"),
        "slash": bool(b.get("slash")),
        "write": bool(b.get("write")),
        "cost": b.get("cost"),
        "concurrency_cap": b.get("concurrency_cap"),
    }


def cmd_show(settings: dict, available: dict[str, bool]) -> dict:
    name, profile = _active_profile(settings)
    workers = settings.get("meta_dev", {}).get("workers", {})
    return {
        "active_profile": name,
        "probe_auth": workers.get("probe_auth", True),
        "profile": profile,
        "available": available,
        "backends": sorted(_merged_backends(settings).keys()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="worker-resolve")
    parser.add_argument(
        "command", choices=["show", "probe", "route"], help="subcommand"
    )
    parser.add_argument("--role", choices=ROLES, default="farm")
    parser.add_argument("--needs-slash", action="store_true")
    parser.add_argument("--needs-write", action="store_true")
    parser.add_argument("--readonly", action="store_true")
    parser.add_argument("--failed-backend", default=None)
    parser.add_argument("--force", default=None)
    parser.add_argument(
        "--profile",
        default=None,
        help="One-shot override of meta_dev.workers.active_profile (no file write)",
    )
    parser.add_argument("--project-root", default=os.getcwd())
    parser.add_argument(
        "--plugin-root",
        default=os.environ.get("CLAUDE_PLUGIN_ROOT", "."),
    )
    args = parser.parse_args(argv)

    try:
        settings = load_merged_settings(args.project_root, args.plugin_root)
        if args.profile:
            settings = deep_merge(
                settings,
                {"meta_dev": {"workers": {"active_profile": args.profile}}},
            )
        available = probe_availability()
        if args.command == "probe":
            json.dump(available, sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 0
        if args.command == "show":
            json.dump(cmd_show(settings, available), sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 0
        # route
        probe_auth = (
            settings.get("meta_dev", {}).get("workers", {}).get("probe_auth", True)
        )
        result = resolve_route(
            settings=settings,
            role=args.role,
            needs_slash=args.needs_slash,
            needs_write=args.needs_write,
            readonly=args.readonly,
            failed_backend=args.failed_backend,
            force=args.force,
            available=available if probe_auth else {b: True for b in BUILTIN_BACKENDS},
            profile_override=None,  # already applied into settings above
        )
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    except NoBackendError as e:
        json.dump(e.payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 2
    except Exception as e:
        json.dump({"error": str(e)}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

Make executable:

```bash
chmod +x plugins/meta-dev/scripts/worker-resolve.py
```

- [ ] **Step 4: Run unit tests — expect pass**

```bash
cd /mnt/d/Projects/360-HEXTILE/meta-dev
python3 -m pytest plugins/meta-dev/tests/test_worker_resolve.py -q
```

Expected: all PASS.

- [ ] **Step 5: Smoke CLI**

```bash
export CLAUDE_PLUGIN_ROOT=/mnt/d/Projects/360-HEXTILE/meta-dev/plugins/meta-dev
cd /mnt/d/Projects/360-Hextile   # any project with or without workers key
python3 "$CLAUDE_PLUGIN_ROOT/scripts/worker-resolve.py" show
python3 "$CLAUDE_PLUGIN_ROOT/scripts/worker-resolve.py" probe
python3 "$CLAUDE_PLUGIN_ROOT/scripts/worker-resolve.py" route --role farm --needs-write
python3 "$CLAUDE_PLUGIN_ROOT/scripts/worker-resolve.py" route --role stateful --needs-slash --needs-write
```

Expected: JSON objects; `farm` → `deep` if key present; `stateful --needs-slash` never returns `grok`.

- [ ] **Step 6: Commit**

```bash
cd /mnt/d/Projects/360-HEXTILE/meta-dev
git add plugins/meta-dev/scripts/worker-resolve.py plugins/meta-dev/tests/test_worker_resolve.py
git commit -m "$(cat <<'EOF'
feat(workers): add worker-resolve for capability-aware routing

Deterministic show/probe/route over the settings cascade. Filters by
auth probes, slash/write needs, and per-profile ladders (incl. grok-first).
EOF
)"
```

---

### Task 3: Doctrine — `auto-execute.md` uses the resolver

**Files:**
- Modify: `plugins/meta-dev/commands/auto-execute.md` (full Core Bias + routing + dispatch sections)
- Modify: `plugins/meta-dev/commands/grok-execute.md` (one-paragraph cross-link only)

**Interfaces:**
- Consumes: `worker-resolve.py route|show` JSON
- Produces: conductor behavior that is profile-driven, not DeepSeek→GLM hardcoded

- [ ] **Step 1: Rewrite frontmatter description + argument-hint**

Replace the YAML frontmatter with:

```yaml
---
name: auto-execute
argument-hint: <any task, prompt, plan, or meta-dev op> [--deep|--glm|--grok|--sonnet|--codex|--opus|--fable] [--effort <level>] [--repo <name>] [--readonly] [--max-turns <n>] [--profile <name>]  # --repo names from .claude/meta-dev-repos.json
description: Opus-conducted headless work router for ANY task. Decomposes work into chunks, routes each via worker-resolve (per-project profile + auth probes + capability filters) across DeepSeek/Grok/GLM/Sonnet/Codex, reviews every round-trip, escalates along the profile ladder.
---
```

- [ ] **Step 2: Replace “Core Bias” section with resolver doctrine**

Delete the hard-coded DeepSeek→GLM-only bias block. Insert this section (keep multi-phase / dashboard / gating sections; only rewrite routing-related prose):

```markdown
## Worker routing — project profile + capability (source of truth)

**Do not freestyle backend choice.** Before the run, and again for every chunk (and every escalation), call the resolver:

```bash
# Once at Step 2 — print active profile + what's authenticated on this machine
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/worker-resolve.py show

# Per chunk — pick role + capability flags, get a dispatch plan
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/worker-resolve.py route \
  --role <farm|stateful|escalation|plan_write|review_lens> \
  ${NEEDS_SLASH:+--needs-slash} \
  ${NEEDS_WRITE:+--needs-write} \
  ${READONLY:+--readonly} \
  ${FAILED:+--failed-backend "$FAILED"} \
  ${FORCE:+--force "$FORCE"}
```

Exit `0` → use `backend` / `script` / `dispatch` / `readonly_flag` from the JSON.  
Exit `2` → no eligible backend; surface `skipped` + `available` to the user (usually: missing API key, or profile disabled everything capable). Do **not** invent a fallback.

### Roles (how to classify a chunk)

| Role | Use when |
|------|----------|
| `farm` | Bounded / mechanical / self-contained (default) |
| `stateful` | Multi-file judgment, long-horizon keep-it-whole, fat-phase core |
| `plan_write` | Plan markdown / design-doc bulk prose |
| `review_lens` | Cross-family review / audit (always pass `--readonly`) |
| `escalation` | Prior attempt FAILED review — pass `--failed-backend <name>` |

### Capability flags (mandatory honesty)

| Flag | Set when |
|------|----------|
| `--needs-slash` | Chunk tells the worker to run a project slash command (`/meta-execute`, `/loop-gap`, `/meta-planner`, …). **Grok and Codex can never win these.** |
| `--needs-write` | Chunk will edit files |
| `--readonly` | Audits / reviews (also auto-applied for `review_lens`) |

### Spec shape by family

- `family: claude-code` (`slash: true`) → may include *run `/command` …* in the chunk spec.
- `family: own` (`slash: false`) → **direct task only** ("Fix X in file Y", "Review this diff for Z"). Never "run `/meta-execute`".

### Fan-out

Obey `fanout` from the route result: `high` (DeepSeek) may parallelize; `low` (Grok, GLM, Codex) → **serialize** — especially GLM (`concurrency_cap: 3` account-wide) and Grok (cost).

### Force flags (CLI)

`--deep` / `--glm` / `--grok` / `--sonnet` / `--codex` / `--opus` / `--fable` → pass `--force <name>` to the resolver (still capability-checked).  
`--profile <name>` → pass through to `worker-resolve.py --profile <name>` (one-shot override of `active_profile` for that call; **does not write settings**). For durable team/local defaults use `config-set.sh … project|local`.

### Per-project credits / access

Routing adapts automatically:

1. **Profile** — `default` | `grok-first` | `no-glm` | `budget` | custom in project settings.
2. **Auth probe** — missing `DEEPSEEK_API_KEY` / `GLM_API_KEY` / `~/.grok/auth.json` / codex login → backend skipped when `probe_auth: true`.
3. **Manual disable** — out of GLM credits?  
   `plans/_dashboard/settings.local.json`:
   ```json
   { "meta_dev": { "workers": { "active_profile": "no-glm" } } }
   ```
   or append `"glm"` to the active profile's `disabled` list.

Full doctrine: `references/worker-routing.md`.
```

- [ ] **Step 3: Update Conductor Loop steps 2–5**

In the conductor loop:

- Step 2 **Route** — replace “Default DeepSeek; mark any chunk that needs GLM” with: classify role + flags → `worker-resolve.py route` → record `backend` + `reason` on the task tracker.
- Step 3 **Dispatch** — use `script` + `dispatch` + `readonly_flag` from the route JSON (not hardcoded `claude-headless-exec --backend deep|glm`). Include Grok path: `scripts/grok-headless-exec`.
- Step 5 **FAIL** — re-route with `--role escalation --failed-backend <previous>` (not hard-coded deep→glm). Max 2 escalation attempts, then surface.

- [ ] **Step 4: Update multi-phase routing paragraph**

Replace “usually leans GLM” with:

```markdown
**Routing per phase:** classify the phase:
- Tasks are small/disjoint → `--role farm` (often deep).
- Cohesive multi-task / stateful → `--role stateful`.
- Worker must run `/meta-execute` → **always** `--needs-slash` (Grok cannot win).
Escalate failed phases with `--role escalation --failed-backend … --needs-slash`.
```

- [ ] **Step 5: Update Step 3 bash dispatch example**

```bash
# Parse route JSON once (SCRIPT, DISPATCH as JSON array string, RO_FLAG, FAMILY, SLASH)
mapfile -t DISPATCH_ARR < <(python3 -c "import json,sys; print('\n'.join(json.loads(sys.argv[1]) or []))" "$DISPATCH_JSON")
cmd=( "${CLAUDE_PLUGIN_ROOT}/scripts/${SCRIPT}" )
((${#DISPATCH_ARR[@]})) && cmd+=( "${DISPATCH_ARR[@]}" )
[[ -n "$RO_FLAG" ]] && cmd+=( "$RO_FLAG" )
# Only forward flags the chosen script supports (claude-headless-exec: effort/repo/max-turns;
# grok-headless-exec: repo/max-turns/readonly; codex-headless-exec: repo/readonly — no max-turns).
if [[ "$SCRIPT" == "claude-headless-exec" ]]; then
  [[ -n "${EFFORT:-}" ]] && cmd+=( --effort "$EFFORT" )
  [[ -n "${REPO:-}" ]] && cmd+=( --repo "$REPO" )
  [[ -n "${MAX_TURNS:-}" ]] && cmd+=( --max-turns "$MAX_TURNS" )
elif [[ "$SCRIPT" == "grok-headless-exec" ]]; then
  [[ -n "${REPO:-}" ]] && cmd+=( --repo "$REPO" )
  [[ -n "${MAX_TURNS:-}" ]] && cmd+=( --max-turns "$MAX_TURNS" )
elif [[ "$SCRIPT" == "codex-headless-exec" ]]; then
  [[ -n "${REPO:-}" ]] && cmd+=( --repo "$REPO" )
fi
cmd+=( -- "<self-contained chunk spec>" )
"${cmd[@]}"
```

- [ ] **Step 6: Soften Grok cost language in `grok-execute.md`**

After “Where it sits on the work ladder”, add:

```markdown
**`/auto-execute` integration:** Grok is a first-class backend on the project
worker profile (`stateful` / `escalation` / `review_lens` ladders). The
conductor routes via `scripts/worker-resolve.py` — prefer `/auto-execute`
for multi-chunk jobs; use `/grok-execute` for a single forced Grok call.
```

Remove or rewrite any sentence that says Grok is “not yet wired” into auto-execute / is only a manual higher-cost option outside the farm.

- [ ] **Step 7: Commit**

```bash
cd /mnt/d/Projects/360-HEXTILE/meta-dev
git add plugins/meta-dev/commands/auto-execute.md plugins/meta-dev/commands/grok-execute.md
git commit -m "$(cat <<'EOF'
docs(auto-execute): capability-aware routing via worker-resolve

Replace hardcoded DeepSeek→GLM bias with profile + probe + slash/write
filters. Wire --grok and document credit-driven profile switching.
EOF
)"
```

---

### Task 4: Reference docs + config-cascade

**Files:**
- Create: `plugins/meta-dev/references/worker-routing.md`
- Modify: `plugins/meta-dev/references/config-cascade.md` (add Workers row + example)

- [ ] **Step 1: Write `worker-routing.md`**

Full content:

```markdown
# Worker Routing (`meta_dev.workers`)

Used by `/auto-execute` via `scripts/worker-resolve.py`.

## Why

Different machines have different keys, logins, and credit budgets. Different
chunks need different capabilities (Claude Code slash harness vs Grok/Codex
own-harness). Routing is **data**, not prose rewrites of auto-execute.

## Cascade

Same three layers as all meta-dev settings:

1. Plugin defaults (`templates/settings.json`)
2. Project `plans/_dashboard/settings.json` (commit for the team)
3. Local `plans/_dashboard/settings.local.json` (gitignored — personal credits)

## Profiles

| Profile | Intent |
|---------|--------|
| `default` | DeepSeek farm (+ glm fallback); GLM then Grok for stateful/escalate; Codex then Grok for review |
| `grok-first` | Prefer Grok over GLM for stateful/escalate/plan_write/review; farm deep→sonnet (slash-capable fallback, not grok — grok cannot run `/meta-execute`) |
| `no-glm` | GLM disabled (out of Z.AI credits or avoid 3-slot ceiling); sonnet as Claude-family fallback |
| `budget` | Cheap only — deep + glm; disable frontier (grok/sonnet/opus/fable) |

**Dual source of profiles:** `templates/settings.json` is the cascade default; `BUILTIN_PROFILES` in `worker-resolve.py` is a **fallback seed** when a profile name is missing after merge. Keep them **identical** — Task 1 and Task 2 both paste the same tables; if you change one, change the other in the same commit.

Set:

```bash
# team / project
bash ${CLAUDE_PLUGIN_ROOT}/scripts/config-set.sh meta_dev.workers.active_profile grok-first project

# this machine only (credits personal)
bash ${CLAUDE_PLUGIN_ROOT}/scripts/config-set.sh meta_dev.workers.active_profile no-glm local

# one-shot (no file write)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/worker-resolve.py route --profile budget --role farm --needs-write
```

Or hand-edit `plans/_dashboard/settings.json`:

```json
{
  "meta_dev": {
    "workers": {
      "active_profile": "grok-first"
    }
  }
}
```

## Auth probes

| Backend | Probe |
|---------|-------|
| deep | `DEEPSEEK_API_KEY` |
| glm | `GLM_API_KEY` |
| sonnet/opus/fable | `claude` on PATH |
| grok | `grok` on PATH + `~/.grok/auth.json` |
| codex | `codex` on PATH + (`~/.codex/auth.json` or `OPENAI_API_KEY`) |

`probe_auth: false` trusts the ladder without checking (CI fixtures / offline dry-runs).

## Credits (human, not scraped)

Vendors do not expose reliable free-balance APIs for all backends. When credits
run out, switch profile or disable the backend — do not wait for a 402 mid-run.

## Capability rules

- `needs_slash` → only `family: claude-code`
- `needs_write` → only `write: true` (excludes codex)
- `review_lens` → codex allowed; prefer readonly

## Custom ladders

```json
{
  "meta_dev": {
    "workers": {
      "active_profile": "my-lab",
      "profiles": {
        "my-lab": {
          "farm": ["deep", "sonnet"],
          "stateful": ["sonnet", "grok"],
          "escalation": ["grok", "sonnet"],
          "plan_write": ["sonnet"],
          "review_lens": ["grok", "codex"],
          "disabled": ["glm"]
        }
      }
    }
  }
}
```

## CLI

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/worker-resolve.py show
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/worker-resolve.py probe
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/worker-resolve.py route --role stateful --needs-write
```
```

- [ ] **Step 2: Patch `config-cascade.md`**

Under “When to Use Each Layer” table, add:

```markdown
| Local | Worker profile when credits are personal (`workers.active_profile`, `workers.profiles.*.disabled`) |
| Project | Shared worker profile for the team (`grok-first` if the lab standardizes on xAI) |
```

Under Dot-Notation examples:

```markdown
`config-get.sh meta_dev.workers.active_profile` -> `"default"`
`config-set.sh meta_dev.workers.active_profile grok-first project`
```

Add at end:

```markdown
## Workers

See `references/worker-routing.md` for profiles, probes, and capability routing.
```

- [ ] **Step 3: Commit**

```bash
cd /mnt/d/Projects/360-HEXTILE/meta-dev
git add plugins/meta-dev/references/worker-routing.md plugins/meta-dev/references/config-cascade.md
git commit -m "$(cat <<'EOF'
docs(workers): routing reference + config-cascade entries

Document profiles, auth probes, and credit-driven profile switches for
per-project /auto-execute adaptability.
EOF
)"
```

---

### Task 5: Plugin test harness + version bump

**Files:**
- Modify: `plugins/meta-dev/scripts/test-plugin.sh` (optional tiny hook to run worker-resolve unit tests if pytest present)
- Modify: `plugins/meta-dev/.claude-plugin/plugin.json` (patch version)

- [ ] **Step 1: Add pytest hook to test-plugin.sh**

After `check_templates` (or at end of script before summary), add a function:

```bash
check_worker_resolve() {
  echo "=== worker-resolve unit tests ==="
  if python3 -m pytest --version &>/dev/null; then
    if python3 -m pytest "$PLUGIN_DIR/tests/test_worker_resolve.py" -q; then
      PASS=$((PASS+1)); green "  PASS: test_worker_resolve.py"
    else
      FAIL=$((FAIL+1)); red "  FAIL: test_worker_resolve.py"
    fi
  else
    echo "  SKIP: pytest not installed"
  fi
}
```

Wire it into `--check-all` / default path the same way other checks are invoked (read the bottom of `test-plugin.sh` and add `check_worker_resolve` next to `check_templates`).

- [ ] **Step 2: Run full schema + unit checks**

```bash
cd /mnt/d/Projects/360-HEXTILE/meta-dev
export CLAUDE_PLUGIN_ROOT="$(pwd)/plugins/meta-dev"
bash plugins/meta-dev/scripts/test-plugin.sh --check-schemas
python3 -m pytest plugins/meta-dev/tests/test_worker_resolve.py -q
```

Expected: PASS.

- [ ] **Step 3: Bump plugin patch version**

In `plugins/meta-dev/.claude-plugin/plugin.json`, increment patch: e.g. `1.3.38` → `1.3.39` (use whatever current is + 1).

- [ ] **Step 4: Final commit**

```bash
cd /mnt/d/Projects/360-HEXTILE/meta-dev
git add plugins/meta-dev/scripts/test-plugin.sh plugins/meta-dev/.claude-plugin/plugin.json
git commit -m "$(cat <<'EOF'
chore(meta-dev): v1.3.39 — worker-resolve in test suite

Bump patch so Claude Code plugin cache rebuilds with auto-execute routing.
EOF
)"
```

(Adjust version string in message to match actual bump.)

---

### Task 6: Consumer project example (360-Hextile) — optional but recommended

**Files:**
- Modify: `/mnt/d/Projects/360-Hextile/plans/_dashboard/settings.json` (meta repo)
- Optional context note: `/mnt/d/Projects/360-Hextile/.claude/context/harness/model-tiers.md` one-paragraph pointer

**Only if Phong wants 360-Hextile on Grok-first immediately.** This is a *consumer* of the plugin, separate git repo.

- [ ] **Step 1: Set project profile**

In `plans/_dashboard/settings.json`, merge under `meta_dev`:

```json
"workers": {
  "active_profile": "grok-first"
}
```

(Leave full profiles in plugin defaults; project only sets `active_profile` unless customizing ladders.)

- [ ] **Step 2: Verify**

```bash
export CLAUDE_PLUGIN_ROOT=/mnt/d/Projects/360-HEXTILE/meta-dev/plugins/meta-dev
cd /mnt/d/Projects/360-Hextile
python3 "$CLAUDE_PLUGIN_ROOT/scripts/worker-resolve.py" show
# expect active_profile: grok-first
python3 "$CLAUDE_PLUGIN_ROOT/scripts/worker-resolve.py" route --role stateful --needs-write
# expect backend: grok if auth present, else glm/deep per probe
python3 "$CLAUDE_PLUGIN_ROOT/scripts/worker-resolve.py" route --role stateful --needs-slash --needs-write
# expect never grok
```

- [ ] **Step 3: Commit in the 360-Hextile meta repo**

```bash
cd /mnt/d/Projects/360-Hextile
git add plans/_dashboard/settings.json
git commit -m "$(cat <<'EOF'
chore(workers): active_profile grok-first for auto-execute

Prefer Grok over GLM for stateful/escalation/review when authenticated;
slash-required phases still stay on Claude-family backends.
EOF
)"
```

---

## Self-review (plan author)

| Spec requirement | Task |
|------------------|------|
| Per-project settings | T1 schema/template + cascade; T6 example |
| Change by credits / access | Profiles `no-glm`/`budget` + `probe_auth` + local disable + `--profile` one-shot (T2, T4) |
| Wire Grok into auto-execute | T2 registry + T3 doctrine |
| Deprioritize GLM / prioritize Grok | `grok-first` profile (T1) — Grok on stateful/escalation/review; farm stays deep→sonnet (slash-safe) |
| Best model per aspect of task | Roles: farm/stateful/plan_write/review_lens/escalation + capability filters (T2–T3) |
| Adaptable / efficient | Auth skip unavailable; farm fallbacks; fanout + concurrency_cap; force + profile flags |
| No freestyle LLM routing | Resolver is source of truth (T3) |
| Version bump for plugin cache | T5 |
| Edit source only (not cache) | Global Constraints |

**Placeholder scan:** none intentional.  
**Type consistency:** `NoBackendError`, roles enum, JSON route shape consistent across T2 tests and T3 conductor docs.

### Hardened by `/loop-gap` (this session)

Fixed before execute: broken `test_probe_auth_*` bodies; farm ladders with auth/slash-safe fallbacks; `resolve_route` probe default; `--profile` one-shot CLI; bash array dispatch (empty dispatch for grok); config-set layer args; plan_write+needs_slash note; dual-source profile sync rule; codex/grok flag matrix on dispatch.

---

## Execution handoff

Plan saved to:

`meta-dev/plans/2026-07-15-auto-execute-worker-routing.md`

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — this session, task-by-task with checkpoints  

**Also confirm before execute:**

- Include **Task 6** (set 360-Hextile to `grok-first`)?  
- Ship-only plugin first, then consumer settings in a second go?

Say **go** / **execute this** (and option 1 or 2 + Task 6 yes/no) when ready. Per project rules, finishing this plan is a full stop until that explicit authorization.
