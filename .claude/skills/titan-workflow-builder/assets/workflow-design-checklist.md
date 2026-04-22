# Workflow Design Checklist

1. Reuse existing workflow if possible.
2. Prefer `command` over new Python when safe.
3. Create `plugin: project` steps only when needed.
4. Keep step entrypoints under `.titan/steps/**`.
5. Extract operations if logic stops being trivial.
6. Use `Exit` only for early clean termination.
7. Keep cleanup reachable.
