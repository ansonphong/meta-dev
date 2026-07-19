---
name: repair
description: "Alias of /meta-repair — identical command (pure redirect: `Execute /meta-repair $ARGUMENTS`). /repair and /meta-repair are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: <failure-output | plan-path>
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---
Execute /meta-repair $ARGUMENTS
