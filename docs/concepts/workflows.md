# Workflows

Titan workflows are YAML files that automate a sequence of actions: plugin steps, project steps, shell commands, and even other workflows.

This page explains the workflow model from a user point of view: what kinds of workflows you can create, what kinds of steps they can contain, and how they fit together.

## What a workflow is

A workflow is a sequence of steps executed in order.

Typical examples:

- run checks, then create a commit
- gather input, generate content with AI, then create a GitHub issue
- create a worktree, do review work, then clean it up

A minimal workflow looks like this:

```yaml
name: "Run tests and commit"
description: "Run tests, then create a commit"

steps:
  - id: run-tests
    name: "Run Tests"
    command: "pytest"

  - id: create-commit
    name: "Create Commit"
    plugin: git
    step: create_commit
```

## Workflow types

There are several ways to use workflows in Titan.

### 1. New workflow from scratch

Create a brand new YAML file and define the full sequence yourself.

Use this when you want a custom automation that does not naturally extend an existing workflow.

### 2. Extended workflow

Extend another workflow and inject your own steps into its hooks.

Use this when Titan or a plugin already gives you most of what you need.

```yaml
name: "Commit with AI + Linter"
extends: "plugin:git/commit-ai"

hooks:
  before_commit:
    - id: run-lint
      name: "Run Linter"
      plugin: project
      step: run_linter
```

### 3. Nested workflow

Call another workflow as a step.

Use this when you want to compose larger flows from smaller reusable ones.

```yaml
steps:
  - id: commit-first
    workflow: "commit-ai"
```

## Where workflows live

Titan discovers workflows from four sources.

| Priority | Source | Location | Typical use |
|----------|--------|----------|-------------|
| 1 | Project | `.titan/workflows/*.yaml` | Project-specific automation shared with the repo |
| 2 | User | `~/.titan/workflows/*.yaml` | Personal reusable workflows across projects |
| 3 | System | Bundled with Titan CLI | Built-in core workflows |
| 4 | Plugin | Bundled with each plugin | Workflows shipped by plugins |

Higher priority wins when two workflows have the same name.

That means a project workflow can override a plugin workflow simply by using the same filename and workflow name.

## Workflow structure

```yaml
name: "My Workflow"
description: "What it does"

params:
  draft: false
  assignees: []

hooks:
  - before_commit
  - after_push

steps:
  - id: my_step
    name: "My Step"
    plugin: github
    step: create_pr
    on_error: continue
    params:
      draft: "${draft}"
```

Main fields:

- `name`: human-friendly label shown in Titan
- `description`: optional explanation
- `params`: default values available through `ctx.get(...)`
- `hooks`: named extension points other workflows can fill
- `steps`: the ordered actions to run

## Step types

Every workflow step must define exactly one action type.

### Plugin step

Calls a public step exposed by a plugin.

```yaml
- plugin: github
  step: create_pr
```

Use this when the capability already exists in a plugin and you want to reuse it.

### Project step

Calls a Python step from `.titan/steps/`.

```yaml
- plugin: project
  step: run_linter
```

Use this when the logic is specific to this repository.

### User step

Calls a Python step from `~/.titan/steps/`.

```yaml
- plugin: user
  step: my_global_helper
```

Use this for personal reusable automations across many projects.

### Core step

Calls a built-in Titan step.

```yaml
- plugin: core
  step: ai_code_assistant
```

Use this when Titan already provides the generic behavior directly.

### Command step

Runs a shell command.

```yaml
- id: lint
  name: "Run Linter"
  command: "ruff check ."
```

Use this when the action is simple and you do not need custom Python logic or UI behavior.

### Nested workflow step

Runs another workflow.

```yaml
- workflow: "commit-ai"
```

Use this when you want to compose workflows instead of repeating steps.

## Choosing the right step type

| Use case | Best fit |
|----------|----------|
| Reuse a built-in plugin capability | Plugin step |
| Add project-specific Python logic | Project step |
| Reuse a personal helper across projects | User step |
| Use a Titan-provided generic helper | Core step |
| Run a straightforward command | Command step |
| Compose existing flows | Nested workflow |

For a full guide to writing Python steps, see [Workflow Steps](workflow-steps.md).

## Parameters and variable substitution

Workflow-level `params` define defaults that all steps can read with `ctx.get(...)`.

Step-level `params` are merged into the context before that step runs.

Use `${key}` to interpolate values from the current context:

```yaml
params:
  assignees: []

steps:
  - plugin: github
    step: create_issue
    params:
      assignees: "${assignees}"
      labels: "${labels}"
```

## Extending workflows with hooks

Hooks let you customize an existing workflow without copying the whole thing.

Base workflow:

```yaml
name: "Commit with AI"
hooks:
  - before_commit

steps:
  - plugin: git
    step: get_status

  - hook: before_commit

  - plugin: git
    step: ai_generate_commit_message

  - plugin: git
    step: create_commit
```

Project extension:

```yaml
name: "Commit with AI + Checks"
extends: "plugin:git/commit-ai"

hooks:
  before_commit:
    - id: run-lint
      name: "Run Linter"
      plugin: project
      step: run_linter

    - id: run-tests
      name: "Run Tests"
      command: "pytest"
```

Notes:

- `extends: "plugin:git/commit-ai"` targets the base plugin workflow directly
- `extends: "commit-ai"` resolves by precedence and may pick a project override
- `after` is always available as an implicit hook at the end of a workflow

## Workflow resolution for nested workflows

There are two useful forms when calling another workflow:

```yaml
# Use the highest-precedence workflow named commit-ai
- workflow: "commit-ai"

# Always call the base workflow shipped by the git plugin
- workflow: "plugin:git/commit-ai"
```

Use the prefixed form when you explicitly want the base plugin workflow and do not want a project override.

## Step result types

Every step returns one of four result types.

```python
from titan_cli.engine import Success, Skip, Error, Exit
```

| Result | Meaning |
|--------|---------|
| `Success` | Step completed and workflow continues |
| `Skip` | Step had nothing to do and workflow continues |
| `Error` | Step failed; workflow stops unless `on_error: continue` |
| `Exit` | Stop the whole workflow early in a controlled way |

### `Success`

```python
return Success("Done")
return Success("Created branch", metadata={"branch_name": "feat/search"})
```

`metadata` is merged into `ctx.data` so later steps can reuse it.

### `Skip`

Use `Skip` when the step is not applicable, but later steps should still run.

```python
return Skip("AI not configured")
return Skip("No labels to select")
```

### `Error`

Use `Error` when the step actually failed.

```python
return Error("GitHub client not available")
```

In YAML, `on_error` controls whether the workflow stops or continues:

```yaml
- plugin: project
  step: run_linter
  on_error: continue
```

### `Exit`

Use `Exit` when the whole workflow should stop cleanly because it is no longer needed.

```python
return Exit("No changes to commit")
```

## Critical: `Skip` vs `Exit`

This is the most common mistake when writing workflow steps.

- `Skip` means: this step has nothing to do, continue the workflow
- `Exit` means: stop the whole workflow now

If resources have already been created, prefer `Skip` so cleanup steps can still run.

Wrong:

```yaml
steps:
  - step: create_worktree
  - step: do_work
  - step: cleanup_worktree
```

If `do_work` returns `Exit`, `cleanup_worktree` never runs.

Safer pattern:

```yaml
steps:
  - step: create_worktree
    on_error: continue

  - step: do_work
    on_error: continue

  - step: cleanup_worktree
```

And inside `do_work`, return `Skip` instead of `Exit` when there is simply nothing to do.

## What to read next

- [Workflow Steps](workflow-steps.md): how to write Python step functions
- [Textual in Steps](textual-steps.md): how to use `ctx.textual` for consistent TUI output
- [Your First Workflow](../getting-started/your-first-workflow.md): hands-on tutorial
