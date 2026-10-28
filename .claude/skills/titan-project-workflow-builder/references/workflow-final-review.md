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
9. Step function names equal their YAML `step:` names (no `_step` suffix).
10. Outputs flow through result `metadata`, not `ctx.data` mutation at return.
11. No raw secret in `ctx.data`/metadata; clients built with `ctx.secret_broker.create_client`.
12. Every AI-calling step has `@declare_ai_usage`, routes through `ctx.ai_router`, passes
    `announce=ctx.textual.ai_chip`, and treats `AI_DISABLED` as `Skip`.
