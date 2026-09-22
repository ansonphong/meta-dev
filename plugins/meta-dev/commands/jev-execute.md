---
name: jev-execute
argument-hint: "<text> [--mock] [--json] [--question id:type:instructions]"
description: "Ask Jev System One for typed answers. Does not spawn a worker or run git."
---

# /jev-execute

Prognostication only. Run `scripts/jev-execute.sh` on the user's text. Honor `--mock`. Print the JSON answers (`noul`, `choice` plus probabilities, or `score`). Do not spawn a coding worker. Do not run git. Do not put an API key in the transcript.

Missing `TYPESAFE_API_KEY` and `OPENROUTER_API_KEY` fails open. `JEV_MOCK=1` skips the network. Never call `/chat/completions`.
