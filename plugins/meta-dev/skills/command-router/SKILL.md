---
name: command-router
description: "Resolve an explicit legacy meta-dev alias through the existing catalog."
---

# Command Router

The primary menu is in `../../references/workflows/protocol.md`. Exact command
skills remain explicitly invocable; this fallback also supports legacy names.

Resolve `../../commands/` from this file, strip a leading slash and look up the
requested name. Bare redirect twins (`Execute /<name> $ARGUMENTS`) lead to the
named canonical command; follow that target rather than deliberating between
aliases. Unknown names fail closed: show matching catalog names and ask which
was intended. Do not invent a procedure.

Read `../../references/workflows/command-adapter.md` and the resolved command.
Reuse already loaded contracts. Load tool/dispatch diagnostics only to resolve
an actual capability or infrastructure problem, not as a routine preflight.
