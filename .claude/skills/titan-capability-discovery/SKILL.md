---
name: titan-capability-discovery
description: Inspect a project, plugin package, and Titan public docs to discover reusable workflow capabilities before creating new workflow code. Use when you need to know what workflows, steps, integrations, registration patterns, or ctx.textual capabilities already exist for a project or plugin.
disable-model-invocation: false
user-invocable: false
---

# Titan Capability Discovery

Inspect before inventing.

## Goal

Identify what can be reused from:

1. the current project's `.titan/`
2. a plugin package if the task targets a plugin
3. Titan public docs
4. existing workflow and step structure

## Modes

Choose the right inspection mode first:

1. `project`
   Inspect `.titan/`.
2. `plugin`
   Inspect the plugin package and its registration flow.
3. `public-plugin`
   Inspect the external or community plugin package layout and registration flow.

## Inspection Order

### Project mode

1. Review `.titan/workflows/*.yaml`.
2. Review `.titan/steps/**/*.py`.
3. Review `.titan/operations/`, `.titan/clients/`, and `.titan/services/` if present.

### Plugin mode

1. Review the plugin package root.
2. Review `plugin.py`.
3. Review workflow files under the plugin package.
4. Review step registration modules if present.
5. Review steps, operations, clients, services, and models.

### Shared

1. Review relevant public Titan docs when local package or project context is not enough.

## Output

Return:

1. Existing workflows worth extending or calling.
2. Existing steps worth reusing.
3. Existing project domains or integrations worth building on.
4. Existing plugin registration patterns worth preserving.
5. Missing pieces that actually need new code.

## References

1. `references/project-inspection-checklist.md`
2. `references/public-titan-capabilities.md`
3. `references/ctx-textual-capabilities.md`
