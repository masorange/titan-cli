# Textual Workflow Steps Development Guide

This guide explains how to create workflow steps using the Textual TUI framework.

## Table of Contents

- [Basic Structure](#basic-structure)
- [Common Pitfalls](#common-pitfalls)
- [TextualComponents API](#textualcomponents-api)
- [Available Widgets](#available-widgets)
- [Complete Examples](#complete-examples)
- [Reference Files](#reference-files)

---

## Basic Structure

### Step Template

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ui.tui.widgets import Panel

def my_step(ctx: WorkflowContext) -> WorkflowResult:
    """Step description."""

    # 1. Verify textual context is available
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # 2. Step logic
    try:
        # Show progress with loading indicator
        with ctx.textual.loading("Processing..."):
            result = do_something()

        # Show result
        ctx.textual.mount(
            Panel(text="Success!", panel_type="success")
        )

        return Success("Operation completed", metadata={"result": result})

    except Exception as e:
        ctx.textual.mount(Panel(str(e), panel_type="error"))
        return Error(str(e))
```

### Key Features

1. **No Manual Step Headers**: The `TextualWorkflowExecutor` automatically renders headers
2. **Single Context**: Only `ctx.textual` for all UI interaction
3. **Loading Indicators**: Use context managers for long operations
4. **Textual Widgets**: Import widgets from `titan_cli.ui.tui.widgets`
5. **Thread-Safe**: All UI communication is automatically thread-safe

---

## Common Pitfalls

### ⚠️ Step Function Naming

**CRITICAL**: The function name must EXACTLY match the `step:` field in your workflow YAML.

#### Example from Project Steps

**Project structure**:
```
.titan/
├── steps/
│   ├── github/
│   │   └── capture_pr_context.py  # Contains function
│   └── android/
│       └── detekt_check.py
└── workflows/
    └── create-pr-ai.yaml
```

**Function definition** (`.titan/steps/github/capture_pr_context.py`):
```python
def capture_pr_context(ctx: WorkflowContext) -> WorkflowResult:  # ← Function name
    """Capture PR context."""
    ...

__all__ = ["capture_pr_context"]  # ← Must match
```

**Workflow reference** (`.titan/workflows/create-pr-ai.yaml`):
```yaml
hooks:
  before_pr_generation:
    - id: capture-context
      name: "Capture PR Context"
      plugin: project
      step: capture_pr_context  # ← Must match function name EXACTLY
```

#### Common Mistakes

❌ **DON'T DO THIS**:
```python
# Function name has _step suffix
def capture_pr_context_step(ctx):  # ← Wrong!
    ...
```
```yaml
step: capture_pr_context  # ← Won't find the function
```

❌ **OR THIS**:
```python
def capture_pr_context(ctx):  # ← Function name
    ...
```
```yaml
step: capture_pr_context_step  # ← Wrong! Extra _step suffix
```

✅ **CORRECT**:
```python
def capture_pr_context(ctx):  # ← Exact match
    ...
```
```yaml
step: capture_pr_context  # ← Exact match
```

#### Why This Happens

The `ProjectStepSource` searches for functions by name using Python's `getattr()`:
```python
step_func = getattr(module, step_name, None)  # Looks for exact name
```

**Rule**: Function name = step name. No suffixes, no prefixes, exact match.

---

## TextualComponents API

### Location
**File**: `/titan_cli/ui/tui/textual_components.py`
**Class**: `TextualComponents`

### Main Methods

#### 1. `mount(widget: Widget)`
Mounts a Textual widget to the output panel.

```python
from titan_cli.ui.tui.widgets import Panel

ctx.textual.mount(
    Panel(text="Operation completed", panel_type="success")
)
```

#### 2. `text(text: str, markup: str = "")`
Appends inline text with optional markup styling.

```python
ctx.textual.text("Processing...", markup="cyan")
ctx.textual.text("Warning!", markup="yellow")
ctx.textual.text("")  # Empty line for spacing
```

**Common markup**: `"bold"`, `"dim"`, `"cyan"`, `"yellow"`, `"red"`, `"green"`, `"bold cyan"`

#### 3. `markdown(markdown_text: str)`
Renders markdown content.

```python
analysis = "## Summary\n\n- Point 1\n- Point 2"
ctx.textual.markdown(analysis)
```

#### 4. `ask_text(question: str, default: str = "") -> Optional[str]`
Requests text input from user (blocks until response).

```python
title = ctx.textual.ask_text("Enter PR title:", default="")
if not title:
    return Error("Title cannot be empty")
```

#### 5. `ask_multiline(question: str, default: str = "") -> Optional[str]`
Requests multiline input (Enter to submit, Shift+Enter for new line).

```python
description = ctx.textual.ask_multiline(
    "Enter issue description:",
    default=""
)
```

#### 6. `ask_confirm(question: str, default: bool = True) -> bool`
Requests Y/N confirmation.

```python
if ctx.textual.ask_confirm("Use AI-generated message?", default=True):
    # User said Yes
    pass
else:
    # User said No
    pass
```

#### 7. `loading(message: str)` (Context Manager)
Shows a loading indicator during long operations.

```python
with ctx.textual.loading("Analyzing issue..."):
    analysis = jira_agent.analyze_issue(issue_key)
# Loading indicator disappears automatically
```

#### 8. `launch_external_cli(cli_name: str, prompt: str = None, cwd: str = None) -> int`
Launches an external CLI, temporarily suspending the TUI.

```python
exit_code = ctx.textual.launch_external_cli(
    "claude",
    prompt="Fix this bug",
    cwd="/path/to/project"
)
```

---

## Scroll Behavior Guidelines

### Overview

The Textual TUI uses a three-layer scroll management system to ensure consistent and predictable scrolling behavior.

### Rules

**1. Widgets NEVER auto-scroll**

Custom widgets (Panel, Markdown, Table, etc.) must NOT call scroll methods internally. This prevents:
- Conflicts between multiple widgets trying to control scroll position
- Unpredictable "tug of war" scroll behavior
- Widgets interrupting user's scroll position

```python
# ❌ BAD - Widget calling scroll
def markdown(self, markdown_text: str):
    md_widget = Markdown(markdown_text)
    target.mount(md_widget)
    self.output_widget._scroll_to_end()  # DON'T DO THIS

# ✅ GOOD - Widget just mounts, no scroll
def markdown(self, markdown_text: str):
    md_widget = Markdown(markdown_text)
    target.mount(md_widget)
    # Screen handles scroll when step completes
```

**2. Steps CAN manually scroll (rarely needed)**

Only use `ctx.textual.scroll_to_end()` in specific cases:
- Step displays very large content (exceeds full screen height)
- AND needs to immediately show an interactive widget below it
- User would otherwise need to manually scroll to see the next action

```python
# ✅ GOOD - Manual scroll for large content with interactive widget after
def ai_pr_description_step(ctx: WorkflowContext) -> WorkflowResult:
    # Show large PR description
    ctx.textual.markdown(large_pr_body)

    # Scroll so user sees the choice buttons below
    ctx.textual.scroll_to_end()

    # User now sees the interactive widget
    choice = ctx.textual.ask_choice("What would you like to do?", options)
```

```python
# ❌ BAD - Unnecessary manual scroll
def simple_step(ctx: WorkflowContext) -> WorkflowResult:
    ctx.textual.text("Processing...")
    ctx.textual.scroll_to_end()  # Not needed - screen will scroll when step ends
    return Success("Done")
```

**3. Screen ALWAYS auto-scrolls on step completion**

The workflow execution screen automatically scrolls to the bottom when:
- A step calls `ctx.textual.end_step()`
- This is the default behavior - no action needed from step developers
- Happens even if step already scrolled manually (redundant but safe)

### When to Use Manual Scroll

Use `ctx.textual.scroll_to_end()` only when ALL of these are true:

1. ✅ Content displayed is VERY large (multiple screen heights)
2. ✅ An interactive widget (ask_text, ask_confirm, ask_choice) comes immediately after
3. ✅ User needs to see the widget to continue the workflow
4. ✅ Without scroll, user would be stuck scrolling manually before they can interact

### Examples

**Example 1: Good use of manual scroll**
```python
# Large markdown preview + edit workflow
ctx.textual.markdown(very_large_pr_description)  # Multiple screens tall
ctx.textual.scroll_to_end()  # User needs to see buttons below
choice = ctx.textual.ask_choice("Use/Edit/Reject?", options)

if choice == "edit":
    edited = ctx.textual.ask_multiline("Edit content:", default=content)
    ctx.textual.scroll_to_end()  # After editing, show preview below
    ctx.textual.markdown(edited_preview)
    ctx.textual.scroll_to_end()  # Show confirmation button
    confirmed = ctx.textual.ask_confirm("Use this?")
```

**Example 2: No manual scroll needed**
```python
# Small/medium content - let screen handle it
ctx.textual.text("Processing...")
ctx.textual.mount(Panel("Result: Success", panel_type="success"))
# Screen will auto-scroll when step ends
return Success("Done")
```

### Default Approach

**When in doubt, DON'T use manual scroll.** Let the screen handle it automatically. Manual scroll is only for exceptional cases with very large content and immediate user interaction.

---

## Available Widgets

### Location
**File**: `/titan_cli/ui/tui/widgets/__init__.py`

### Panel
Displays content in a bordered panel.

```python
from titan_cli.ui.tui.widgets import Panel

# Success panel
ctx.textual.mount(Panel("Operation successful", panel_type="success"))

# Error panel
ctx.textual.mount(Panel("Error occurred", panel_type="error"))

# Info panel
ctx.textual.mount(Panel("FYI: Something happened", panel_type="info"))

# Warning panel
ctx.textual.mount(Panel("Warning message", panel_type="warning"))

# Default panel
ctx.textual.mount(Panel("Regular message", panel_type="default"))
```

### Table
Displays tabular data.

```python
from titan_cli.ui.tui.widgets import Table

headers = ["#", "Key", "Status", "Summary"]
rows = [
    ["1", "PROJ-123", "Open", "Fix login bug"],
    ["2", "PROJ-124", "In Progress", "Add dark mode"],
]

ctx.textual.mount(
    Table(
        headers=headers,
        rows=rows,
        title="Issues"
    )
)
```

---

## Complete Examples

### Example 1: Simple Step with Panel

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ui.tui.widgets import Panel

def simple_step(ctx: WorkflowContext) -> WorkflowResult:
    """A simple step that shows a message."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    message = ctx.get("message", "Hello, World!")

    ctx.textual.mount(
        Panel(text=message, panel_type="success")
    )

    return Success("Message displayed")
```

### Example 2: Step with User Input

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from titan_cli.ui.tui.widgets import Panel

def prompt_for_title_step(ctx: WorkflowContext) -> WorkflowResult:
    """Prompt user for a title."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Skip if already exists
    if ctx.get("title"):
        return Skip("Title already provided")

    try:
        title = ctx.textual.ask_text("Enter title:", default="")

        if not title:
            return Error("Title cannot be empty")

        ctx.textual.mount(
            Panel(f"Title set: {title}", panel_type="success")
        )

        return Success("Title captured", metadata={"title": title})

    except (KeyboardInterrupt, EOFError):
        return Error("User cancelled")
```

### Example 3: Step with AI and Loading Indicator

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from titan_cli.ui.tui.widgets import Panel

def ai_analyze_step(ctx: WorkflowContext) -> WorkflowResult:
    """Analyze content using AI."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Check AI availability
    if not ctx.ai or not ctx.ai.is_available():
        ctx.textual.mount(
            Panel("AI not configured", panel_type="info")
        )
        return Skip("AI not configured")

    content = ctx.get("content")
    if not content:
        ctx.textual.mount(
            Panel("No content to analyze", panel_type="error")
        )
        return Error("No content to analyze")

    # Analyze with loading indicator
    with ctx.textual.loading("Analyzing content with AI..."):
        analysis = ctx.ai.generate([{
            "role": "user",
            "content": f"Analyze this: {content}"
        }])

    # Show result
    ctx.textual.text("")
    ctx.textual.text("AI Analysis:", markup="bold cyan")
    ctx.textual.text("")
    ctx.textual.markdown(analysis)

    # Confirm usage
    use_analysis = ctx.textual.ask_confirm(
        "Use this analysis?",
        default=True
    )

    if not use_analysis:
        ctx.textual.text("Analysis rejected", markup="yellow")
        return Skip("User rejected analysis")

    ctx.textual.mount(
        Panel("Analysis accepted", panel_type="success")
    )

    return Success("Analysis completed", metadata={"analysis": analysis})
```

### Example 4: Step with Table Results

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ui.tui.widgets import Panel, Table

def search_issues_step(ctx: WorkflowContext) -> WorkflowResult:
    """Search and display issues."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    if not ctx.jira:
        ctx.textual.mount(
            Panel("JIRA client not available", panel_type="error")
        )
        return Error("JIRA client not available")

    query = ctx.get("query", "status = Open")

    # Search with loading
    with ctx.textual.loading("Searching issues..."):
        issues = ctx.jira.search_tickets(jql=query, max_results=50)

    if not issues:
        ctx.textual.mount(
            Panel("No issues found", panel_type="info")
        )
        return Success("No issues found", metadata={"issues": []})

    # Show result
    ctx.textual.mount(
        Panel(f"Found {len(issues)} issues", panel_type="success")
    )
    ctx.textual.text("")

    # Prepare table
    headers = ["#", "Key", "Status", "Summary"]
    rows = []
    for i, issue in enumerate(issues, 1):
        rows.append([
            str(i),
            issue.key,
            issue.status or "Unknown",
            (issue.summary or "No summary")[:60]
        ])

    # Render table
    ctx.textual.mount(
        Table(headers=headers, rows=rows, title="Issues")
    )

    return Success(
        f"Found {len(issues)} issues",
        metadata={"issues": issues}
    )
```

### Example 5: Step with Error Handling

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ui.tui.widgets import Panel
import requests

def fetch_data_step(ctx: WorkflowContext) -> WorkflowResult:
    """Fetch data from API."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    url = ctx.get("url")
    if not url:
        ctx.textual.mount(Panel("URL is required", panel_type="error"))
        return Error("URL is required")

    try:
        # Show info
        ctx.textual.text(f"Fetching from: {url}", markup="dim")

        # Fetch with loading
        with ctx.textual.loading(f"Fetching data from {url}..."):
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

        # Success
        ctx.textual.mount(
            Panel(
                f"Successfully fetched {len(data)} records",
                panel_type="success"
            )
        )

        return Success("Data fetched", metadata={"data": data})

    except requests.RequestException as e:
        error_msg = f"Failed to fetch data: {e}"
        ctx.textual.mount(Panel(error_msg, panel_type="error"))
        return Error(error_msg)
    except ValueError as e:
        error_msg = f"Invalid JSON response: {e}"
        ctx.textual.mount(Panel(error_msg, panel_type="error"))
        return Error(error_msg)
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        error_msg = f"Unexpected error: {e}\n\n{error_detail}"
        ctx.textual.mount(Panel(error_msg, panel_type="error"))
        return Error(error_msg)
```

---

## Reference Files

### Core Components
- **TextualComponents API**: `/titan_cli/ui/tui/textual_components.py`
- **Widgets**: `/titan_cli/ui/tui/widgets/`
- **Executor**: `/titan_cli/ui/tui/textual_workflow_executor.py`
- **Execution Screen**: `/titan_cli/ui/tui/screens/workflow_execution.py`

### Real Step Examples

**GitHub Plugin**:
- `/plugins/titan-plugin-github/titan_plugin_github/steps/github_prompt_steps.py`
- `/plugins/titan-plugin-github/titan_plugin_github/steps/ai_pr_step.py`
- `/plugins/titan-plugin-github/titan_plugin_github/steps/create_pr_step.py`

**Git Plugin**:
- `/plugins/titan-plugin-git/titan_plugin_git/steps/ai_commit_message_step.py`
- `/plugins/titan-plugin-git/titan_plugin_git/steps/commit_step.py`

**Jira Plugin**:
- `/plugins/titan-plugin-jira/titan_plugin_jira/steps/search_saved_query_step.py`
- `/plugins/titan-plugin-jira/titan_plugin_jira/steps/prompt_select_issue_step.py`
- `/plugins/titan-plugin-jira/titan_plugin_jira/steps/get_issue_step.py`
- `/plugins/titan-plugin-jira/titan_plugin_jira/steps/ai_analyze_issue_step.py`

---

## Benefits of the Textual Framework

1. **Unified UI**: Single context (`ctx.textual`) for all UI interaction
2. **Better UX**: Interactive Textual widgets superior to basic terminal output
3. **Integrated Progress**: Executor handles headers automatically, steps focus on logic
4. **Loading Indicators**: Context managers for showing progress during long operations
5. **No Boilerplate**: No repetitive code for headers and formatting
6. **Thread-Safe**: Automatic synchronization between execution threads and UI
7. **Markdown Support**: Native markdown rendering in the TUI
8. **External CLIs**: Can suspend TUI to launch external tools (claude, gemini, etc.)

---

**Last updated**: 2026-02-05
