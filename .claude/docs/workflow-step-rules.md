# Workflow Step Rules

Rules for authoring workflow steps in Titan CLI.

## Step Data Outputs

Do not write step outputs directly into `ctx.data` when returning from a step.

Prefer returning outputs through `Success(metadata={...})`, `Skip(metadata={...})`, or `Exit(metadata={...})`. The workflow executor automatically merges result metadata into `ctx.data` for subsequent steps.

Use local variables inside the current step. Use `ctx.data` or `ctx.set()` only when data must be available through the context before the step returns, or when an existing API explicitly requires context mutation.

Bad:

```python
ctx.data["existing_comments_index"] = index

return Success(
    "Comments index built",
    metadata={"existing_comments_index": index},
)
```

Good:

```python
return Success(
    "Comments index built",
    metadata={"existing_comments_index": index},
)
```
