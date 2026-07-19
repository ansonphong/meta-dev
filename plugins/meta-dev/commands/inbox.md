---
name: inbox
description: "Alias of /meta-inbox — identical command (pure redirect: `Execute /meta-inbox $ARGUMENTS`). /inbox and /meta-inbox are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: "[list | add | resolve <id> | dismiss <id> | clear | render]"
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep]
model: opus
---
Execute /meta-inbox $ARGUMENTS
