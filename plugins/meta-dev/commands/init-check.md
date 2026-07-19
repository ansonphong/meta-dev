---
name: init-check
description: "Alias of /meta-init-check — identical command (pure redirect: `Execute /meta-init-check $ARGUMENTS`). /init-check and /meta-init-check are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: "[--quick | --full]"
allowed-tools: [Skill, Read, Bash, Glob, Grep]
model: opus
---
Execute /meta-init-check $ARGUMENTS
