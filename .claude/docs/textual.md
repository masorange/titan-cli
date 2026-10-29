# Textual Workflow Steps Guide

Read this when you write or change a workflow step: structure, pitfalls and scroll rules. The rest is split by task:

| Need | Read |
|---|---|
| A `ctx.textual` method (display, input, utility, AI review) | [textual-api.md](textual-api.md) |
| A widget and its parameters | [textual-widgets.md](textual-widgets.md) |
| A worked step to copy, real steps to imitate | [textual-examples.md](textual-examples.md) |
| A new widget or `TextualComponents` method (changing Titan itself) | [textual-extending.md](textual-extending.md) |

---

## Basic Structure

### Step Template

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip, Exit

def my_step(ctx: WorkflowContext) -> WorkflowResult:
    """Step description."""

    # 1. Verify textual context is available
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # 2. Mark the beginning of the step (renders the step header)
    ctx.textual.begin_step("My Step")

    # 3. Step logic
    try:
        # Show progress with loading indicator
        with ctx.textual.loading("Processing..."):
            result = do_something()

        # Show result
        ctx.textual.panel("Success!", panel_type="success")

        # 4. Mark the end of the step before returning
        ctx.textual.end_step("success")
        return Success("Operation completed", metadata={"result": result})

    except Exception as e:
        ctx.textual.panel(str(e), panel_type="error")
        ctx.textual.end_step("error")
        return Error(str(e))
```

### Key Features

1. **Step Headers via begin_step/end_step**: Steps render their own header by calling `ctx.textual.begin_step("Title")` at the start and `ctx.textual.end_step("success" | "error" | "skip")` before returning (see `plugins/titan-plugin-git/titan_plugin_git/steps/commit_step.py` for a real example)
2. **Single Context**: Only `ctx.textual` for all UI interaction
3. **Loading Indicators**: Use context managers for long operations
4. **Textual Widgets**: Import widgets from `titan_cli.ui.tui.widgets`
5. **Thread-Safe**: All UI communication is automatically thread-safe

---

## Common Pitfalls

### ⚠️ Step Function Naming

**CRITICAL (project/user steps only)**: For steps loaded from `.titan/steps/` (`plugin: project`) or `~/.titan/steps/` (`plugin: user`), the function name must EXACTLY match the `step:` field in your workflow YAML.

**Plugin steps are different**: official plugin steps are mapped explicitly in the plugin's `get_steps()` dictionary, so the YAML `step:` name can differ from the function name (e.g. the git plugin maps `"create_commit"` to `create_git_commit_step`).

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

**Rule**: For project/user steps, function name = step name. No suffixes, no prefixes, exact match. Plugin steps are resolved through the `get_steps()` mapping instead.

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
ctx.textual.panel("Result: Success", panel_type="success")
# Screen will auto-scroll when step ends
return Success("Done")
```

### Default Approach

**When in doubt, DON'T use manual scroll.** Let the screen handle it automatically. Manual scroll is only for exceptional cases with very large content and immediate user interaction.
