---
name: titan-workflows
description: Create and extend Titan CLI workflows with YAML, hooks, and parameter substitution. Use when user says "create workflow", "add hooks", "extend workflow", "workflow YAML", "implement workflow pattern", or asks about "workflow structure", "parameters", or "cleanup pattern".
keywords: workflow, yaml, hooks, extends, parameters, workflow extension, steps
metadata:
  author: MasOrange
  version: 1.0.0
---

# Titan CLI - Complete Workflows Guide

Comprehensive guide to creating, extending, and using workflows in Titan CLI.

---

## What is a Workflow?

A **workflow** in Titan CLI is a declarative YAML file that defines a sequence of steps to accomplish a task. Workflows can:

- Execute plugin steps (Git, GitHub, Jira, custom plugins)
- Run shell commands
- Call other workflows (nested workflows)
- Request user input
- Use AI to generate content
- Define hooks for extensibility

Workflows are designed to be **reusable**, **composable**, and **extensible**.

---

## Workflow YAML Structure

### Basic Structure

```yaml
name: "Workflow Name"
description: "What this workflow does"

params:
  param_name: "default_value"
  another_param: 123

steps:
  - id: step1
    name: "Step Description"
    plugin: plugin_name
    step: step_function_name

  - id: step2
    name: "Another Step"
    plugin: another_plugin
    step: another_step
```

### Complete Field Reference

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | Yes | string | Display name for the workflow |
| `description` | No | string | Human-readable description |
| `params` | No | dict | Default parameter values |
| `hooks` | No | list | Named hook points for extension |
| `steps` | Yes | list | Sequence of steps to execute |
| `extends` | No | string | Base workflow to extend |

---

## Step Types

### 1. Plugin Steps

Execute a function from a plugin:

```yaml
- id: commit
  name: "Create Commit"
  plugin: git
  step: commit_step
  params:
    message: "${commit_message}"
```

**Fields:**
- `id`: Unique identifier for this step
- `name`: Display name
- `plugin`: Plugin name (`git`, `github`, `jira`, `project`, etc.)
- `step`: Function name from the plugin
- `params`: Parameters passed to the step
- `on_error`: Error handling (`fail` | `continue`) - default: `fail`

### 2. Shell Commands

Execute shell commands directly:

```yaml
- id: build
  name: "Build Project"
  shell: "npm run build"
```

### 3. Nested Workflows

Call another workflow as a step:

```yaml
- id: prepare
  name: "Run Preparation Workflow"
  workflow: "plugin:git/prepare-branch"
```

**Workflow Reference Format:**
- `plugin:plugin_name/workflow-name` - Workflow from a plugin
- `workflow-name` - Workflow from `.titan/workflows/`

### 4. Hook Placeholders

Define extension points:

```yaml
- hook: before_commit
```

Hooks are placeholders that extending workflows can fill with custom steps.

---

## Parameters and Substitution

### Parameter Declaration

Declare default parameters at the workflow level:

```yaml
params:
  environment: "staging"
  notify: true
  branch_name: "develop"
```

### Parameter Substitution

Use `${key}` syntax to reference parameters in step configurations:

```yaml
steps:
  - id: deploy
    plugin: project
    step: deploy_step
    params:
      env: "${environment}"
      notify_slack: "${notify}"
```

### Parameter Sources (Override Precedence)

Parameters are resolved with the following precedence (highest to lowest):

1. **Runtime arguments** (when workflow is executed)
2. **Step-level params** (in the YAML step definition)
3. **Workflow-level params** (in the YAML `params:` section)
4. **Extended workflow params** (from the base workflow)

### Accessing Parameters in Steps

Inside step functions, access parameters using `ctx.get()`:

```python
def my_step(ctx: WorkflowContext) -> WorkflowResult:
    environment = ctx.get("environment", "staging")
    notify = ctx.get("notify", False)
```

---

## Workflow Sources and Discovery

Titan CLI searches for workflows in multiple locations:

### 1. Project Workflows

**Location**: `.titan/workflows/` (at the git root)

These are project-specific workflows. When inside a git repository, Titan resolves the project root using `git rev-parse --show-toplevel`, so you can run `titan` from any subdirectory.

```bash
.titan/workflows/
├── deploy.yaml
├── commit-ai.yaml
└── custom-workflow.yaml
```

### 2. Plugin Workflows

**Location**: `plugins/titan-plugin-{name}/workflows/`

Official plugins (Git, GitHub, Jira) provide built-in workflows:

```
plugins/titan-plugin-git/workflows/
├── commit-ai.yaml
└── prepare-branch.yaml

plugins/titan-plugin-github/workflows/
├── create-pr.yaml
└── review-pr.yaml
```

### 3. Discovery Order

When you run `titan`, workflows are discovered in this order:

1. `.titan/workflows/` (project workflows)
2. All enabled plugin workflows (from `plugins/`)
3. Extended workflows (via `extends:`)

---

## Extending Workflows with Hooks

### Base Workflow (in Plugin)

Define hook points where extending workflows can inject steps:

**plugins/titan-plugin-git/workflows/commit-ai.yaml**:
```yaml
name: "Commit with AI"
description: "Create commit with AI-generated message"

hooks:
  - before_commit
  - after_commit

steps:
  - id: stage_changes
    name: "Stage Changes"
    plugin: git
    step: stage_changes_step

  - hook: before_commit

  - id: generate_message
    name: "Generate Commit Message"
    plugin: git
    step: generate_commit_message_ai

  - id: commit
    name: "Create Commit"
    plugin: git
    step: commit_step

  - hook: after_commit
```

### Extended Workflow (in Project)

Implement hooks with custom steps:

**.titan/workflows/commit-ai.yaml**:
```yaml
name: "Commit with AI and Linting"
description: "Extended commit workflow with pre-commit checks"
extends: "plugin:git/commit-ai"

hooks:
  before_commit:
    - id: format_code
      name: "Format Code"
      plugin: project
      step: run_black_formatter
      on_error: continue

    - id: run_linter
      name: "Run Linter"
      plugin: project
      step: run_pylint
      on_error: fail

  after_commit:
    - id: notify_team
      name: "Notify Team"
      plugin: project
      step: send_slack_notification
      on_error: continue
```

### How It Works

1. The base workflow declares hook points: `hooks: [before_commit, after_commit]`
2. The extended workflow uses `extends: "plugin:git/commit-ai"`
3. The extended workflow fills hooks with custom steps
4. At runtime, Titan merges the workflows:
   - Base workflow steps run in order
   - When a `- hook: before_commit` is encountered, the steps from `hooks.before_commit` are injected
   - Execution continues with the next base step

---

## Result Types and Execution Flow

Every step returns a `WorkflowResult`, which determines execution flow.

### Result Types

| Result Type | Description | Effect on Workflow |
|-------------|-------------|-------------------|
| `Success` | Step completed successfully | Continue to next step |
| `Skip` | Step had nothing to do | Continue to next step (no error) |
| `Error` | Step failed | Stop workflow (unless `on_error: continue`) |
| `Exit` | User requested early exit | Stop workflow immediately |

### Skip vs Exit - Critical Difference

#### Skip
- **Purpose**: Step had no work to do (e.g., no Python files to format)
- **Effect**: Workflow continues normally
- **Use when**: Nothing to process, but not an error

```python
if not python_files:
    return Skip("No Python files to format")
```

#### Exit
- **Purpose**: User cancelled or workflow should stop early
- **Effect**: Workflow stops immediately (cleanup steps may not run)
- **Use when**: User explicitly cancels, or early termination is intentional

```python
if not user_confirmed:
    return Exit("User cancelled deployment")
```

### Error Handling with `on_error`

Control how step failures affect workflow execution:

```yaml
steps:
  - id: critical_step
    plugin: project
    step: deploy_step
    on_error: fail  # Default - stop workflow on error

  - id: optional_step
    plugin: project
    step: send_notification
    on_error: continue  # Continue even if this fails
```

---

## Guaranteed Cleanup Pattern

**Problem**: When a workflow creates resources (e.g., worktrees, temp files), cleanup must run even if later steps fail or user exits.

**Solution**: Use `Skip` (not `Exit`) + `on_error: continue` for all steps after resource creation.

### Example: Worktree Workflow

```yaml
steps:
  # Early steps: Exit is OK (no resources yet)
  - id: select_issue
    plugin: jira
    step: select_issue_step
    # If user cancels here → Exit is fine

  # Resource creation point
  - id: create_worktree
    plugin: git
    step: create_worktree_step
    on_error: continue  # ← Must continue to cleanup

  # Work steps: Use Skip if nothing to do
  - id: create_branch
    plugin: git
    step: create_branch_step
    on_error: continue  # ← Returns Skip if branch exists

  - id: do_work
    plugin: project
    step: work_step
    on_error: continue  # ← Returns Skip if cancelled

  # Cleanup: ALWAYS runs
  - id: cleanup_worktree
    plugin: git
    step: cleanup_worktree_step
```

**Rules:**
1. Before resource creation: `Exit` is OK
2. After resource creation: Use `Skip` (not `Exit`)
3. All steps after creation: `on_error: continue`
4. Cleanup step: Always runs, regardless of previous failures

---

## Practical Workflow Examples

### Example 1: Simple Deployment Workflow

**.titan/workflows/deploy.yaml**:
```yaml
name: "Deploy to Environment"
description: "Deploy application to specified environment"

params:
  environment: "staging"
  skip_tests: false

steps:
  - id: validate
    name: "Validate Environment"
    plugin: project
    step: validate_environment
    params:
      env: "${environment}"

  - id: run_tests
    name: "Run Tests"
    plugin: project
    step: run_tests
    params:
      skip: "${skip_tests}"
    on_error: fail

  - id: build
    name: "Build Application"
    shell: "npm run build"

  - id: deploy
    name: "Deploy to ${environment}"
    plugin: project
    step: deploy_step
    params:
      target: "${environment}"

  - id: verify
    name: "Verify Deployment"
    plugin: project
    step: verify_deployment
    on_error: continue
```

### Example 2: Complex Workflow with Hooks

**Base Workflow (plugin):**
```yaml
name: "Release Workflow"
description: "Create a new release with customizable hooks"

hooks:
  - before_build
  - after_build
  - before_release
  - after_release

params:
  version: ""
  publish: true

steps:
  - id: validate_version
    plugin: project
    step: validate_version
    params:
      version: "${version}"

  - hook: before_build

  - id: build
    plugin: project
    step: build_release
    on_error: fail

  - hook: after_build

  - id: run_tests
    plugin: project
    step: run_integration_tests
    on_error: fail

  - hook: before_release

  - id: create_release
    plugin: github
    step: create_release_step
    params:
      version: "${version}"
      publish: "${publish}"

  - hook: after_release
```

**Extended Workflow (project):**
```yaml
name: "Production Release"
description: "Extended release with changelog and notifications"
extends: "plugin:project/release"

params:
  version: ""
  publish: true
  notify_channel: "#releases"

hooks:
  before_build:
    - id: update_changelog
      plugin: project
      step: update_changelog
      on_error: fail

  after_build:
    - id: create_artifacts
      plugin: project
      step: create_release_artifacts
      on_error: fail

  before_release:
    - id: require_approval
      plugin: project
      step: require_manager_approval
      on_error: fail

  after_release:
    - id: notify_slack
      plugin: project
      step: notify_slack
      params:
        channel: "${notify_channel}"
      on_error: continue

    - id: update_docs
      plugin: project
      step: update_documentation
      on_error: continue
```

### Example 3: Multi-Step Workflow with Nested Calls

```yaml
name: "Complete CI/CD Pipeline"
description: "Full pipeline with tests, build, and deploy"

params:
  environment: "production"

steps:
  # Call preparation workflow
  - id: prepare
    name: "Prepare Environment"
    workflow: "plugin:project/prepare-env"

  # Run tests
  - id: test
    name: "Run Test Suite"
    workflow: "plugin:project/run-tests"

  # Build
  - id: build
    name: "Build Docker Image"
    plugin: project
    step: build_docker_image
    on_error: fail

  # Deploy
  - id: deploy
    name: "Deploy to ${environment}"
    plugin: project
    step: deploy_to_kubernetes
    params:
      env: "${environment}"
    on_error: fail

  # Verify
  - id: verify
    name: "Run Smoke Tests"
    workflow: "plugin:project/smoke-tests"
    on_error: continue

  # Notify
  - id: notify
    name: "Send Notification"
    plugin: project
    step: send_slack_notification
    on_error: continue
```

### Example 4: Conditional Execution

```yaml
name: "Conditional Deployment"
description: "Deploy only if tests pass and environment is valid"

params:
  environment: "staging"
  run_tests: true

steps:
  - id: validate_env
    name: "Validate Environment"
    plugin: project
    step: validate_environment
    params:
      env: "${environment}"

  # Conditional test execution
  - id: run_tests
    name: "Run Tests (optional)"
    plugin: project
    step: run_tests
    params:
      enabled: "${run_tests}"
    # Step returns Skip if run_tests=false

  # Only deploys if previous steps succeed
  - id: deploy
    name: "Deploy to ${environment}"
    plugin: project
    step: deploy_step
    params:
      target: "${environment}"
    on_error: fail
```

---

## Creating Custom Project Steps

For project-specific steps (not official plugins), create steps in `.titan/steps/`.

### Step File Location

**.titan/steps/my_custom_step.py**:

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip

def my_custom_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Custom step for project-specific logic.

    User steps can use ANY pattern - the only requirement is:
    WorkflowContext → WorkflowResult
    """
    ctx.textual.begin_step("My Custom Step")

    # Get parameters
    value = ctx.get("some_param", "default")

    if not value:
        ctx.textual.warning_text("No value provided")
        ctx.textual.end_step("success")
        return Skip("Nothing to do")

    # Do something
    ctx.textual.info_text(f"Processing: {value}")

    # Your logic here...

    ctx.textual.success_text("Done!")
    ctx.textual.end_step("success")
    return Success("Completed", metadata={"result": value})
```

**CRITICAL**: The function name MUST match the `step:` field in the workflow YAML exactly.

### Using Custom Steps in Workflows

**.titan/workflows/custom-workflow.yaml**:
```yaml
name: "My Custom Workflow"

params:
  some_param: "default_value"

steps:
  - id: my_step
    name: "My Custom Step"
    plugin: project  # ← Uses .titan/steps/
    step: my_custom_step
    params:
      some_param: "${some_param}"
```

---

## Best Practices

### 1. Workflow Design

- **Single Responsibility**: Each workflow should do one thing well
- **Composability**: Break complex workflows into smaller, reusable workflows
- **Clear Names**: Use descriptive names for workflows and steps
- **Default Parameters**: Provide sensible defaults for all parameters

### 2. Error Handling

- **Critical Steps**: Use `on_error: fail` (default)
- **Cleanup Steps**: Use `on_error: continue`
- **Optional Steps**: Use `on_error: continue` for notifications, logging, etc.

### 3. Parameter Management

- **Document Parameters**: Add descriptions in workflow `description` field
- **Validation**: Validate parameters early in the workflow
- **Defaults**: Always provide default values for parameters

### 4. Hooks

- **Extensibility**: Define hooks at natural extension points
- **Naming**: Use clear hook names (`before_deploy`, `after_tests`)
- **Documentation**: Document expected hook behavior

### 5. Skip vs Exit

- **Skip**: Use when step has nothing to do (not an error)
- **Exit**: Use ONLY when user explicitly cancels
- **After Resources**: Use Skip (not Exit) after creating resources

---

## Common Patterns

### Pattern: Pre/Post Hooks

```yaml
name: "Action with Hooks"

hooks:
  - before_action
  - after_action

steps:
  - id: validate
    plugin: project
    step: validate_step

  - hook: before_action

  - id: main_action
    plugin: project
    step: main_step
    on_error: fail

  - hook: after_action
```

### Pattern: Guaranteed Cleanup

```yaml
steps:
  # Early validation (Exit OK)
  - id: select_item
    plugin: project
    step: select_item_step

  # Resource creation (continue on error)
  - id: create_resource
    plugin: project
    step: create_resource_step
    on_error: continue

  # Work (continue on error, Skip if cancelled)
  - id: do_work
    plugin: project
    step: work_step
    on_error: continue

  # Cleanup (ALWAYS runs)
  - id: cleanup
    plugin: project
    step: cleanup_step
```

### Pattern: Nested Workflow Call

```yaml
steps:
  # Call prerequisite workflow
  - id: prerequisite
    workflow: "plugin:project/prepare"

  # Continue with main work
  - id: main_work
    plugin: project
    step: main_step
```

### Pattern: Conditional Execution in Step

```python
def conditional_step(ctx: WorkflowContext) -> WorkflowResult:
    """Step that may skip based on conditions."""
    ctx.textual.begin_step("Conditional Step")

    feature_enabled = ctx.get("feature_enabled", False)

    if not feature_enabled:
        ctx.textual.info_text("Feature not enabled, skipping")
        ctx.textual.end_step("success")
        return Skip("Feature disabled")

    # Continue with work...
    ctx.textual.end_step("success")
    return Success("Completed")
```

---

## Troubleshooting

### Common Issues

#### Issue: "Step function not found"

**Cause**: Function name in Python file doesn't match `step:` field in YAML

**Solution**: Ensure exact match:
```python
# File: .titan/steps/my_step.py
def my_step(ctx: WorkflowContext) -> WorkflowResult:  # ← Exact match
    ...
```
```yaml
# YAML
step: my_step  # ← Must match function name
```

#### Issue: "Workflow not found"

**Cause**: Workflow file not in search path or incorrect reference format

**Solution**:
- Check `.titan/workflows/` for project workflows
- Use `plugin:plugin_name/workflow-name` for plugin workflows
- Ensure plugin is enabled in `.titan/config.toml`

#### Issue: "Parameters not substituted"

**Cause**: Missing `${}` syntax or parameter not defined

**Solution**:
```yaml
params:
  my_param: "value"  # ← Declare parameter

steps:
  - params:
      key: "${my_param}"  # ← Use ${} syntax
```

#### Issue: "Cleanup step not running"

**Cause**: Using `Exit` instead of `Skip`, or missing `on_error: continue`

**Solution**:
- Use `Skip` (not `Exit`) after resource creation
- Add `on_error: continue` to all steps after resource creation

---

## Summary

Workflows in Titan CLI are:

- **Declarative**: Define what to do, not how (YAML)
- **Extensible**: Use hooks to customize behavior
- **Composable**: Call workflows from workflows
- **Type-safe**: Steps return strongly-typed results
- **User-friendly**: Clear success/error handling

**Key Concepts:**
1. YAML structure: `name`, `params`, `hooks`, `steps`
2. Step types: plugin steps, shell commands, nested workflows, hooks
3. Parameters: `${key}` substitution with precedence rules
4. Result types: `Success`, `Skip`, `Error`, `Exit`
5. Error handling: `on_error: fail|continue`
6. Cleanup pattern: `Skip` + `on_error: continue`
7. Hooks: Define extension points, implement in extending workflows

For more details on creating plugin steps, see the [Textual Workflow Steps Guide](../../.claude/docs/textual.md) and [Plugin Architecture Guide](../../.claude/docs/plugin-architecture.md).

---

## Quick Examples

### Example 1: User asks "Create a deployment workflow"

**User says**: "Create a deployment workflow that runs tests first"

**What Claude does**:
1. Creates `.titan/workflows/deploy.yaml`
2. Adds test step before deployment
3. Includes error handling with `on_error: fail`
4. Adds verification step after deployment

**Result**: Complete workflow with test → build → deploy → verify steps

### Example 2: User asks "Extend the commit workflow with linting"

**User says**: "I want to run linting before commits"

**What Claude does**:
1. Creates `.titan/workflows/commit-ai.yaml` extending base workflow
2. Implements `before_commit` hook
3. Adds linting step with `on_error: fail`
4. Preserves base workflow behavior

**Result**: Extended workflow that runs linter before committing

### Example 3: User asks "How do I guarantee cleanup?"

**User says**: "My workflow creates a worktree but cleanup doesn't always run"

**What Claude does**:
1. Explains Skip vs Exit pattern
2. Shows how to use `on_error: continue` after resource creation
3. Provides complete example with guaranteed cleanup

**Result**: Workflow that always cleans up resources

---

## Troubleshooting

### Issue: "Workflow not found"
**User says**: "When I run the workflow it says not found"

**Cause**: Workflow file not in correct location or wrong reference format

**Solution**:
- Project workflows must be in `.titan/workflows/` at git root
- Use `plugin:plugin_name/workflow-name` for plugin workflows
- Check plugin is enabled in `.titan/config.toml`

### Issue: "Step function not found"
**User says**: "Error: step function 'my_step' not found"

**Cause**: Function name in Python doesn't match `step:` field in YAML

**Solution**:
```python
# File: .titan/steps/my_step.py
def my_step(ctx):  # ← Function name must match exactly
    ...
```
```yaml
# YAML
step: my_step  # ← Must match function name
```

### Issue: "Cleanup doesn't run after error"
**User says**: "My cleanup step doesn't run when earlier steps fail"

**Cause**: Missing `on_error: continue` or using `Exit` instead of `Skip`

**Solution**:
- Add `on_error: continue` to all steps after resource creation
- Use `Skip` (not `Exit`) after creating resources
- See "Guaranteed Cleanup Pattern" section above

---

**Version**: 1.0.0
**Last updated**: 2026-03-31
