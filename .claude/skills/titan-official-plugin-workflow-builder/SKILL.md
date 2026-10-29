---
name: titan-official-plugin-workflow-builder
description: Design and create workflows for official Titan plugins inside the titan-cli repository. Use when adding or changing workflows in plugins/titan-plugin-*, registering plugin steps, or extending official plugin capabilities that stay inside this repository.
disable-model-invocation: false
---

# Titan Official Plugin Workflow Builder

Build workflows for official Titan plugins inside `titan-cli`.

## Goal

Create or update workflows that belong to official plugins inside this repository.

## Scope

Use this skill when the workflow belongs inside:

1. `plugins/titan-plugin-*/titan_plugin_*/workflows/`
2. `plugins/titan-plugin-*/titan_plugin_*/steps/`
3. plugin operations, clients, services, or models used by those workflows

These workflows are internal to this repository, but they still expose official plugin capabilities and should follow repo architecture and documentation rules.

## Required process

### 1. Discover plugin structure first

Inspect:

1. `plugin.py`
2. existing `get_steps()` wiring
3. existing workflow files under the plugin package
4. existing steps, operations, clients, and services
5. plugin docs under `docs/plugins/`

### 2. Reuse before creating

Prefer:

1. extending an existing plugin workflow
2. reusing an existing plugin step
3. reusing an existing client API
4. adding operations before adding deeper layers unnecessarily

### 3. Respect official plugin architecture

Use `titan-workflow-architecture` rules with extra rigor.

For official plugins:

1. steps should stay thin
2. operations hold business logic when complexity warrants it
3. clients expose the public API
4. services remain internal
5. docs must be kept in sync when public plugin capability changes
6. services return `ClientResult[UIModel]`; `Network*` models mirror the API, `UI*` models
   are pre-formatted, mappers are pure (`.claude/docs/plugin-architecture.md`)
7. steps never call low-level client methods (`run_in_worktree`, `run_command`)
8. the plugin gets credentials in `initialize(config, broker)` and builds its client with
   `broker.create_client(...)`; AI steps use `declare_ai_usage` + `ctx.ai_router`
   (`titan-workflow-architecture` → `references/step-contracts.md`)

If the change needs a new public client function (not just a workflow over existing
ones), use the `titan-plugin-capability` skill for that part.

### 4. Register steps correctly

Official plugin steps are exposed via `get_steps()` in `plugin.py`.

Whenever a new step is added, update plugin registration accordingly.

### 5. Update plugin docs when public capability changes

If the change adds or changes a public plugin capability, update `docs/plugins/<plugin>/`
(`overview.md`, `workflow-steps.md`, `client-api.md`, `built-in-workflows.md` — whichever
the change touches), then regenerate the step reference with the `sync-plugin-docs`
workflow and check it with `validate-plugin-docs` (`.titan/workflows/`).

## References

1. `references/official-plugin-workflow-layout.md`
2. `references/official-plugin-step-registration.md`
3. `references/official-plugin-doc-rules.md`
4. `references/official-plugin-decision-flow.md`
5. `.claude/docs/workflow-step-rules.md` (step conventions, including: errors are error cards)
