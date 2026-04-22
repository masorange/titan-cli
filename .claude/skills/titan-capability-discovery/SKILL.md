---
name: titan-capability-discovery
description: Inspect a project and Titan public docs to discover reusable workflow capabilities before creating new workflow code. Use when you need to know what workflows, steps, integrations, or ctx.textual capabilities already exist.
disable-model-invocation: false
user-invocable: false
---

# Titan Capability Discovery

Inspect before inventing.

## Goal

Identify what can be reused from:

1. the current project's `.titan/`
2. Titan public docs
3. existing workflow and step structure

## Inspection Order

1. Review `.titan/workflows/*.yaml`.
2. Review `.titan/steps/**/*.py`.
3. Review `.titan/operations/`, `.titan/clients/`, and `.titan/services/` if present.
4. Review relevant public Titan docs when the local project is not enough.

## Output

Return:

1. Existing workflows worth extending or calling.
2. Existing steps worth reusing.
3. Existing project domains or integrations worth building on.
4. Missing pieces that actually need new code.

## References

1. `references/project-inspection-checklist.md`
2. `references/public-titan-capabilities.md`
3. `references/ctx-textual-capabilities.md`
