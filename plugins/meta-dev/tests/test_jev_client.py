"""Injected-transport tests for the Jev System One client."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def load_client():
    path = Path(__file__).resolve().parents[1] / "scripts" / "lib" / "jev-client.py"
    spec = importlib.util.spec_from_file_location("jev_client", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLIENT = load_client()
DUMMY = "typ_test_dummy_not_live"


def test_systemone_shape_and_bearer_redacted(capsys):
    seen = {}

    def transport(url, headers, body):
        seen["url"] = url
        seen["headers"] = headers
        seen["body"] = body
        return {
            "answers": {
                "rung": {
                    "type": "choice",
                    "choice": "deep",
                    "probabilities": {"deep": 1.0},
                    "confidence": 0.9,
                }
            }
        }

    result = CLIENT.evaluate(
        "classify this task",
        {
            "rung": {
                "type": "choice",
                "instructions": "pick",
                "criteria": {"deep": "pooled"},
            }
        },
        transport=transport,
        env={"TYPESAFE_API_KEY": DUMMY},
    )
    print(json.dumps(result))
    captured = capsys.readouterr().out
    assert DUMMY not in captured
    assert "/chat/completions" not in seen["url"]
    assert seen["url"] == "https://api.typesafe.ai/v1/systemone"
    assert seen["headers"]["Authorization"] == "Bearer " + DUMMY
    assert seen["body"]["model"] == "jev-latest"
    assert seen["body"]["state"] == "classify this task"
    assert seen["body"]["questions"]["rung"]["type"] == "choice"
    assert result["fail_open"] is False
    assert result["answers"]["rung"]["choice"] == "deep"


def test_openrouter_alpha_door():
    seen = {}

    def transport(url, headers, body):
        seen["url"] = url
        seen["body"] = body
        return {"answers": {}}

    CLIENT.evaluate("x", {}, transport=transport, env={"OPENROUTER_API_KEY": "or-test-dummy"})
    assert seen["url"] == "https://openrouter.ai/api/alpha/decisions"
    assert "/chat/completions" not in seen["url"]
    assert seen["body"]["model"] == "typesafe/jev-1.13"


def test_empty_env_fails_open():
    result = CLIENT.evaluate("task", {"q": {"type": "noul", "instructions": "x"}}, env={})
    assert result["fail_open"] is True
    assert result["answers"] == {}
    assert result["reason"] == "missing_key"


def test_transport_error_redacts_key():
    def transport(url, headers, body):
        raise RuntimeError("rejected " + DUMMY)

    result = CLIENT.evaluate("task", {}, transport=transport, env={"TYPESAFE_API_KEY": DUMMY})
    assert result["fail_open"] is True
    assert DUMMY not in result["reason"]
    assert "[REDACTED]" in result["reason"]


def test_mock_skips_transport():
    def transport(url, headers, body):
        raise AssertionError("network")

    result = CLIENT.evaluate(
        "task",
        {"safe": {"type": "noul", "instructions": "safe?"}},
        transport=transport,
        env={},
        mock=True,
    )
    assert result["mock"] is True
    assert result["answers"]["safe"]["noul"] == 0.5
