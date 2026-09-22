#!/usr/bin/env python3
"""TypeSafe Jev System One client.

Sends state + typed questions. Never calls /chat/completions.
Missing credentials fail open and do not raise.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

TYPESAFE_ROOT = "https://api.typesafe.ai"
OPENROUTER_DECISIONS = "https://openrouter.ai/api/alpha/decisions"

DISPATCH_QUESTIONS = {
    "rung": {
        "type": "choice",
        "instructions": "Pick a legal host rung id.",
        "criteria": {
            "grok45_or_luna": "collect or mechanical",
            "grok46_or_terra": "ordinary",
            "grok46_high_or_sol": "hard",
            "deep": "pooled flash",
            "sonnet_or_opus": "rare extra family",
            "none_of_the_above": "no listed rung",
        },
    },
    "budget": {
        "type": "choice",
        "instructions": "Pick a depth budget.",
        "criteria": {
            "low": "mechanical",
            "medium": "ordinary",
            "high": "hard or risky",
        },
    },
    "hotl": {
        "type": "noul",
        "instructions": "Is this safe to auto-execute under blast-radius rules?",
    },
    "needs_cross_family": {
        "type": "noul",
        "instructions": "Is a second-family reviewer warranted?",
    },
}

PROGNOSTICATE_QUESTIONS = {
    "safe_to_auto": {
        "type": "noul",
        "instructions": "Is this safe to auto-execute under blast-radius rules?",
    },
    "task_shape": {
        "type": "choice",
        "instructions": "What shape is this task?",
        "criteria": {
            "collect": "filename or inventory",
            "ordinary": "bounded edit",
            "hard": "architecture or ambiguous",
        },
    },
    "stakes": {
        "type": "score",
        "instructions": "How high are the stakes?",
        "criteria": ["none", "low", "medium", "high"],
    },
}


def fail_open(reason):
    return {"fail_open": True, "reason": reason, "answers": {}, "mock": False}


def _redact(text, secrets):
    out = str(text)
    for secret in secrets:
        if secret:
            out = out.replace(secret, "[REDACTED]")
    return out


def _door(env):
    """Return (key, url, model) or ('', '', '') when no key is set."""
    typesafe = (env.get("TYPESAFE_API_KEY") or "").strip()
    openrouter = (env.get("OPENROUTER_API_KEY") or "").strip()
    base = (env.get("TYPESAFE_BASE_URL") or "").strip().rstrip("/")
    if typesafe:
        root = base or TYPESAFE_ROOT
        return typesafe, root + "/v1/systemone", "jev-latest"
    if openrouter:
        if base:
            return openrouter, base + "/v1/systemone", "typesafe/jev-1.13"
        return openrouter, OPENROUTER_DECISIONS, "typesafe/jev-1.13"
    return "", "", ""


def _mock_answer(question):
    kind = question.get("type")
    if kind == "choice":
        criteria = question.get("criteria") or {}
        if isinstance(criteria, dict) and criteria:
            choice = next(iter(criteria))
        else:
            choice = "none_of_the_above"
        return {
            "type": "choice",
            "choice": choice,
            "probabilities": {choice: 1.0},
            "confidence": 1.0,
        }
    if kind == "score":
        return {"type": "score", "score": 0.0, "legend": question.get("criteria") or []}
    return {"type": "noul", "noul": 0.5}


def _mock_answers(questions):
    return {key: _mock_answer(spec) for key, spec in questions.items()}


def _urlopen_transport(url, headers, body):
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError("HTTP %s %s" % (exc.code, detail)) from exc
    return json.loads(raw)


def evaluate(state, questions, *, transport=None, env=None, mock=False):
    """Return typed answers, or a fail-open object. Does not raise for auth or HTTP failure."""
    if questions is None:
        questions = {}
    source = os.environ if env is None else env
    if mock or str(source.get("JEV_MOCK") or "") == "1":
        return {
            "fail_open": False,
            "reason": "mock",
            "mock": True,
            "answers": _mock_answers(questions),
        }

    key, url, model = _door(source)
    if not key:
        return fail_open("missing_key")
    if "/chat/completions" in url:
        return fail_open("refused_chat_completions")

    payload = {"model": model, "state": state, "questions": questions}
    headers = {
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    }
    send = transport or _urlopen_transport
    try:
        raw = send(url, headers, payload)
    except Exception as exc:
        return fail_open(_redact(exc, [key]))

    answers = raw.get("answers") if isinstance(raw, dict) else None
    if not isinstance(answers, dict):
        return fail_open("bad_response")
    return {
        "fail_open": False,
        "reason": "",
        "mock": False,
        "model": model,
        "answers": answers,
    }
