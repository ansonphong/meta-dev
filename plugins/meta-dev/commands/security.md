---
name: security
description: "Alias of /meta-security — identical command (pure redirect: `Execute /meta-security $ARGUMENTS`). /security and /meta-security are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: "[<repo> | <path>] [--scope auth|payment|all] [--fix]"
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---
Execute /meta-security $ARGUMENTS
