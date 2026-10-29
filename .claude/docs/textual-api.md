# TextualComponents API

Read this when you call or look up an `ctx.textual` method: display, interactive input, utility and AI review flows. Step structure, pitfalls and scroll rules: [textual.md](textual.md).

---

### Location
**File**: `/titan_cli/ui/tui/textual_components.py`
**Class**: `TextualComponents`

This is the main API available in workflow steps via `ctx.textual`. It provides methods for displaying content and requesting user input.

### Display Methods

#### Text Display Methods

These methods use the custom text widgets from `/titan_cli/ui/tui/widgets/text.py`:

```python
# Normal text
ctx.textual.text("Normal message")
ctx.textual.text("")  # Empty line for spacing

# Styled text
ctx.textual.bold_text("Important message")
ctx.textual.dim_text("Secondary information")

# Colored text
ctx.textual.primary_text("Primary color message")
ctx.textual.bold_primary_text("Bold primary message")
ctx.textual.success_text("Operation successful")
ctx.textual.error_text("Operation failed")  # an error card: copy button, plain text (no markup)
ctx.textual.error_text(err, actions=[("⟳ Retry", retry)])  # plus buttons of your own
# Every error is an ErrorCard, whichever way you show it: Panel(..., panel_type="error"),
# ctx.textual.panel(..., "error") and app.notify(..., severity="error") all end up as one
# (the last one in a modal). Toasts (notify) are informational only.
ctx.textual.warning_text("Warning message")

# RULE: every error the user sees is an error card, so it can be copied whole and offer the
# action that helps (Retry, Diagnose, Ask AI…). Do not print one as red text or a plain panel.
# An error worth copying (a ClientError, an engine Error, an exception or a message):
# bordered panel with a "⧉ Copy error" button; an exception's traceback goes in the copy
ctx.textual.error_card(result, title="Could not publish")

# Tinted, content-width chip — for a fact ABOUT the output, not part of it.
# Its one use today is naming the AI that served the step; pass it straight to the façade:
#   ctx.ai_router.generate_text(prompt, policy=my_step, announce=ctx.textual.ai_chip)
ctx.textual.ai_chip("claude · CLI, automatic")
```

**Note**: There are no `italic_text()` / `dim_italic_text()` methods on `ctx.textual`. If you need italic text, mount the `ItalicText` / `DimItalicText` widgets directly (from `titan_cli.ui.tui.widgets`).

**IMPORTANT**: `text()` takes a single string argument (no `markup` parameter). Always use the specific styled methods instead:

```python
# ✅ CORRECT
ctx.textual.dim_text("(empty content)")
ctx.textual.success_text("Done!")

# ❌ WRONG - Don't use markup parameter
ctx.textual.text("(empty content)", markup="dim")
ctx.textual.text("Done!", markup="green")
```

#### Other Display Methods

##### `markdown(markdown_text: str)`
Renders markdown content.

```python
analysis = "## Summary\n\n- Point 1\n- Point 2"
ctx.textual.markdown(analysis)
```

##### `panel(text, panel_type="info", show_icon=True, use_markdown=False)`
Shows a bordered panel with consistent styling. Preferred over mounting the `Panel` widget manually.

```python
ctx.textual.panel("Operation completed successfully!", panel_type="success")
ctx.textual.panel("Warning: This action cannot be undone", panel_type="warning")
ctx.textual.panel("## Analysis\n\n- Point one", panel_type="info", use_markdown=True)
```

Panel types: `"info"`, `"success"`, `"warning"`, `"error"`.

##### `table(headers, rows, title="", full_width=True, cell_padding=1, zebra_stripes=False, show_header=True, show_cursor=True, cursor_type="row", row_height=1, flex_column=None)`
Shows a table with consistent styling. Preferred over mounting the `Table` widget manually.

```python
ctx.textual.table(headers=["Name", "Value"], rows=[["foo", "bar"]])
ctx.textual.table(headers=headers, rows=rows, title="Results", row_height=2)
```

**`flex_column` — tables with one long column.** By default every column is as wide as its
widest cell, so a column holding long text (an issue title, a file path, a commit message)
pushes the columns after it off screen and the reader has to scroll sideways to see them.
Pass the index of that column as `flex_column`: it takes whatever width the other columns
leave, its text is folded into that width keeping its styles, and each row grows as tall as
it needs. Rows are re-folded when the terminal is resized.

```python
# "Issue" holds class + method + exception message; Events and Users stay visible.
ctx.textual.table(
    headers=["#", "Issue", "Events", "Users"],
    rows=rows,
    flex_column=1,
)
```

Do not combine it with `row_height`: heights are computed per row (`row_height` acts only as
a floor). Fixing the column width instead of using this would not help — Textual's
`DataTable` crops a fixed-width cell, with no ellipsis, and ignores the extra lines of a
tall row.

##### `collapsible_list(entries: List[CollapsibleEntry], classes: str = "")`
A list of expandable rows: one summary line each, detail behind the fold. Use it for
list+detail content — log events, review findings, anything where the rows are scanned
and only a few are opened.

```python
from titan_cli.ui.tui.widgets import CollapsibleEntry, escape_markup

ctx.textual.collapsible_list([
    CollapsibleEntry(
        title="POST /login",
        right="240ms",                        # anchored to the right edge of the row
        body=[escape_markup(response_body)],  # str, Rich markup, or any Rich renderable
        copy_text=response_body,              # adds a ⧉ button; omit for no button
        copy_label="response body",           # named in the "Copied …" confirmation
        children=[CollapsibleEntry(title="headers", body=[headers])],
    ),
    CollapsibleEntry(title="a row with nothing to expand"),  # renders as a plain line
])
```

Behaviour worth knowing:

- **Titles fit the row width** and re-fit on resize, with the cut marked by `…`. The title
  gets every column the `right` block and the copy button do not.
- **Children of a collapsed row are built when it is first opened.** Building a large tree
  up front costs thousands of widgets and seconds before the first frame, all for detail
  that starts hidden.
- **An entry with no `body` and no `children` renders as a plain line**, not a triangle
  that opens onto nothing.
- **`body_colour`** (default `#d8d8d8`) is inherited by children. Body text would otherwise
  take the output panel's green and read as status rather than as data.
- **Content from outside must go through `escape_markup()`** — payloads containing
  `[MOBILE, LANDLINE]` or `[/bold]` otherwise vanish or raise.
- **Copy uses a local clipboard helper first** (`wl-copy`/`xclip`/`xsel`/`pbcopy`) and OSC 52
  only as a fallback, since many terminals silently ignore the escape. The notification says
  which route was taken.

To build the tree without mounting it — to nest it inside your own container — use
`build_collapsible_list(entries)` from `titan_cli.ui.tui.widgets` and mount it yourself.

##### `show_diff_stat(formatted_files, formatted_summary, title="Changes summary:", use_panel=False)`
Renders a formatted `git diff --stat` display. Use alongside `format_diff_stat_display()` from `titan_plugin_git.operations`.

```python
from titan_plugin_git.operations import format_diff_stat_display

formatted_files, formatted_summary = format_diff_stat_display(stat_output)
ctx.textual.show_diff_stat(formatted_files, formatted_summary, "Changes in branch:")
ctx.textual.show_diff_stat(formatted_files, formatted_summary, "Changes made:", use_panel=True)
```

##### `mount(widget: Widget)`
Mounts any Textual widget to the output panel. Use for custom widgets; for panels and tables prefer the `panel()` / `table()` convenience methods above.

```python
from titan_cli.ui.tui.widgets import DimItalicText

ctx.textual.mount(DimItalicText("Secondary emphasis"))
```

##### `begin_step(title: str)`
Marks the beginning of a step (shows step header).

```python
ctx.textual.begin_step("Fetching PR Comments")
```

##### `end_step(status: str)`
Marks the end of a step. Status can be "success", "error", or "skip".

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

**WorkflowResult Types:**
- `Success(message, metadata={})` - Step completed successfully, continue workflow
- `Error(message)` - Step failed, stop workflow
- `Skip(message)` - Step was skipped, continue workflow
- `Exit(message)` - Exit workflow early in a controlled way (not an error)

```python
# Example: Exit when no data found (not an error, just nothing to do)
if not data:
    ctx.textual.dim_text("No data found")
    ctx.textual.end_step("success")  # ← Step itself succeeded
    return Exit("No data to process")  # ← But exit the workflow

# Example: User cancelled (skip this step)
if not user_confirmed:
    ctx.textual.warning_text("User cancelled")
    ctx.textual.end_step("skip")  # ← Mark as skipped
    return Exit("User cancelled")  # ← Exit the workflow
```

##### `scroll_to_end()`
Manually scrolls to the bottom of the output (rarely needed, see [Scroll Behavior Guidelines](textual.md#scroll-behavior-guidelines)).

```python
# Only use when showing large content + interactive widget immediately after
ctx.textual.markdown(very_large_content)
ctx.textual.scroll_to_end()  # Ensure user sees the next widget
choice = ctx.textual.ask_choice("What to do?", options)
```

### Interactive Methods (User Input)

#### `ask_text(question: str, default: str = "") -> Optional[str]`
Requests single-line text input from user (blocks until response).

```python
title = ctx.textual.ask_text("Enter PR title:", default="")
if not title:
    return Error("Title cannot be empty")
```

#### `ask_password(question: str) -> Optional[str]`
Requests a password/secret with hidden input (blocks until response). Raises `KeyboardInterrupt` if the user presses Escape.

```python
passphrase = ctx.textual.ask_password("Enter GPG passphrase:")
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

#### What every `ask_*` does when the user quits mid-prompt

They raise `WorkflowAborted` (from `titan_cli.core.interrupt`), which unwinds the
workflow thread. They do **not** return their default. `default` is what the prompt
offers the user, never an answer given on the user's behalf: a step that kept running
after the TUI closed would act on invented answers with nobody watching — that is how
quitting at "Export report as PDF?" (`default=True`) still wrote a PDF file.

Steps need no handling for it. `WorkflowAborted` is a `BaseException`, so the
`except Exception` that turns step failures into `Error` results does not catch it; it
reaches `workflow_execution.py`, which logs `workflow_aborted_on_app_exit` and lets the
thread die. Two consequences worth knowing when you write a step:

- Cleanup in an `except Exception` block will **not** run on abort. Put anything that
  must always run in `finally`.
- Later steps do not run either, so the `Skip`/`Exit` cleanup pattern does not save you
  here. This has always been true of aborts (see `run_interruptible` for blocking AI and
  CLI calls); prompts now follow the same rule.

#### `ask_multiselect(question: str, options: List[SelectionOption]) -> List[Any]`
Shows a multi-select list (spacebar to toggle, Enter to confirm).

```python
from titan_cli.ui.tui.widgets import SelectionOption

options = [
    SelectionOption(value="feature1", label="Feature 1"),
    SelectionOption(value="feature2", label="Feature 2", selected=True),
]

selected = ctx.textual.ask_multiselect("Select features:", options)
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
Shows a styled option list with titles and descriptions (like workflow selection menu).

```python
from titan_cli.engine import OptionItem  # canonical import (widgets re-export is backward-compat)

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

### AI Content Review Flows

#### `ai_content_review_flow(content_title, content_body, ...) -> tuple[str, Optional[str], Optional[str]]`
Generic Use/Edit/Reject flow for reviewing AI-generated title + body content (PRs, issues, etc.). Shows a preview, offers three choices, and handles the edit loop.

Optional keyword args: `header_text`, `title_label`, `description_label`, `edit_instruction`, `confirm_question`, `choice_question`.

Returns `(choice, final_title, final_body)` where `choice` is `"use"`, `"edit"`, or `"reject"` (title/body are `None` on reject).

```python
choice, title, body = ctx.textual.ai_content_review_flow(
    content_title="feat: Add dark mode support",
    content_body="## Summary\n- Implemented theme switcher...",
    header_text="AI-Generated PR",
    title_label="PR Title:",
    description_label="PR Description:",
)

if choice == "reject":
    return Skip("User rejected AI content")
```

#### `ai_document_review_flow(document_title, document_content, ...) -> tuple[str, Optional[str]]`
Same Use/Edit/Reject flow for single long-form documents (release notes, reports). Uses a panel to preserve line breaks.

Optional keyword args: `header_text`, `title_label`, `edit_instruction`, `confirm_question`, `choice_question`.

Returns `(choice, final_content)`.

```python
choice, content = ctx.textual.ai_document_review_flow(
    document_title="Release Notes v26.8",
    document_content="# 26.8\n\n## Features\n- ...",
)
```
