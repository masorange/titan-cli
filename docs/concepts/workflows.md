# Workflows

A workflow is a sequence of steps that Titan executes in order. You define workflows in YAML files and run them from the Titan TUI or CLI.

Workflows are the core of Titan. Everything you do — committing, opening a PR, analyzing a Jira ticket — is a workflow.

---

## A minimal example

```yaml
name: "Run tests and commit"
description: "Runs the test suite, then commits if tests pass"

steps:
  - id: run-tests
    name: "Run Tests"
    command: "pytest"

  - id: commit
    name: "Commit"
    plugin: git
    step: create_commit
```

This workflow runs `pytest` as a shell command, then calls the `create_commit` step from the `git` plugin.

---

## YAML structure

```yaml
name: "My Workflow"           # Required. Shown in the menu.
description: "What it does"  # Optional. Shown below the name.

params:                       # Optional. Default values accessible in all steps.
  draft: false
  assignees: []

hooks:                        # Optional. Named injection points for extending this workflow.
  - before_commit
  - after_push

steps:
  - id: my_step              # Optional. Auto-generated if omitted.
    name: "My Step"          # Optional. Shown in the TUI while running.
    plugin: github           # Which plugin provides this step.
    step: create_pr          # The step function name inside that plugin.
    on_error: continue       # Optional. "fail" (default) or "continue".
    params:                  # Optional. Extra values passed to this step.
      draft: "${draft}"
```

---

## Step types

Every step must define exactly one action.

### Plugin step

Calls a registered step function from a plugin.

```yaml
- plugin: github
  step: create_pr
```

**Special plugin values:**

| Value | Meaning |
|-------|---------|
| `plugin: git` | Built-in Git plugin |
| `plugin: github` | Built-in GitHub plugin |
| `plugin: jira` | Built-in Jira plugin |
| `plugin: project` | A step in `.titan/steps/` of the current project |
| `plugin: user` | A step in `~/.titan/steps/` (personal steps) |
| `plugin: core` | A built-in Titan step (e.g. `ai_code_assistant`) |

### Shell command

Runs a shell command directly.

```yaml
- id: lint
  name: "Run Linter"
  command: "ruff check ."
  on_error: continue    # keep going even if lint fails
```

Add `use_shell: true` if your command needs pipes or redirects (`cmd1 | cmd2`).

### Nested workflow

Calls another workflow as a step.

```yaml
- id: commit-first
  workflow: "commit-ai"
```

**Resolution modes:**

```yaml
# Resolved by precedence (project overrides win):
- workflow: "commit-ai"

# Always the base workflow from the git plugin, ignoring any project override:
- workflow: "plugin:git/commit-ai"
```

Use the `plugin:` prefix when you explicitly need the base workflow, not a project's customized version.

---

## Parameters

Workflow-level `params` define defaults accessible in all steps via `ctx.get("key")`.

Step-level `params` are merged into the context before that step runs.

Use `${key}` to interpolate values from the context at runtime:

```yaml
params:
  assignees: []

steps:
  - plugin: github
    step: create_issue
    params:
      assignees: "${assignees}"   # resolved from ctx.data at runtime
      labels: "${labels}"
```

---

## Where workflows live

Titan discovers workflows from four sources. When the same workflow name exists in multiple sources, **higher priority wins**:

| Priority | Source | Location |
|----------|--------|----------|
| 1 (highest) | Project | `.titan/workflows/*.yaml` |
| 2 | User | `~/.titan/workflows/*.yaml` |
| 3 | System | Bundled with Titan CLI |
| 4 (lowest) | Plugin | Bundled with each plugin |

This means you can override any built-in workflow by creating a file with the same name in `.titan/workflows/`.

---

## Extending workflows

Instead of replacing a workflow entirely, you can **extend** it — injecting extra steps at named hook points.

### How it works

A base workflow declares hooks (named injection points):

```yaml
# Built into the git plugin
name: "Commit with AI"
hooks:
  - before_commit      # ← injection point

steps:
  - plugin: git
    step: get_status

  - hook: before_commit  # ← your steps get injected here

  - plugin: git
    step: ai_generate_commit_message

  - plugin: git
    step: create_commit
```

Your project extends it by filling those hooks:

```yaml
# .titan/workflows/commit-ai.yaml
name: "Commit with AI + Linter"
extends: "plugin:git/commit-ai"

hooks:
  before_commit:
    - id: run-lint
      name: "Run Linter"
      command: "ruff check ."
      on_error: continue
```

Now when you run `commit-ai`, Titan runs the base workflow with your lint step injected before the commit.

**Notes:**

- `extends: "plugin:git/commit-ai"` targets the base plugin workflow directly
- `extends: "commit-ai"` resolves by precedence — could be another project override
- The `after` hook is always available, even if not declared in the base, for appending steps at the very end
- Params are shallow-merged: your params override base params on conflict

---

## Step results

Every step function returns one of four result types. The engine checks the result after each step to decide what to do next.

```
Step returns:
  Success  →  merge metadata into ctx.data  →  continue to next step
  Skip     →  merge metadata into ctx.data  →  continue to next step
  Error    →  check on_error config         →  stop OR continue
  Exit     →  merge metadata into ctx.data  →  STOP entire workflow
```

### `Success`

The step completed. Workflow continues.

```python
return Success("PR created")
return Success("Branch created", metadata={"branch_name": "feat/my-feature"})
```

`metadata` is merged into `ctx.data` so subsequent steps can read it.

### `Skip`

The step had nothing to do, but the workflow should continue. Semantically different from `Success`: nothing happened, the step was not applicable.

```python
return Skip("AI not configured")
return Skip("No commits to push")
```

### `Error`

The step failed. Behavior depends on `on_error` in the YAML:

| `on_error` | Behavior |
|------------|----------|
| `"fail"` (default) | Workflow stops immediately |
| `"continue"` | Workflow continues to the next step |

```python
return Error("GitHub client not available")
return Error("API rate limit exceeded")
```

### `Exit`

Stops the **entire workflow immediately**. Not an error — signals "the workflow is no longer needed". The engine converts it to `Success` for any parent workflow.

```python
return Exit("No changes to commit")   # Nothing to do — stop cleanly
return Exit("No open PRs found")
```

---

## Critical: `Skip` vs `Exit`

This is the most common mistake when writing workflow steps.

**`Exit` stops ALL remaining steps**, including cleanup steps. Use it only before any resources have been allocated.

**`Skip` continues to the next step.** Use it for "nothing to do here, keep going".

### The wrong way

```yaml
steps:
  - step: create_worktree    # Creates a worktree on disk
  - step: do_work            # Returns Exit("nothing to do") ← workflow stops here
  - step: cleanup_worktree   # ← NEVER RUNS. Worktree left on disk.
```

### The right way

```python
# In do_work step
if not items:
    return Skip("Nothing to do")   # Continues to cleanup_worktree
```

### Guaranteed cleanup pattern

To ensure a step always runs (cleanup, teardown):

1. Use `on_error: continue` on all steps after resource creation
2. Use `Skip` (not `Exit`) in intermediate steps when they have nothing to do
3. Use `Exit` only in early steps where no resources have been created yet

```yaml
steps:
  # Early steps: Exit is fine here — nothing created yet
  - plugin: github
    step: select_pr_for_review

  # After this, a worktree exists on disk — must guarantee cleanup
  - id: create_worktree
    plugin: github
    step: create_worktree
    on_error: continue          # even if this fails, try to cleanup

  - plugin: github
    step: do_work               # returns Skip (not Exit) when nothing to do
    on_error: continue

  - plugin: github
    step: cleanup_worktree      # ALWAYS runs thanks to Skip + on_error: continue
```

---

## Writing a step function

Step functions are Python functions that follow this signature:

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip, Exit

def my_step(ctx: WorkflowContext) -> WorkflowResult:
    value = ctx.get("some_key")          # read from context
    value = ctx.get("some_key", "default")  # with default

    # ... do work ...

    return Success("Done", metadata={"result": value})
```

**The function name must exactly match the `step:` field in the YAML.**

```python
# .titan/steps/run_linter.py
def run_linter(ctx: WorkflowContext) -> WorkflowResult:  # ← function name = step name
    ...
```

```yaml
- plugin: project
  step: run_linter   # ← must match exactly
```

For a hands-on example, see [Your First Workflow](../getting-started/your-first-workflow.md).
