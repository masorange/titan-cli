# Workflow Final Review

Before finishing, confirm:

1. The workflow lives in `.titan/workflows/<name>.yaml`.
2. It uses `extends` only when a real base workflow exists.
3. Each step is one of: `plugin`, `command`, or `workflow`.
4. Params are passed with `${key}` only where needed.
5. `Error` handling is explicit when failure should not stop execution.
6. `Exit` is only used before resources requiring cleanup are created.
7. Cleanup steps are still reachable if intermediate work is skipped or fails.
8. New Python code exists only where orchestration alone is insufficient.
