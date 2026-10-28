# Step Authoring Basics

Project step entrypoints must be discoverable under `.titan/steps/**`.

Step contract:

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip, Exit


def my_step(ctx: WorkflowContext) -> WorkflowResult:
    value = ctx.get("key", "default")
    return Success("Done", metadata={"result": value})
```

Rules:

1. Function name must match the workflow `step:` value.
2. Steps orchestrate UI and workflow flow.
3. Steps should not own complex business logic.
4. Use metadata to pass values to later steps; don't write `ctx.data` before returning.
5. Credentials only through `ctx.secret_broker`; never a raw secret in metadata.
6. AI calls: `@declare_ai_usage(...)` + `ctx.ai_router`, `AI_DISABLED` → `Skip`.
7. Don't scroll manually; the screen scrolls on step completion.
8. No doctest examples in docstrings.

Full rules and code: `titan-workflow-architecture` skill, `references/step-contracts.md`.
