---
name: titan-workflow-architecture
description: Choose the correct Titan architecture for new workflow code. Use when deciding between command steps, project steps, operations, clients, services, or a plugin-like project layout, or when the user asks how much architecture is justified.
disable-model-invocation: false
user-invocable: false
---

# Titan Workflow Architecture

Decide the smallest correct architecture for workflow-related code.

## Goal

Prevent both under-design and over-design.

## Decision Rules

### 1. Prefer orchestration first

Use:

1. workflow extension
2. nested workflow
3. command step

before adding Python.

### 2. Add a project step when orchestration is not enough

Create a project step when the workflow needs:

1. branching logic
2. prompts or `ctx.textual`
3. metadata flow
4. Python-only integration code

### 3. Extract operations when logic becomes reusable

Create an operation when you see:

1. parsing
2. filtering
3. ranking
4. validation
5. domain orchestration

that would clutter the step.

### 4. Create clients only for real reusable integrations

Use `references/when-to-create-client.md`.

Do not create a client unless there is a stable domain or integration worth reusing.

### 5. Use plugin-like project layout when the domain deserves it

For reusable domains, prefer a project layout that resembles a plugin while staying compatible with Titan project-step discovery.

See `references/plugin-like-project-architecture.md`.

## References

1. `references/when-to-use-command-vs-step.md`
2. `references/when-to-create-operation.md`
3. `references/when-to-create-client.md`
4. `references/plugin-like-project-architecture.md`
5. `references/layer-boundaries.md`

## Assets

1. `assets/project-step-template.py`
2. `assets/operation-template.py`
3. `assets/client-template.py`
