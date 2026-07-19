---
name: config
description: "Alias of /meta-config — identical command (pure redirect: `Execute /meta-config $ARGUMENTS`). /config and /meta-config are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: "[get <path> | set <path> <value> [--local] | reset | export | import <file>]"
allowed-tools: [Skill, Read, Write, Bash(bash:*)]
model: opus
---
Execute /meta-config $ARGUMENTS
