---
name: titan-workflow-builder
description: Design and create complete Titan workflows from user requirements. Use when the user wants to create, extend, refactor, or scaffold a Titan workflow, asks for workflow YAML, project steps, hooks, or wants guidance that ends with a working workflow.
disable-model-invocation: false
---

# Titan Workflow Builder

Build Titan workflows end-to-end while teaching briefly as you go.

## Goal

Turn user requirements into a complete Titan workflow that:

1. Reuses existing Titan capabilities first.
2. Chooses the smallest correct architecture.
3. Produces working files under `.titan/`.
4. Respects Titan semantics for hooks, params, result types, and cleanup.

## Workflow

### 1. Clarify the task

Capture:

1. What the workflow should automate.
2. Whether this should extend an existing workflow or create a new one.
3. Whether the workflow is simple or introduces a reusable domain integration.

Keep questions minimal. If the repo already makes the answer clear, do not ask.

### 2. Discover before creating

Use `titan-capability-discovery` behavior before writing code.

Check:

1. Existing `.titan/workflows/*.yaml` files.
2. Existing `.titan/steps/**/*.py` files.
3. Existing reusable code under `.titan/operations/`, `.titan/clients/`, `.titan/services/`.
4. Relevant public Titan docs if local project context is insufficient.

Prefer:

1. Extending an existing workflow.
2. Calling an existing workflow.
3. Reusing an existing step.
4. Using a command step.
5. Creating new code only when necessary.

### 3. Decide the implementation shape

Follow `references/workflow-decision-flow.md`.

Choose between:

1. Pure YAML orchestration.
2. YAML + project step.
3. YAML + project step + operation.
4. Plugin-like project layout for reusable domains.

Use `titan-workflow-architecture` rules when that choice is not obvious.

### 4. Generate the workflow

Create files under `.titan/` using these rules:

1. Workflows always live in `.titan/workflows/`.
2. Project step entrypoints must remain discoverable under `.titan/steps/**`.
3. Extra code may be organized by domain under `.titan/operations/`, `.titan/clients/`, `.titan/services/`.

Useful templates:

1. `assets/new-workflow-template.yaml`
2. `assets/extends-workflow-template.yaml`
3. `references/step-authoring-basics.md`

### 5. Validate the result

Review the generated design against `references/workflow-final-review.md` and `references/workflow-antipatterns.md`.

Always verify:

1. `Skip` vs `Exit`
2. `on_error` usage
3. cleanup guarantees
4. parameter flow via `ctx.get()` and metadata
5. whether new code is justified

## Output expectations

When the user wants implementation, finish with:

1. A workflow file.
2. Any required step/operation/client files.
3. A short explanation of key decisions.

When the user wants guidance only, provide:

1. The recommended architecture.
2. The file layout.
3. The workflow shape.

## References

1. `references/workflow-decision-flow.md`
2. `references/workflow-final-review.md`
3. `references/workflow-antipatterns.md`
4. `references/step-authoring-basics.md`

## Assets

1. `assets/new-workflow-template.yaml`
2. `assets/extends-workflow-template.yaml`
3. `assets/workflow-design-checklist.md`
