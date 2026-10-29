# Extending the Textual System

Read this only when you change Titan itself: a new widget, a new `TextualComponents` method, or widget tests. Writing a step does not need it.

---

This section explains how to add new widgets and methods to extend the Textual TUI framework.

### Creating a New Widget

Custom widgets should be created in `/titan_cli/ui/tui/widgets/` and follow Textual's widget patterns.

#### Step 1: Create Widget File

```python
# /titan_cli/ui/tui/widgets/my_custom_widget.py
from textual.widgets import Static
from textual.app import ComposeResult
from textual.containers import Vertical
from dataclasses import dataclass
from typing import Any, Callable, Optional

@dataclass
class MyCustomItem:
    """Data model for widget items."""
    value: Any
    label: str
    description: str = ""

class MyCustomWidget(Static):
    """
    Custom widget for specialized UI interaction.

    This widget shows a list of items with custom styling.
    """

    def __init__(
        self,
        question: str,
        items: list[MyCustomItem],
        on_submit: Optional[Callable[[Any], None]] = None,
        **kwargs
    ):
        """
        Args:
            question: Question to display
            items: List of items to show
            on_submit: Callback when user submits selection
        """
        super().__init__(**kwargs)
        self.question = question
        self.items = items
        self.on_submit = on_submit
        self.selected_index = 0

    def compose(self) -> ComposeResult:
        """Compose the widget UI using Textual components."""
        from .text import BoldText, DimText

        # Show question
        yield BoldText(self.question)
        yield DimText("")  # Empty line

        # Show items
        with Vertical():
            for i, item in enumerate(self.items):
                # Use markup for inline styling
                prefix = "→ " if i == self.selected_index else "  "
                yield Static(f"{prefix}[bold]{item.label}[/bold]")
                if item.description:
                    yield Static(f"  [dim]{item.description}[/dim]")

    def on_key(self, event) -> None:
        """Handle keyboard input."""
        if event.key == "up":
            self.selected_index = max(0, self.selected_index - 1)
            self.refresh()
        elif event.key == "down":
            self.selected_index = min(len(self.items) - 1, self.selected_index + 1)
            self.refresh()
        elif event.key == "enter":
            # Submit selection
            selected_item = self.items[self.selected_index]
            if self.on_submit:
                self.on_submit(selected_item.value)
```

#### Step 2: Export Widget

Add to `/titan_cli/ui/tui/widgets/__init__.py`:

```python
from .my_custom_widget import MyCustomWidget, MyCustomItem

__all__ = [
    # ... existing exports
    "MyCustomWidget",
    "MyCustomItem",
]
```

#### Step 3: Use Widget in Steps

You can now use the widget directly:

```python
from titan_cli.ui.tui.widgets import MyCustomWidget, MyCustomItem

def my_step(ctx: WorkflowContext) -> WorkflowResult:
    items = [
        MyCustomItem(value=1, label="Option 1", description="First option"),
        MyCustomItem(value=2, label="Option 2", description="Second option"),
    ]

    # Direct usage (widget handles its own display)
    ctx.textual.mount(MyCustomWidget(
        question="Select an option:",
        items=items
    ))

    return Success("Widget displayed")
```

### Adding Methods to TextualComponents

To make widgets easier to use in steps, add convenience methods to `TextualComponents`.

#### Location
**File**: `/titan_cli/ui/tui/textual_components.py`

#### Pattern for Interactive Methods

All interactive methods must use threading and event containers for communication between threads.

```python
# In TextualComponents class

def ask_custom(self, question: str, items: list) -> Any:
    """
    Ask user to select from custom widget.

    Args:
        question: Question to display
        items: List of items to choose from

    Returns:
        Selected value or None if cancelled
    """
    from .widgets import MyCustomWidget, MyCustomItem

    # Container for thread-safe communication
    result_container = {"result": None, "ready": threading.Event()}

    def on_submit(value):
        """Callback when user submits."""
        result_container["result"] = value
        result_container["ready"].set()

    # Create widget with callback
    widget = MyCustomWidget(
        question=question,
        items=items,
        on_submit=on_submit
    )

    # Mount widget on UI thread
    target = self._get_current_output_target()
    self.app.call_from_thread(target.mount, widget)

    # Wait for user response with timeout for Ctrl+C handling
    try:
        while not result_container["ready"].wait(timeout=0.5):
            pass
    except KeyboardInterrupt:
        result_container["result"] = None

    return result_container["result"]
```

#### KeyboardInterrupt Handling

**CRITICAL**: All interactive methods MUST handle Ctrl+C using a timeout loop:

```python
# ✅ CORRECT - Timeout allows KeyboardInterrupt to be caught
try:
    while not result_container["ready"].wait(timeout=0.5):
        pass
except KeyboardInterrupt:
    result_container["result"] = None

# ❌ WRONG - Blocks forever, Ctrl+C doesn't work
result_container["ready"].wait()
```

**Why this pattern:**
- Python can only process KeyboardInterrupt during active code execution
- `wait()` with no timeout blocks in C code, preventing interrupt handling
- `wait(timeout=0.5)` returns to Python every 0.5s, allowing interrupts
- Wrapping in try/except catches Ctrl+C and returns None gracefully

#### Usage After Adding Method

```python
def my_step(ctx: WorkflowContext) -> WorkflowResult:
    from titan_cli.ui.tui.widgets import MyCustomItem

    items = [
        MyCustomItem(value=1, label="Option 1", description="First"),
        MyCustomItem(value=2, label="Option 2", description="Second"),
    ]

    # Now much cleaner to use!
    selected = ctx.textual.ask_custom("Select an option:", items)

    if not selected:
        return Error("No selection made")

    return Success(f"Selected: {selected}")
```

### Common Extension Patterns

#### Pattern 1: Generic AI Integration

Always use `AIMessage` for model-agnostic AI calls:

```python
from titan_cli.ai.models import AIMessage

def ai_helper_step(ctx: WorkflowContext) -> WorkflowResult:
    if not ctx.ai or not ctx.ai.is_available():
        return Skip("AI not configured")

    # Build messages
    messages = [
        AIMessage(role="user", content="Analyze this...")
    ]

    # Generate (works with Claude, Gemini, any configured provider)
    with ctx.textual.loading("Generating..."):
        response = ctx.ai.generate(messages)

    result = response.content.strip()
    ctx.textual.markdown(result)

    return Success("AI analysis complete")
```

#### Pattern 2: Empty Content Handling

Always check for empty/None content from APIs:

```python
# ✅ CORRECT - Handle empty content gracefully
if content and content.strip():
    ctx.textual.markdown(content)
else:
    ctx.textual.dim_text("(no content)")

# ❌ WRONG - May crash on None or show empty space
ctx.textual.markdown(content)
```

#### Pattern 3: API Field Variations

Some APIs return different field names for the same data. Try multiple fields:

```python
# GitHub API line numbers
line = data.get("line") or data.get("original_line") or data.get("start_line")

# Author information
author = data.get("user") or data.get("author") or {}
```

#### Pattern 4: Recursive Data Structures

Use recursion for building hierarchical structures:

```python
def build_comment_tree(comments: list, parent_id: int = None) -> list:
    """Recursively build comment thread tree."""
    tree = []

    for comment in comments:
        if comment.parent_id == parent_id:
            # This comment belongs at this level
            tree.append(comment)

            # Recursively find children
            children = build_comment_tree(comments, comment.id)
            if children:
                comment.children = children

    return tree
```

### Widget Best Practices

#### 1. Use Dataclasses for Item Models

```python
@dataclass
class OptionItem:
    """Clear data structure for widget items."""
    value: Any
    title: str
    description: str = ""
```

#### 2. Accept Callbacks for Events

```python
def __init__(self, on_submit: Optional[Callable] = None):
    self.on_submit = on_submit
```

#### 3. Use Textual Markup for Styling

```python
# ✅ CORRECT - Use markup strings
yield Static(f"[bold]{title}[/bold]")
yield Static(f"[dim]{description}[/dim]")

# ❌ WRONG - Don't create multiple styled widgets
yield BoldText(title)  # Unnecessary - markup is cleaner
```

#### 4. Handle Focus and Keyboard Events

```python
def on_mount(self) -> None:
    """Set focus when widget mounts."""
    self.focus()

def on_key(self, event: Key) -> None:
    """Handle keyboard input."""
    if event.key == "enter":
        self.submit()
    elif event.key == "escape":
        self.cancel()
```

### Testing New Widgets

Test widgets interactively by creating a test step:

```python
# Test in a workflow step
def test_widget_step(ctx: WorkflowContext) -> WorkflowResult:
    if not ctx.textual:
        return Error("No Textual context")

    from titan_cli.ui.tui.widgets import MyCustomWidget, MyCustomItem

    items = [
        MyCustomItem(value=1, label="Test 1", description="First test"),
        MyCustomItem(value=2, label="Test 2", description="Second test"),
    ]

    ctx.textual.mount(MyCustomWidget("Test question:", items))

    return Success("Widget test complete")
```
