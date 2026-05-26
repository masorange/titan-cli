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
4. Use metadata to pass values to later steps.
