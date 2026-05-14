# Inbox Options Security

## Command Whitelist

`options.command` values from `source=user` adds are sanitized:
- Only allow `/meta-*` slash commands
- Only allow known plugin commands
- Reject arbitrary shell commands

## Internal Sources (trusted)

Items from overlord_finding, sweep_anomaly, review_failure, etc. are system-generated.
Their `options.command` values are constructed by trusted scripts — no sanitization needed.

## Advisory Execution

When user selects an option, the command is invoked as a slash command.
The command itself handles its own safety (permissions, gates, etc.).
