---
name: titan-ui-steps
description: Create Textual TUI steps with ctx.textual API - widgets, user input, pattern matching. Use when building workflow steps or working with the TUI framework.
keywords: steps, textual, tui, widgets, ctx.textual, user interface, pattern matching
---

# Titan UI Steps - Textual TUI Step Development

**Purpose**: Creating workflow steps that orchestrate user experience using the Textual TUI framework.

## Table of Contents

- [What Are Steps?](#what-are-steps)
- [Core Responsibilities](#core-responsibilities)
- [Basic Structure](#basic-structure)
- [ctx.textual API Reference](#ctxtextual-api-reference)
- [Available Widgets](#available-widgets)
- [Pattern Matching for ClientResult](#pattern-matching-for-clientresult)
- [Text vs Markdown](#text-vs-markdown)
- [Scroll Behavior](#scroll-behavior)
- [Common Mistakes](#common-mistakes)
- [Step Examples](#step-examples)
- [Calling Operations](#calling-operations)
- [Return Types](#return-types)

---

## What Are Steps?

**Steps** are the top layer in Titan's plugin architecture. They orchestrate the user experience and workflow execution.

**Steps are ONLY for UI orchestration**:
- Displaying information to the user
- Getting user input
- Calling operations/client methods
- Managing workflow state
- Handling results

**Steps are NOT for**:
- Business logic (use Operations)
- Data transformation (use Operations or Mappers)
- API calls (use Client Services)
- Complex calculations (use Operations)

Think of steps as **UI controllers** that coordinate between the user and the underlying business logic.

---

## Core Responsibilities

### 1. User Interaction

Display information:
```python
# Simple text
ctx.textual.text("Processing...")
ctx.textual.bold_text("Important Message")
ctx.textual.success_text("✓ Completed")
ctx.textual.error_text("✗ Failed")
ctx.textual.warning_text("⚠ Warning")
ctx.textual.dim_text("(optional detail)")

# Complex content
ctx.textual.markdown(long_formatted_content)
ctx.textual.mount(Panel("Info", panel_type="info"))
ctx.textual.mount(Table(headers, rows))
```

Get user input:
```python
name = ctx.textual.ask_text("Enter name:")
confirmed = ctx.textual.ask_confirm("Proceed?")
selected = ctx.textual.ask_choice("What to do?", options)
```

### 2. Workflow Orchestration

```python
def my_step(ctx: WorkflowContext) -> WorkflowResult:
    # ALWAYS start with this
    ctx.textual.begin_step("Step Name")

    # 1. Get parameters from context
    param1 = ctx.get("param1")
    param2 = ctx.get("param2", "default")

    # 2. Call client/operations
    result = ctx.client.do_something(param1)

    # 3. Pattern match the result
    match result:
        case ClientSuccess(data=item):
            # Display success
            ctx.textual.success_text("Success!")
            ctx.textual.end_step("success")
            return Success("Done", metadata={"item_id": item.id})

        case ClientError(error_message=err):
            # Display error
            ctx.textual.error_text(f"Failed: {err}")
            ctx.textual.end_step("error")
            return Error(err)
```

### 3. State Management

```python
# Read from context
value = ctx.get("key")
value = ctx.get("key", "default")

# Write to context (via metadata)
return Success("Done", metadata={
    "created_id": "123",
    "created_url": "https://...",
    "status": "active"
})
# These values become available in ctx.data for subsequent steps
```

### 4. Step Lifecycle

```python
def my_step(ctx: WorkflowContext) -> WorkflowResult:
    # 1. ALWAYS begin
    ctx.textual.begin_step("My Step")

    # 2. Do work...

    # 3. ALWAYS end (with status)
    ctx.textual.end_step("success")  # or "error"

    # 4. ALWAYS return a result
    return Success("Message")  # or Error(), Skip(), Exit()
```

---

## Basic Structure

### Step Template

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip, Exit
from titan_cli.ui.tui.widgets import Panel

def my_step(ctx: WorkflowContext) -> WorkflowResult:
    """Step description."""

    # 1. Verify textual context is available
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # 2. Begin step
    ctx.textual.begin_step("My Step")

    # 3. Step logic
    try:
        # Show progress with loading indicator
        with ctx.textual.loading("Processing..."):
            result = do_something()

        # Show result
        ctx.textual.mount(
            Panel(text="Success!", panel_type="success")
        )

        # End step
        ctx.textual.end_step("success")
        return Success("Operation completed", metadata={"result": result})

    except Exception as e:
        ctx.textual.mount(Panel(str(e), panel_type="error"))
        ctx.textual.end_step("error")
        return Error(str(e))
```

### Key Features

1. **No Manual Step Headers**: The `TextualWorkflowExecutor` automatically renders headers
2. **Single Context**: Only `ctx.textual` for all UI interaction
3. **Loading Indicators**: Use context managers for long operations
4. **Textual Widgets**: Import widgets from `titan_cli.ui.tui.widgets`
5. **Thread-Safe**: All UI communication is automatically thread-safe

---

## ctx.textual API Reference

**Location**: `/titan_cli/ui/tui/textual_components.py`
**Class**: `TextualComponents`

Available via `ctx.textual` in workflow steps.

### Display Methods

#### Text Display

```python
# Normal text
ctx.textual.text("Normal message")
ctx.textual.text("")  # Empty line for spacing

# Styled text
ctx.textual.bold_text("Important message")
ctx.textual.dim_text("Secondary information")
ctx.textual.italic_text("Emphasis")
ctx.textual.dim_italic_text("Secondary emphasis")

# Colored text
ctx.textual.primary_text("Primary color message")
ctx.textual.bold_primary_text("Bold primary message")
ctx.textual.success_text("Operation successful")
ctx.textual.error_text("Operation failed")
ctx.textual.warning_text("Warning message")
```

**IMPORTANT**: Always use these specific methods instead of `text()` with markup:

```python
# ✅ CORRECT
ctx.textual.dim_text("(empty content)")
ctx.textual.success_text("Done!")

# ❌ WRONG - Don't use markup parameter
ctx.textual.text("(empty content)", markup="dim")
ctx.textual.text("Done!", markup="green")
```

#### Other Display Methods

**`markdown(markdown_text: str)`** - Renders markdown content

```python
analysis = "## Summary\n\n- Point 1\n- Point 2"
ctx.textual.markdown(analysis)
```

**`mount(widget: Widget)`** - Mounts any Textual widget

```python
from titan_cli.ui.tui.widgets import Panel

ctx.textual.mount(
    Panel(text="Operation completed", panel_type="success")
)
```

**`begin_step(title: str)`** - Marks the beginning of a step

```python
ctx.textual.begin_step("Fetching PR Comments")
```

**`end_step(status: str)`** - Marks the end of a step

```python
ctx.textual.end_step("success")
ctx.textual.end_step("error")
ctx.textual.end_step("skip")
```

**Important**: The `end_step()` status is separate from the `WorkflowResult` you return:
- `Success` → typically use `end_step("success")`
- `Error` → typically use `end_step("error")`
- `Skip` → typically use `end_step("skip")`
- `Exit` → use `end_step("success")` or `end_step("skip")` depending on context

**`scroll_to_end()`** - Manually scrolls to bottom (rarely needed)

```python
# Only use when showing large content + interactive widget immediately after
ctx.textual.markdown(very_large_content)
ctx.textual.scroll_to_end()  # Ensure user sees the next widget
choice = ctx.textual.ask_choice("What to do?", options)
```

### Interactive Methods

#### `ask_text(question: str, default: str = "") -> Optional[str]`

Requests single-line text input from user (blocks until response).

```python
title = ctx.textual.ask_text("Enter PR title:", default="")
if not title:
    return Error("Title cannot be empty")
```

#### `ask_multiline(question: str, default: str = "") -> Optional[str]`

Requests multiline input (Enter to submit, Shift+Enter for new line).

```python
description = ctx.textual.ask_multiline(
    "Enter issue description:",
    default=""
)
```

#### `ask_confirm(question: str, default: bool = True) -> bool`

Requests Y/N confirmation.

```python
if ctx.textual.ask_confirm("Use AI-generated message?", default=True):
    # User said Yes
    pass
else:
    # User said No
    pass
```

#### `ask_selection(question: str, options: List[SelectionOption]) -> List[Any]`

Shows a multi-select list (spacebar to toggle, Enter to confirm).

```python
from titan_cli.ui.tui.widgets import SelectionOption

options = [
    SelectionOption(value="feature1", label="Feature 1"),
    SelectionOption(value="feature2", label="Feature 2"),
]

selected = ctx.textual.ask_selection("Select features:", options)
# Returns list of selected values: ["feature1", "feature2"]
```

#### `ask_choice(question: str, options: List[ChoiceOption]) -> Any`

Shows single-choice buttons.

```python
from titan_cli.ui.tui.widgets import ChoiceOption

options = [
    ChoiceOption(value="use", label="Use as-is", variant="primary"),
    ChoiceOption(value="edit", label="Edit", variant="default"),
    ChoiceOption(value="reject", label="Reject", variant="error"),
]

choice = ctx.textual.ask_choice("What to do?", options)
# Returns single value: "use", "edit", or "reject"
```

#### `ask_option(question: str, options: List[OptionItem]) -> Any`

Shows a styled option list with titles and descriptions.

```python
from titan_cli.ui.tui.widgets import OptionItem

options = [
    OptionItem(
        value=123,
        title="PR #123: Add new feature",
        description="Branch: feature/new → main"
    ),
    OptionItem(
        value=124,
        title="PR #124: Fix bug",
        description="Branch: fix/bug → develop"
    ),
]

selected = ctx.textual.ask_option("Select a PR:", options)
# Returns value: 123 or 124
```

### Utility Methods

#### `loading(message: str)` (Context Manager)

Shows a loading spinner during long operations.

```python
with ctx.textual.loading("Analyzing issue..."):
    analysis = jira_agent.analyze_issue(issue_key)
# Loading indicator disappears automatically
```

#### `launch_external_cli(cli_name: str, prompt: str = None, cwd: str = None) -> int`

Launches an external CLI, temporarily suspending the TUI.

```python
exit_code = ctx.textual.launch_external_cli(
    "claude",
    prompt="Fix this bug",
    cwd="/path/to/project"
)
```

---

## Available Widgets

**Location**: `/titan_cli/ui/tui/widgets/`

All widgets are imported from this package and can be mounted using `ctx.textual.mount()`.

### Display Widgets

#### Panel

Displays content in a bordered panel with different types/colors.

```python
from titan_cli.ui.tui.widgets import Panel

# Success panel (green)
ctx.textual.mount(Panel("Operation successful", panel_type="success"))

# Error panel (red)
ctx.textual.mount(Panel("Error occurred", panel_type="error"))

# Info panel (blue)
ctx.textual.mount(Panel("FYI: Something happened", panel_type="info"))

# Warning panel (yellow)
ctx.textual.mount(Panel("Warning message", panel_type="warning"))

# Default panel (no color)
ctx.textual.mount(Panel("Regular message", panel_type="default"))
```

#### Table

Displays tabular data with headers.

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

#### Text Widgets

Various styled text widgets (used internally by `ctx.textual` methods).

**Note**: You should use `ctx.textual` methods instead of mounting these widgets directly:
- `ctx.textual.text()` → Text
- `ctx.textual.bold_text()` → BoldText
- `ctx.textual.dim_text()` → DimText
- `ctx.textual.success_text()` → SuccessText
- etc.

### Interactive Widgets

These are used internally by the `ctx.textual.ask_*()` methods. You typically don't instantiate them directly:

- **PromptInput**: Single-line text input (used by `ask_text()`)
- **PromptTextArea**: Multi-line text input (used by `ask_multiline()`)
- **PromptSelectionList**: Multi-select list (used by `ask_selection()`)
- **PromptChoice**: Single-choice buttons (used by `ask_choice()`)
- **PromptOptionList**: Styled option list (used by `ask_option()`)

---

## Pattern Matching for ClientResult

**CRITICAL**: ALL client method calls return `ClientResult[T]`. You MUST use pattern matching, never try/except.

### ✅ REQUIRED Pattern

```python
# Get data from client
result = ctx.client.get_item(item_id)

# Pattern matching is MANDATORY
match result:
    case ClientSuccess(data=item):
        # Success path - use the data
        ctx.textual.success_text(f"Found: {item.title}")
        ctx.textual.end_step("success")
        return Success("Item retrieved", metadata={"item_id": item.id})

    case ClientError(error_message=err):
        # Error path - handle the error
        ctx.textual.error_text(f"Failed: {err}")
        ctx.textual.end_step("error")
        return Error(err)
```

### ❌ WRONG - Don't Use try/except

```python
# ❌ BAD - try/except for ClientResult
try:
    result = ctx.client.get_item(item_id)

    if isinstance(result, ClientError):  # ❌ isinstance check
        return Error(result.error_message)

    item = result.data  # ❌ Direct .data access (assumes success)

except Exception as e:  # ❌ Catching generic exceptions
    return Error(str(e))
```

### Why Pattern Matching?

1. **Type Safety**: Compiler knows what fields are available
2. **Exhaustive**: You can't forget to handle error cases
3. **Cleaner**: No need for isinstance checks
4. **Idiomatic**: Pythonic way to handle sum types

---

## Text vs Markdown

### Use `text()` / `bold_text()` for Simple Content

```python
# ✅ CORRECT - Simple headers/labels
ctx.textual.bold_text("Issue Details")
ctx.textual.dim_text("(optional)")

# ❌ WRONG - Markdown overkill
ctx.textual.markdown("## Issue Details")
ctx.textual.markdown("_(optional)_")
```

### Use `markdown()` for Complex Content

```python
# ✅ CORRECT - Complex formatted content
analysis = """
## Summary

This issue has the following problems:

- **Authentication**: Token expired
- **Permissions**: Missing admin role
- **Data**: Invalid schema

### Recommendation

Update the authentication service.
"""

ctx.textual.markdown(analysis)
```

### Guidelines

- **Simple headers**: `bold_text()`
- **Simple labels**: `text()`
- **Secondary info**: `dim_text()`
- **Lists, code blocks, tables**: `markdown()`
- **Multi-paragraph formatted content**: `markdown()`

---

## Scroll Behavior

### Rules

**1. Widgets NEVER auto-scroll**

Custom widgets must NOT call scroll methods internally. This prevents conflicts.

**2. Steps CAN manually scroll (rarely needed)**

Only use `ctx.textual.scroll_to_end()` when:
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

The workflow execution screen automatically scrolls to the bottom when a step calls `ctx.textual.end_step()`. This is the default behavior - no action needed from step developers.

### Default Approach

**When in doubt, DON'T use manual scroll.** Let the screen handle it automatically.

---

## Common Mistakes

### ❌ Mistake #1: Business Logic in Steps

```python
# ❌ BAD - Complex logic in step
def filter_issues_step(ctx: WorkflowContext) -> WorkflowResult:
    issues = ctx.get("issues")

    filtered = []
    for issue in issues:
        if issue.status == "pending" and issue.priority > 3:
            if issue.created_date < datetime.now() - timedelta(days=7):
                filtered.append(issue)

    # ... display filtered
```

```python
# ✅ GOOD - Call operation
from ..operations import filter_high_priority_pending

def filter_issues_step(ctx: WorkflowContext) -> WorkflowResult:
    issues = ctx.get("issues")

    filtered = filter_high_priority_pending(issues, days_old=7)

    # Display filtered
    ctx.textual.text(f"Found {len(filtered)} high-priority issues")
    # ...
```

### ❌ Mistake #2: try/except for ClientResult

See [Pattern Matching for ClientResult](#pattern-matching-for-clientresult) section above.

### ❌ Mistake #3: Calling API Multiple Times

```python
# ❌ BAD - Calling API twice
def create_issue_step(ctx: WorkflowContext) -> WorkflowResult:
    # Create issue - FIRST API CALL
    result = ctx.jira.create_issue(
        project_key=project,
        issue_type=issue_type,
        summary=summary
    )

    match result:
        case ClientSuccess(data=issue):
            ctx.textual.success_text(f"Issue created: {issue.key}")

            # ❌ SECOND API CALL - just to get the URL
            issue_details = ctx.jira.get_issue(issue.key)

            match issue_details:
                case ClientSuccess(data=details):
                    ctx.textual.text(f"URL: {details.url}")  # Already had this!
            # ...
```

```python
# ✅ GOOD - Get all data in one call
def create_issue_step(ctx: WorkflowContext) -> WorkflowResult:
    result = ctx.jira.create_issue(
        project_key=project,
        issue_type=issue_type,
        summary=summary
    )

    match result:
        case ClientSuccess(data=issue):
            # UIIssue has everything we need
            ctx.textual.success_text(f"Issue created: {issue.key}")
            ctx.textual.text(f"URL: {issue.url}")  # ✅ No extra API call
            # ...
```

**Tip**: If you need more data, update the UI model or the service method to include it in the initial response.

### ❌ Mistake #4: Markdown for Simple Text

```python
# ❌ WRONG - Markdown for simple title
ctx.textual.markdown("## Describe the Issue")

description = ctx.textual.ask_text(
    prompt="Description:",
    multiline=True
)
```

```python
# ✅ CORRECT - bold_text for simple headers
ctx.textual.bold_text("Describe the Issue")

description = ctx.textual.ask_text(
    prompt="Description:",
    multiline=True
)
```

### ❌ Mistake #5: Importing Services or Network

```python
# ❌ BAD - Steps should not import lower layers
from ..clients.services import ResourceService
from ..clients.network import ResourceAPI

def my_step(ctx: WorkflowContext) -> WorkflowResult:
    service = ResourceService()  # ❌ Direct instantiation
    # ...
```

```python
# ✅ GOOD - Use ctx.client or operations
from ..operations import fetch_resources

def my_step(ctx: WorkflowContext) -> WorkflowResult:
    # Use client from context
    result = ctx.client.get_resources()

    # OR call operation
    resources = fetch_resources(ctx.client, filters)
    # ...
```

---

## Step Examples

### Example 1: Simple Step with Panel

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ui.tui.widgets import Panel

def simple_step(ctx: WorkflowContext) -> WorkflowResult:
    """A simple step that shows a message."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Simple Step")

    message = ctx.get("message", "Hello, World!")

    ctx.textual.mount(
        Panel(text=message, panel_type="success")
    )

    ctx.textual.end_step("success")
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

    ctx.textual.begin_step("Prompt for Title")

    # Skip if already exists
    if ctx.get("title"):
        ctx.textual.end_step("skip")
        return Skip("Title already provided")

    try:
        title = ctx.textual.ask_text("Enter title:", default="")

        if not title:
            ctx.textual.end_step("error")
            return Error("Title cannot be empty")

        ctx.textual.mount(
            Panel(f"Title set: {title}", panel_type="success")
        )

        ctx.textual.end_step("success")
        return Success("Title captured", metadata={"title": title})

    except (KeyboardInterrupt, EOFError):
        ctx.textual.end_step("error")
        return Error("User cancelled")
```

### Example 3: Step with Pattern Matching

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ui.tui.widgets import Panel

def get_issue_step(ctx: WorkflowContext) -> WorkflowResult:
    """Fetch and display a Jira issue."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Fetch Issue")

    issue_key = ctx.get("issue_key")
    if not issue_key:
        ctx.textual.end_step("error")
        return Error("issue_key is required")

    # Fetch with loading
    with ctx.textual.loading(f"Fetching {issue_key}..."):
        result = ctx.jira.get_issue(issue_key)

    # Pattern matching is MANDATORY
    match result:
        case ClientSuccess(data=issue):
            # Display success
            ctx.textual.mount(Panel(
                f"Found: {issue.key} - {issue.summary}",
                panel_type="success"
            ))
            ctx.textual.end_step("success")
            return Success("Issue retrieved", metadata={"issue": issue})

        case ClientError(error_message=err):
            # Display error
            ctx.textual.mount(Panel(err, panel_type="error"))
            ctx.textual.end_step("error")
            return Error(err)
```

### Example 4: Step with Table Results

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ui.tui.widgets import Panel, Table

def search_issues_step(ctx: WorkflowContext) -> WorkflowResult:
    """Search and display issues."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Search Issues")

    query = ctx.get("query", "status = Open")

    # Search with loading
    with ctx.textual.loading("Searching issues..."):
        result = ctx.jira.search_issues(jql=query, max_results=50)

    match result:
        case ClientSuccess(data=issues):
            if not issues:
                ctx.textual.mount(Panel("No issues found", panel_type="info"))
                ctx.textual.end_step("success")
                return Success("No issues found", metadata={"issues": []})

            # Show result
            ctx.textual.mount(Panel(
                f"Found {len(issues)} issues",
                panel_type="success"
            ))
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

            ctx.textual.end_step("success")
            return Success(
                f"Found {len(issues)} issues",
                metadata={"issues": issues}
            )

        case ClientError(error_message=err):
            ctx.textual.mount(Panel(err, panel_type="error"))
            ctx.textual.end_step("error")
            return Error(err)
```

---

## Calling Operations

Steps should delegate business logic to **operations** (pure functions in `operations/`).

### Pattern

```python
# operations/issue_operations.py
from typing import List
from ..models.view import UIJiraIssue

def filter_high_priority_pending(
    issues: List[UIJiraIssue],
    days_old: int = 7
) -> List[UIJiraIssue]:
    """Filter high-priority pending issues older than N days."""
    from datetime import datetime, timedelta

    cutoff_date = datetime.now() - timedelta(days=days_old)

    return [
        issue for issue in issues
        if issue.status == "Pending"
        and issue.priority in ["High", "Critical"]
        and issue.created_date < cutoff_date
    ]
```

```python
# steps/filter_issues_step.py
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..operations import filter_high_priority_pending

def filter_issues_step(ctx: WorkflowContext) -> WorkflowResult:
    """Filter high-priority pending issues."""
    ctx.textual.begin_step("Filter Issues")

    issues = ctx.get("issues", [])

    # Call operation (pure function, easy to test)
    filtered = filter_high_priority_pending(issues, days_old=7)

    # Display results
    ctx.textual.text(f"Found {len(filtered)} high-priority pending issues")

    ctx.textual.end_step("success")
    return Success("Issues filtered", metadata={"filtered_issues": filtered})
```

### Benefits

- **Testable**: Operations are pure functions with no dependencies
- **Reusable**: Can be called from multiple steps
- **Clean**: Steps focus on UI, operations focus on logic
- **Maintainable**: Business logic in one place

---

## Return Types

Steps MUST return a `WorkflowResult`:

### Success

Step completed successfully, continue workflow.

```python
return Success("Operation completed", metadata={"result": result})
```

### Error

Step failed, stop workflow.

```python
return Error("Operation failed")
return Error("Operation failed", code="AUTH_ERROR")
```

### Skip

Step was skipped, continue workflow.

```python
return Skip("AI not configured")
return Skip("Title already provided", metadata={"title": existing_title})
```

### Exit

Exit workflow early in a controlled way (not an error, just nothing more to do).

```python
# No data found - not an error, just exit
if not data:
    ctx.textual.dim_text("No data found")
    ctx.textual.end_step("success")  # Step itself succeeded
    return Exit("No data to process")  # But exit the workflow

# User cancelled - skip this step and exit
if not user_confirmed:
    ctx.textual.warning_text("User cancelled")
    ctx.textual.end_step("skip")  # Mark as skipped
    return Exit("User cancelled")  # Exit the workflow
```

### Relationship with end_step()

The `end_step()` status reflects the **step's execution**, while the return type affects **workflow continuation**:

| Return Type | Typical end_step() | Workflow Effect |
|------------|-------------------|----------------|
| Success | "success" | Continue |
| Error | "error" | Stop |
| Skip | "skip" | Continue |
| Exit | "success" or "skip" | Stop (controlled) |

---

## What Steps MUST Do

✅ **Pattern match ALL ClientResult**:
```python
match result:
    case ClientSuccess(data=item):
        ...
    case ClientError(error_message=err):
        ...
```

✅ **Begin and end every step**:
```python
ctx.textual.begin_step("Name")
# ... work ...
ctx.textual.end_step("success" | "error" | "skip")
```

✅ **Return WorkflowResult**:
```python
return Success("msg", metadata={...})
return Error("msg", code=...)
return Skip("msg", metadata={...})
return Exit("msg")
```

## What Steps MUST NOT Do

❌ **NO business logic**:
```python
# Use operations instead
```

❌ **NO try/except for ClientResult**:
```python
# Use pattern matching
```

❌ **NO importing Services or Network**:
```python
# Use ctx.client or operations
```

---

**Last updated**: 2026-03-31
