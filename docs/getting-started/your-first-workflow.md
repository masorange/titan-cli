# Your First Workflow

In this tutorial you'll build a custom workflow that runs a linter before every commit. You'll learn how to:

- Write a custom step in Python
- Extend a built-in workflow using hooks
- Run your workflow from Titan

**Prerequisites:** Titan installed and configured in a project with the `git` plugin enabled. If not, see [Installation](installation.md).

---

## The scenario

The built-in `commit-ai` workflow commits your changes with an AI-generated message. You want to run `ruff` (a Python linter) before the commit happens, and skip it gracefully if ruff isn't installed.

You'll inject your linter step into the `before_commit` hook that `commit-ai` already exposes.

---

## Step 1 — Write the step function

Create the file `.titan/steps/run_linter.py` in your project:

```python
import subprocess
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Skip, Error


def run_linter(ctx: WorkflowContext) -> WorkflowResult:
    """Run ruff linter. Skip gracefully if ruff is not installed."""

    # Check ruff is available
    check = subprocess.run(
        ["ruff", "--version"],
        capture_output=True,
    )
    if check.returncode != 0:
        return Skip("ruff not found — skipping lint")

    # Run the linter
    result = subprocess.run(
        ["ruff", "check", "."],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        ctx.textual.text(result.stdout)
        return Error("Linting failed — fix errors before committing")

    return Success("Linting passed")
```

A few things to notice:

- The **function name** (`run_linter`) must match the `step:` field in the YAML exactly.
- We return `Skip` when ruff isn't available — this lets the workflow continue without failing.
- We return `Error` when lint fails — by default this stops the workflow (no commit happens).
- We return `Success` when everything is fine.

---

## Step 2 — Create the workflow file

Create `.titan/workflows/commit-ai.yaml`:

```yaml
name: "Commit with AI + Linter"
description: "Runs ruff before committing with an AI-generated message"
extends: "plugin:git/commit-ai"

hooks:
  before_commit:
    - id: run-lint
      name: "Run Linter"
      plugin: project
      step: run_linter
      on_error: continue   # remove this line if you want lint failures to block the commit
```

What this does:

- `extends: "plugin:git/commit-ai"` — takes the base workflow from the git plugin
- `hooks.before_commit` — injects your step at the `before_commit` injection point
- `plugin: project` — tells Titan to look for `run_linter` in `.titan/steps/`
- `on_error: continue` — even if linting fails, the commit step still runs (remove this to make lint failures block commits)

Because this file is named `commit-ai.yaml` and lives in `.titan/workflows/`, it **overrides** the built-in `commit-ai` workflow for this project. Titan's [precedence rules](../concepts/workflows.md#where-workflows-live) mean project workflows always win.

---

## Step 3 — Run it

```bash
titan
```

Select **Commit with AI + Linter** from the menu. The workflow runs your lint step before generating the commit message.

You'll see each step in the TUI as it executes. If linting fails (and you kept `on_error: continue`), you'll see the lint errors but the commit step will still run. Remove that line to make lint failures stop the workflow.

---

## What's next

You've seen the two core building blocks: a **step** (Python function) and a **workflow** (YAML that sequences steps). From here you can:

- Add more steps to `.titan/steps/` and wire them into workflows
- Create a completely new workflow (no `extends`) for project-specific automation
- Use `ctx.get()` and `metadata` to pass data between steps
- Add AI calls using `ctx.ai` for generated content

Read [Workflow Concepts](../concepts/workflows.md) for the full reference on step types, result types, parameters, and the `Skip` vs `Exit` distinction.

If you want your custom steps to use Titan's TUI API directly, continue with [Your First Textual Step](your-first-textual-step.md).
