# Codex Command Adapter

Use this contract whenever a native command skill points at a canonical
`commands/*.md` procedure.

1. Resolve the plugin root from the command skill's own path. Never guess it
   from the working directory.
2. Read the named command file completely before acting. Treat the user's text
   after the skill mention as `$ARGUMENTS`.
3. Apply `references/workflows/protocol.md` as the host-neutral authority for
   permissions, state, verification, review routing, and result states.
4. Translate Claude-only mechanics without changing the command's outcome:
   - `${CLAUDE_PLUGIN_ROOT}` means the resolved plugin root.
   - Read/Glob/Grep/Bash/Write/Edit mean the equivalent native Codex tools;
     edit repository files with the host's patch mechanism.
   - TaskCreate/TaskUpdate mean Codex's visible plan/task tracker when one is
     available.
   - Agent/Task delegation means native Codex delegation. Use an external
     backend only when the user selected that backend.
   - A referenced `/command` means invoke its exact native command skill when
     available, otherwise read its canonical command file and follow it inline.
   - A referenced Claude Skill means use the matching native skill when
     available, otherwise read its `workflow-skills/<name>/SKILL.md` source and
     follow it inline.
   - Claude command frontmatter such as `allowed-tools:` and `model:` is not a
     Codex capability contract. Use the configured Codex route instead.
5. In Codex, read applicable `AGENTS.md` files first, then the project's routed
   neutral context. Do not consult `CLAUDE.md` for project details. Inspect it
   only when the command itself explicitly concerns an adapter, compatibility,
   or migration.
6. Preserve all permission gates. Planning, review, audit, and diagnosis do not
   authorize source implementation.

If the command procedure conflicts with the shared protocol because it names a
Claude-only reviewer or unavailable surface, the shared protocol wins while
the artifact and acceptance contract remain unchanged.
