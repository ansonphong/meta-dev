"""Pytest config for planctl tests — hermeticity seams + import path.

Puts the plugin ``scripts/`` dir on ``sys.path`` so ``from planctl import …``
resolves when pytest is invoked plainly (``cd meta-dev && python3 -m pytest
plugins/meta-dev/tests/planctl/…``), and pins the two hermeticity env seams
(``META_DEV_STATE_DIR`` / ``META_DEV_ROOT``) to a per-test tmp dir — so any
planctl import that resolves state paths stays off the real ``~/.cache/meta-dev``
and off the live host tree. ``test_derive.py`` is pure-function and needs
neither, but the seams are set defensively for the DB-touching tests landing in
0c–0e.
"""
import os
import pathlib
import sys

# conftest lives at plugins/meta-dev/tests/planctl/ — scripts/ is two parents up
# (planctl/ -> tests/ -> plugins/meta-dev/) then /scripts.
_HERE = pathlib.Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import pytest  # noqa: E402  (after the sys.path insert above)


@pytest.fixture(autouse=True)
def _hermetic_state(tmp_path, monkeypatch):
    monkeypatch.setenv("META_DEV_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("META_DEV_ROOT", str(tmp_path / "root"))
    yield
