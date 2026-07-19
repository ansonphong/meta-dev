---
name: loop-gap
description: "Alias of /meta-loop-gap — identical command (pure redirect: `Execute /meta-loop-gap $ARGUMENTS`). /loop-gap and /meta-loop-gap are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: <plan-dir | feature:name | code-path | project> [--budget auto|low|medium|high] [--iterations N] [--fix-backend deep|glm|opus|sonnet|haiku|fable|inline] [--deep|--glm|--opus|--sonnet|--haiku|--fable]
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---
Execute /meta-loop-gap $ARGUMENTS
