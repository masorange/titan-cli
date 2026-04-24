# Workflow Steps

Workflow steps are Python functions that Titan can execute from a workflow.

This page explains how to write them, how they receive and return data, and when to use each kind of step source.

## What a step function looks like

Every step function follows the same basic signature:

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip, Exit


def my_step(ctx: WorkflowContext) -> WorkflowResult:
    return Success("Done")
```

The function name must exactly match the `step:` value used in YAML.

```python
# .titan/steps/run_linter.py
def run_linter(ctx: WorkflowContext) -> WorkflowResult:
    ...
```

```yaml
- plugin: project
  step: run_linter
```

## Where steps can come from

| Step source | YAML form | Typical use |
|-------------|-----------|-------------|
| Plugin step | `plugin: git`, `plugin: github`, `plugin: jira` | Reuse built-in or plugin-provided capabilities |
| Project step | `plugin: project` | Repository-specific Python logic |
| User step | `plugin: user` | Personal reusable steps in `~/.titan/steps/` |
| Core step | `plugin: core` | Built-in Titan helpers |

## Reading data from the workflow context

Use `ctx.get(...)` to read values from the current workflow context.

```python
branch_name = ctx.get("branch_name")
draft = ctx.get("draft", False)
```

Those values can come from:

- workflow `params`
- step `params`
- metadata returned by earlier steps

## Returning data to later steps

Use the `metadata` argument on `Success` or `Skip` to save values back into the workflow context.

```python
return Success(
    "Branch created",
    metadata={"branch_name": "feat/search"},
)
```

Later steps can then read that value with `ctx.get("branch_name")`.

## Result types

Step functions return one of these result types:

```python
from titan_cli.engine import Success, Skip, Error, Exit
```

### `Success`

Use when the step completed successfully.

### `Skip`

Use when the step had nothing to do, but the rest of the workflow should continue.

### `Error`

Use when the step failed.

### `Exit`

Use when the whole workflow should stop early in a controlled way.

If cleanup steps still need to run, prefer `Skip` over `Exit`.

## A minimal project step

```python
import subprocess

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def run_tests(ctx: WorkflowContext) -> WorkflowResult:
    result = subprocess.run(["pytest"], capture_output=True, text=True)

    if result.returncode != 0:
        return Error("Tests failed")

    return Success("Tests passed")
```

## A step that passes data forward

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def choose_branch(ctx: WorkflowContext) -> WorkflowResult:
    branch_name = ctx.get("branch_name")
    if not branch_name:
        return Error("Missing branch_name")

    return Success(
        "Branch selected",
        metadata={"selected_branch": branch_name},
    )
```

## When to use a command step instead

Use a command step when:

- the action is a straightforward shell command
- no custom Python branching is needed
- no `ctx.textual` UI interaction is needed
- no reusable Python logic is being introduced

Use a project step when:

- you need Python conditionals or parsing
- you want to pass structured metadata to later steps
- you want to use `ctx.textual`
- the command version would be awkward or unsafe

## Using `ctx.textual`

If you want your step to look and feel like the rest of Titan, use `ctx.textual`.

That lets you:

- show step headers and status
- display formatted text, markdown, panels, and tables
- ask for user input interactively
- show loading indicators during long operations

See [Textual in Steps](textual-steps.md) for the public API.

## Recommended structure for public plugin steps

If you are exposing a public step from a plugin through `get_steps()`, treat it as part of the plugin's public API.

Use a canonical docstring structure:

```python
def my_public_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    One-line summary.

    Requires:
        ctx.github: An initialized GitHubClient.

    Inputs (from ctx.data):
        pr_number (int): Pull request number to inspect.

    Outputs (saved to ctx.data):
        pr_info: The fetched pull request object.

    Returns:
        Success: If the step completes successfully.
        Error: If required context is missing or execution fails.
    """
```

This is especially important for public plugin docs and generated step inventories.

## Common mistakes

- function name does not match `step:` in YAML
- using `Exit` when `Skip` is the right result
- forgetting to return metadata that later steps need
- using a Python step for logic that could just be a simple command step
- writing custom UI output instead of using `ctx.textual`

## What to read next

- [Workflows](workflows.md)
- [Textual in Steps](textual-steps.md)
- [Your First Workflow](../getting-started/your-first-workflow.md)
