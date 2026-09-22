"""Risk-tag floor over mocked Jev answers."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def load_compose():
    path = Path(__file__).resolve().parents[1] / "scripts" / "lib" / "jev-compose.py"
    spec = importlib.util.spec_from_file_location("jev_compose", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compose = load_compose().compose


def test_auth_payment_forces_high_despite_low_jev():
    answers = {
        "budget": {
            "type": "choice",
            "choice": "low",
            "probabilities": {"low": 0.99},
            "confidence": 0.99,
        },
        "hotl": {"type": "noul", "noul": 0.99},
        "needs_cross_family": {"type": "noul", "noul": 0.01},
    }
    out = compose("low", "security-boundary,money-path", answers, fail_open=False)
    assert out["budget"] == "high"
    assert out["hotl"] is False
    assert out["extra_family_skip"] is False


def test_fail_open_keeps_keyword_budget():
    out = compose("medium", "none", {}, fail_open=True)
    assert out["budget"] == "medium"
    assert out["extra_family_skip"] is None
    assert out["fail_open"] is True
