---
name: init
description: "Alias of /meta-init — identical command (pure redirect: `Execute /meta-init $ARGUMENTS`). /init and /meta-init are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: "[--auto | --dry-run]"
allowed-tools: [Skill, Read, Write, Edit, Bash(bash:*), Bash(python3:*), Bash(git:*)]
model: opus
---
Execute /meta-init $ARGUMENTS
