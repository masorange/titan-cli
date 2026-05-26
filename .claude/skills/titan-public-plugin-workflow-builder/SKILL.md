---
name: titan-public-plugin-workflow-builder
description: Design and create workflows for public or community Titan plugins intended for external users. Use when adding workflows to a plugin package that will be distributed outside its current repository.
disable-model-invocation: false
---

# Titan Public Plugin Workflow Builder

Build workflows for distributed Titan plugins intended for external consumers.

## Goal

Create or update plugin workflows that become part of a public plugin package.

## Scope

Use this skill when the workflow belongs inside a plugin package that will be consumed outside the current repository.

Examples:

1. community plugins
2. external plugin repositories
3. plugin packages organized by feature, domain, or category

## Required process

### 1. Inspect the plugin package structure

Check:

1. `plugin.py`
2. workflow directories
3. step registration strategy
4. feature, domain, or category layout
5. existing operations, clients, and services

### 2. Preserve the plugin's public contract

Treat the plugin as a public capability surface.

Prefer:

1. stable workflow naming
2. stable step names
3. reuse of existing client APIs
4. clear layout by category and layer

### 3. Follow plugin-specific registration rules

Do not assume project-step discovery.

Public plugins expose steps through plugin registration, often via:

1. `plugin.py -> get_steps()`
2. one or more step registry modules

### 4. Keep the layout reusable

When the plugin already organizes by feature, domain, or category first, respect that structure.

Example:

1. `<category>/steps/...`
2. `<category>/operations/...`
3. `<category>/clients/...`

### 5. Think like a public plugin author

Prefer changes that stay maintainable for external users and future releases.

## References

1. `references/public-plugin-workflow-layout.md`
2. `references/public-plugin-step-registration.md`
3. `references/public-plugin-stability-rules.md`
4. `references/project-vs-plugin-workflow.md`
