# Workflows

Complete guide to creating, extending, and executing workflows in Titan CLI.

---

## Overview

Workflows are YAML files that declare a sequence of steps to execute. Each step calls a plugin step function, a shell command, or another workflow. The engine runs them in order, and each step returns a result that determines whether execution continues.

---

## YAML Structure

```yaml
name: "My Workflow"              # Required. Display name.
description: "What it does"     # Optional. Shown in the UI.

params:                          # Optional. Default values available in all steps via ctx.get()
  draft: false
  assignees: []

hooks:                           # Optional. Hook points available for extension (see Extending Workflows)
  - before_commit
  - after_push

steps:
  - id: my_step                  # Optional. Auto-generated from name if omitted.
    name: "My Step"              # Optional. Display name.
    plugin: github               # Plugin providing the step.
    step: create_pr              # Step function name inside the plugin.
    on_error: continue           # Optional. "fail" (default) or "continue".
    params:                      # Optional. Extra values merged into ctx.data for this step.
      draft: "${draft}"
```

---

## Step Types

A step must define exactly one action type:

### 1. Plugin Step

Calls a registered step function from a plugin.

```yaml
- id: fetch_pr
  name: "Fetch PR Data"
  plugin: github
  step: fetch_pull_request
```

**Special plugin values:**
- `plugin: project` → calls a step from `.titan/steps/` in the current project
- `plugin: user` → calls a step from `~/.titan/steps/`
- `plugin: core` → calls a built-in Titan step (e.g., `ai_code_assistant`)

### 2. Shell Command

Runs a shell command directly.

```yaml
- id: run_lint
  name: "Run Linter"
  command: "ruff check ."
  on_error: continue
```

Add `use_shell: true` if the command requires shell features (pipes, redirects). Avoid for untrusted input.

### 3. Nested Workflow

Calls another workflow as a step. The sub-workflow's result is returned to the parent.

```yaml
- id: commit_first
  name: "Commit Changes"
  workflow: "commit-ai"
```

**Two resolution modes:**

- **Without prefix** (`"commit-ai"`): resolved by source precedence (project → user → plugin). If a project has its own `commit-ai`, that one wins.
- **With prefix** (`"plugin:git/commit-ai"`): targets a specific plugin's workflow directly, bypassing precedence. Use this when you explicitly need the base workflow, not a project override.

```yaml
# Uses whichever commit-ai has highest precedence (e.g. project's extended version)
- workflow: "commit-ai"

# Always uses the base commit-ai from the git plugin, ignoring any project overrides
- workflow: "plugin:git/commit-ai"
```

This is especially useful in hooks where you want to call the base workflow without triggering a project's extended version of it.

---

## Parameters

Workflow-level `params` define defaults that all steps can access via `ctx.get("key")`.

Step-level `params` are merged into `ctx.data` before the step runs, overriding workflow-level values for that step.

**Variable substitution** uses `${key}` syntax to interpolate values from `ctx.data`:

```yaml
params:
  assignees: []

steps:
  - plugin: github
    step: create_issue
    params:
      assignees: "${assignees}"   # Resolved from ctx.data at runtime
      labels: "${labels}"
```

---

## Workflow Sources and Precedence

Titan discovers workflows from four sources. When the same workflow name exists in multiple sources, the **highest-precedence source wins**:

| Priority | Source | Location |
|---|---|---|
| 1 (highest) | Project | `.titan/workflows/*.yaml` |
| 2 | User | `~/.titan/workflows/*.yaml` |
| 3 | System | Bundled with Titan CLI |
| 4 (lowest) | Plugin | Bundled with each plugin |

This means a project workflow can override a plugin workflow of the same name.

---

## Extending Workflows (hooks)

A base workflow declares **hook points** — named injection points in its step sequence. An extending workflow injects additional steps at those points.

### Base workflow defines hooks

```yaml
# plugin:git/commit-ai
name: "Commit with AI"
hooks:
  - before_commit    # ← injection point

steps:
  - plugin: git
    step: get_status

  - hook: before_commit   # ← steps injected here at runtime

  - plugin: git
    step: ai_generate_commit_message

  - plugin: git
    step: create_commit
```

### Extending workflow injects steps into hooks

```yaml
# .titan/workflows/commit-ai.yaml
name: "Commit with AI, Linter and Tests"
extends: "plugin:git/commit-ai"

hooks:
  before_commit:           # ← inject into this hook
    - id: run-lint
      name: "Run Linter"
      plugin: project
      step: ruff_linter
      on_error: continue

    - id: run-tests
      name: "Run Tests"
      plugin: project
      step: test_runner
      on_error: continue
```

**Extends syntax:**
- `"plugin:git/commit-ai"` → a specific plugin's workflow
- `"commit-ai"` → resolved by source precedence (any source)

**Implicit hook:** `after` is always available for appending steps at the very end, even if not declared in the base.

**Params:** overlay params are shallow-merged over base params (overlay wins on conflict).

---

## Step Result Types

Every step function returns one of four result types. The engine checks the type after each step to decide what to do next.

```python
from titan_cli.engine import Success, Error, Skip, Exit
```

### Execution Flow

```
Step returns:
  Success  →  merge metadata into ctx.data  →  continue to next step
  Skip     →  merge metadata into ctx.data  →  continue to next step
  Error    →  check on_error config         →  stop OR continue
  Exit     →  merge metadata into ctx.data  →  STOP entire workflow
```

### Success

Step completed. Workflow continues.

```python
return Success("PR created")
return Success("Branch created", metadata={"branch_name": "feat/my-feature"})
```

The `metadata` dict is automatically merged into `ctx.data` so subsequent steps can access it.

### Skip

Step had nothing to do, but the workflow should continue. Semantically different from `Success`: nothing happened, the step was not applicable.

```python
return Skip("AI not configured")
return Skip("No commits to push")
return Skip("Push cancelled by user", metadata={"push_successful": False})
```

Metadata is also merged into `ctx.data`.

### Error

Step failed. Behavior depends on `on_error` in the YAML:

| `on_error` | Behavior |
|---|---|
| `"fail"` (default) | Workflow stops immediately with an error |
| `"continue"` | Workflow continues to the next step |

```python
return Error("GitHub client not available")
return Error("API rate limit exceeded", code=429)
return Error("Connection failed", exception=exc)
```

### Exit

Stops the **entire workflow immediately**. Not an error — signals "the workflow is no longer needed". The engine converts it to `Success` for any parent workflow.

```python
return Exit("No changes to commit")       # Nothing to do
return Exit("No open PRs found")          # Workflow complete before doing anything
```

---

## Critical: Skip vs Exit

This is the most common mistake when writing steps.

**`Exit` stops ALL remaining steps**, including cleanup steps at the end of the workflow. Use it only when no resources have been allocated that need cleanup.

**`Skip` continues to the next step.** Use it for "nothing to do in this step, but keep going".

### ❌ Wrong — cleanup is skipped

```yaml
steps:
  - step: create_worktree     # Creates a worktree
    on_error: continue
  - step: do_work             # Returns Exit("nothing to do")  ← stops here
    on_error: continue
  - step: cleanup_worktree    # ← NEVER RUNS
```

```python
# do_work step
if not items:
    return Exit("Nothing to do")   # Stops the workflow — cleanup never runs!
```

### ✅ Correct — cleanup always runs

```python
# do_work step
if not items:
    return Skip("Nothing to do")   # Continues to cleanup_worktree
```

### Pattern: Guaranteed Cleanup

To guarantee a step always runs (e.g., cleanup):

1. **Use `on_error: continue`** on all preceding steps that might fail
2. **Use `Skip`** (not `Exit`) in intermediate steps when they have nothing to do
3. **Use `Exit`** only in early steps where no resources have been created yet

```yaml
steps:
  # Early steps: Exit is fine here (nothing created yet)
  - id: select_pr
    plugin: github
    step: select_pr_for_review
    # Exit here stops before any worktree is created — correct

  # After resource creation: all intermediate steps must use Skip, not Exit
  - id: create_worktree
    plugin: github
    step: create_worktree
    on_error: continue        # ← if this fails, still try to cleanup

  - id: do_work
    plugin: github
    step: review_comments     # ← must return Skip (not Exit) for "nothing to do"
    on_error: continue

  - id: push_commits
    plugin: github
    step: push_commits        # ← must return Skip (not Exit) when no commits
    on_error: continue

  - id: cleanup               # ← ALWAYS runs if above use Skip + on_error: continue
    plugin: github
    step: cleanup_worktree
```

---

## Step Function Signature

All step functions follow the same signature:

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip, Exit

def my_step(ctx: WorkflowContext) -> WorkflowResult:
    ...
```

**The function name must exactly match the `step:` field in the YAML.** No `_step` suffix is needed — the function name IS the step name.

```python
# .titan/steps/my_step.py
def my_step(ctx: WorkflowContext) -> WorkflowResult:  # ← function name = step name
    ...
```

```yaml
- plugin: project
  step: my_step               # ← must match exactly
```

### Accessing context data

```python
pr_number = ctx.get("selected_pr_number")  # None if not set
pr_number = ctx.get("selected_pr_number", 0)  # With default
```

---

## Real Examples

### Simple linear workflow

```yaml
# plugins/titan-plugin-github/workflows/create-issue-ai.yaml
name: "Create GitHub Issue (AI-Powered)"
description: "Create a GitHub issue with AI-generated description and auto-categorization"
params:
  assignees: []
steps:
  - plugin: github
    step: prompt_for_issue_body_step

  - plugin: github
    step: ai_suggest_issue_title_and_body

  - plugin: github
    step: prompt_for_self_assign

  - plugin: github
    step: create_issue
    params:
      assignees: "${assignees}"
      labels: "${labels}"
```

### Workflow calling another workflow

```yaml
# plugins/titan-plugin-github/workflows/create-pr-ai.yaml
name: "Create Pull Request with AI"
params:
  draft: false
hooks:
  - before_pr_generation
  - before_push
  - after_pr
steps:
  - workflow: "commit-ai"        # ← calls the commit-ai workflow first

  - plugin: git
    step: get_current_branch

  - hook: before_pr_generation

  - plugin: github
    step: ai_suggest_pr_description

  - hook: before_push

  - plugin: github
    step: create_pr

  - hook: after_pr
```

### Workflow with cleanup guarantee

```yaml
# plugins/titan-plugin-github/workflows/review-pr-comments.yaml
name: "Review PR Comments"
steps:
  - plugin: github
    step: select_pr_for_review
    # Exit here is fine — no resources created yet

  - plugin: github
    step: fetch_pending_comments
    # Exit here is also fine — no worktree yet

  - id: create_worktree
    plugin: github
    step: create_worktree
    on_error: continue           # ← resource created here; continue even on failure

  - plugin: github
    step: review_comments        # ← returns Skip (not Exit) when user exits early
    on_error: continue

  - plugin: github
    step: push_commits           # ← returns Skip (not Exit) when no commits
    on_error: continue

  - plugin: github
    step: send_comment_replies   # ← returns Skip (not Exit) when no replies
    on_error: continue

  - plugin: github
    step: cleanup_worktree       # ← ALWAYS runs
```
