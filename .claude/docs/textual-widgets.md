# Textual Widgets

Read this when you need a widget (display, interactive, container) or its parameters. Step structure and scroll rules: [textual.md](textual.md).

---

### Location
**Directory**: `/titan_cli/ui/tui/widgets/`
**Exports**: `/titan_cli/ui/tui/widgets/__init__.py`

All widgets are imported from this package and can be mounted using `ctx.textual.mount()` or used in interactive methods.

### Display Widgets

#### Panel
Displays content in a bordered panel with different types/colors. In steps, prefer the `ctx.textual.panel()` convenience method instead of mounting this widget manually.

```python
# Preferred in steps
ctx.textual.panel("Operation successful", panel_type="success")
ctx.textual.panel("Error occurred", panel_type="error")
ctx.textual.panel("FYI: Something happened", panel_type="info")
ctx.textual.panel("Warning message", panel_type="warning")
```

**Implementation**: `/titan_cli/ui/tui/widgets/panel.py`

#### LabeledSwitch
An on/off row: Textual's `Switch` beside a title and an optional description. Reusable wherever a setting is on or off (the Mods screen uses it for a mod and for each of its sections).

```python
LabeledSwitch("Merge queue", value=True, description="Your place in the queue.", name="queue")

def on_labeled_switch_changed(self, event: LabeledSwitch.Changed) -> None:
    save(event.switch.name, event.value)
```

`Changed` fires only when the person toggles it; assigning `.value` from code does not. `disabled=True` dims the row and blocks it.

**Implementation**: `/titan_cli/ui/tui/widgets/labeled_switch.py`

#### Table
Displays tabular data with headers. In steps, prefer the `ctx.textual.table()` convenience method instead of mounting this widget manually.

```python
headers = ["#", "Key", "Status", "Summary"]
rows = [
    ["1", "PROJ-123", "Open", "Fix login bug"],
    ["2", "PROJ-124", "In Progress", "Add dark mode"],
]

# Preferred in steps
ctx.textual.table(headers=headers, rows=rows, title="Issues")

# When one column holds long text, let it absorb the leftover width
ctx.textual.table(headers=headers, rows=rows, title="Issues", flex_column=3)
```

**Implementation**: `/titan_cli/ui/tui/widgets/table.py`, column arithmetic in
`/titan_cli/ui/tui/widgets/table_layout.py`

#### Text Widgets
Various styled text widgets (used internally by `ctx.textual` methods).

```python
from titan_cli.ui.tui.widgets import (
    Text,              # Normal text
    BoldText,          # Bold
    DimText,           # Dimmed/secondary
    ItalicText,        # Italic
    DimItalicText,     # Dim + Italic
    PrimaryText,       # Primary color
    BoldPrimaryText,   # Bold + Primary
    SuccessText,       # Green
    ErrorText,         # Red
    WarningText,       # Yellow
)

# Direct usage (rarely needed - prefer ctx.textual methods)
ctx.textual.mount(DimText("Secondary information"))
ctx.textual.mount(SuccessText("Operation completed"))
```

**Implementation**: `/titan_cli/ui/tui/widgets/text.py`

**Note**: These are used internally by `ctx.textual.dim_text()`, `ctx.textual.success_text()`, etc. You should use those methods instead of mounting these widgets directly.

### Interactive Widgets

#### PromptInput
Single-line text input widget (used by `ctx.textual.ask_text()`).

```python
from titan_cli.ui.tui.widgets import PromptInput

# Used internally by ctx.textual.ask_text()
# Typically not instantiated directly
```

**Implementation**: `/titan_cli/ui/tui/widgets/prompt_input.py`

#### PromptTextArea
Multi-line text input widget (used by `ctx.textual.ask_multiline()`).

```python
from titan_cli.ui.tui.widgets import PromptTextArea

# Used internally by ctx.textual.ask_multiline()
# Typically not instantiated directly
```

**Implementation**: `/titan_cli/ui/tui/widgets/prompt_textarea.py`

#### PromptSelectionList
Multi-select list widget (used by `ctx.textual.ask_multiselect()`).

```python
from titan_cli.ui.tui.widgets import PromptSelectionList, SelectionOption

options = [
    SelectionOption(value="opt1", label="Option 1"),
    SelectionOption(value="opt2", label="Option 2"),
]

# Used via ctx.textual.ask_multiselect("Question?", options)
```

**Implementation**: `/titan_cli/ui/tui/widgets/prompt_selection_list.py`

#### PromptChoice
Single-choice button widget (used by `ctx.textual.ask_choice()`).

```python
from titan_cli.ui.tui.widgets import PromptChoice, ChoiceOption

options = [
    ChoiceOption(value="yes", label="Yes", variant="primary"),
    ChoiceOption(value="no", label="No", variant="default"),
]

# Used via ctx.textual.ask_choice("Question?", options)
```

**Implementation**: `/titan_cli/ui/tui/widgets/prompt_choice.py`

**Variants**: `"primary"`, `"default"`, `"success"`, `"warning"`, `"error"`

#### PromptOptionList
Styled option list with titles and descriptions (used by `ctx.textual.ask_option()`).

```python
from titan_cli.engine import OptionItem  # canonical import (widgets re-export is backward-compat)
from titan_cli.ui.tui.widgets import PromptOptionList

options = [
    OptionItem(
        value=1,
        title="Option 1",
        description="Description for option 1"
    ),
    OptionItem(
        value=2,
        title="Option 2",
        description="Description for option 2"
    ),
]

# Used via ctx.textual.ask_option("Select:", options)
```

**Implementation**: `/titan_cli/ui/tui/widgets/prompt_option_list.py`

**Use case**: When you need to show a list with both a title and description (like PR selection, workflow selection).

### Container Widgets

#### StepContainer
Container for step content with header.

```python
from titan_cli.ui.tui.widgets import StepContainer

# Used internally by TextualWorkflowExecutor
# Shows step number and title
```

**Implementation**: `/titan_cli/ui/tui/widgets/step_container.py`

#### Button
Styled button widget.

```python
from titan_cli.ui.tui.widgets import Button

# Used internally by PromptChoice
# Typically not used directly
```

**Implementation**: `/titan_cli/ui/tui/widgets/button.py`
