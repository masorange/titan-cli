# Coding Standards & Review Checklist

> Comprehensive guidelines for Titan CLI development. This document serves as the reference for code reviews and quality assurance.

---

## 📋 Table of Contents

1. [Architecture & Structure](#-architecture--structure)
2. [Plugin Development](#-plugin-development)
3. [Workflow System](#-workflow-system)
4. [UI Components](#-ui-components)
5. [Messages & i18n](#-messages--i18n)
6. [Code Style](#-code-style)
7. [Testing](#-testing)
8. [Documentation Standards](#-documentation-standards)
9. [Common Mistakes](#-common-mistakes)

---

## 🏗️ Architecture & Structure

### Layer Separation

**✅ DO:**
- Keep core logic in `core/`
- Put CLI commands in `commands/`
- Place UI components in `ui/components/` (atomic) or `ui/views/` (composite)
- Workflow execution logic goes in `engine/`

**❌ DON'T:**
- Mix business logic with UI rendering
- Put workflow logic in commands
- Create circular dependencies between layers

### Directory Structure

```
titan_cli/
├── core/               # Configuration, plugins, discovery
├── commands/           # CLI command implementations
├── ui/
│   ├── components/     # Atomic wrappers (Panel, Typography, Table)
│   └── views/          # Composite components (Banner, Prompts, Menus)
├── engine/             # Workflow orchestration
└── ai/                 # AI integration
```

---

## 🔌 Plugin Development

### Plugin Anatomy

**Required files:**
```
plugins/my-plugin/
├── pyproject.toml             # Entry point declaration
└── my_plugin/
    ├── __init__.py
    ├── plugin.py              # TitanPlugin implementation
    ├── clients/               # API/CLI wrappers
    ├── models.py              # Pydantic models
    ├── exceptions.py          # Custom exceptions
    ├── messages.py            # ⚠️ REQUIRED - All user-facing strings
    └── steps/                 # Workflow steps
```

### Entry Point

**✅ DO:**
```toml
# pyproject.toml
[project.entry-points."titan.plugins"]
my-plugin = "my_plugin.plugin:MyPlugin"
```

### Plugin Class

**✅ DO:**
```python
from titan_cli.core.plugins.plugin_base import TitanPlugin
from .messages import msg  # ⚠️ ALWAYS import messages

class MyPlugin(TitanPlugin):
    @property
    def name(self) -> str:
        return "my-plugin"

    @property
    def dependencies(self) -> list[str]:
        return ["git"]  # Declare dependencies

    def initialize(self, config: TitanConfig, secrets: SecretManager):
        # Validate config with Pydantic
        validated_config = MyPluginConfig(**plugin_config_data)
        self.client = MyClient(validated_config.field)

    def get_config_schema(self) -> dict:
        return MyPluginConfig.model_json_schema()

    def get_steps(self) -> dict:
        from .steps import my_step
        return {"my_step": my_step}
```

**❌ DON'T:**
- Handle initialization errors with try/except (raise them)
- Hardcode configuration values
- Skip config schema implementation

### Configuration Models

**✅ DO:**
```python
# titan_cli/core/plugins/models.py
from pydantic import BaseModel, Field

class MyPluginConfig(BaseModel):
    api_url: str = Field(..., description="API endpoint URL")
    timeout: int = Field(30, description="Request timeout in seconds")
```

**Location:** Plugin-specific config models go in `titan_cli/core/plugins/models.py`

---

## 🚀 Workflow System

### YAML Workflow Structure

**✅ DO:**
```yaml
name: "Workflow Name"
description: "Brief description"

# Optional parameters with defaults
params:
  base_branch: "main"
  draft: false

# Workflow steps
steps:
  - id: git_status
    name: "Check Git Status"
    plugin: git
    step: get_status

  # Hook injection point
  - hook: before_commit

  - id: create_commit
    name: "Create Commit"
    plugin: git
    step: create_commit
    requires:
      - commit_message  # Validate ctx.data has this key
    on_error: fail      # fail (default) | continue | skip
```

**❌ DON'T:**
- Forget to declare `requires` for dependent variables
- Use undefined hooks
- Skip `on_error` for critical steps

### Workflow Location & Precedence

1. **Project:** `.titan/workflows/*.yaml` (highest priority)
2. **User:** `~/.titan/workflows/*.yaml`
3. **System:** `titan_cli/workflows/*.yaml`
4. **Plugin:** `plugins/*/workflows/*.yaml` (lowest priority)

### Step Implementation

**Naming Convention:**
- **Step functions MUST end with `_step` suffix**
- Examples: `search_issues_step`, `create_commit_step`, `ai_analyze_issue_requirements_step`
- This distinguishes workflow steps from regular functions

**✅ DO:**
```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from ..messages import msg  # ⚠️ ALWAYS import messages

def my_step_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Brief description of what this step does.

    Requires:
        ctx.git: GitClient instance
        ctx.ui: UI components

    Outputs (saved to ctx.data):
        my_output (str): Description of output

    Returns:
        Success: If step completed
        Error: If step failed
        Skip: If step not applicable
    """
e 

    # 2. Validate requirements
    if not ctx.git:
        return Error(msg.MyPlugin.GIT_NOT_AVAILABLE)

    # 3. Execute step logic
    try:
        result = ctx.git.do_something()

        # 4. Show success (if needed for this step)
        if ctx.ui:
            ctx.ui.text.success(msg.MyPlugin.OPERATION_SUCCESS)

        # 5. Return with metadata (auto-merged into ctx.data)
        return Success("Operation completed", metadata={"my_output": result})

    except Exception as e:
        return Error(msg.MyPlugin.OPERATION_FAILED.format(error=str(e)), exception=e)
```

**❌ DON'T:**
- Print to console directly (use `ctx.ui`)
- Hardcode user-facing strings
- Forget to return WorkflowResult
- Handle exceptions without returning Error
- Skip step header if `ctx.views` is available

### Workflow Context Usage

**Available in ctx:**
```python
# Core dependencies
ctx.secrets: SecretManager

# Service clients (populated by builder)
ctx.ai: AIClient          # If .with_ai() called
ctx.git: GitClient        # If .with_git() called
ctx.github: GitHubClient  # If .with_github() called
ctx.jira: JiraClient      # If .with_jira() called

# UI components (two levels)
ctx.ui.text               # TextRenderer (titles, success, error, info)
ctx.ui.panel              # PanelRenderer (bordered panels)
ctx.ui.table              # TableRenderer (tabular data)
ctx.ui.spacer             # SpacerRenderer (vertical spacing)

ctx.views.prompts         # PromptsRenderer (ask_text, ask_confirm, etc.)
ctx.views.menu            # MenuRenderer (interactive menus)
ctx.views.step_header     # Standardized step header

# Workflow metadata (injected by executor)
ctx.workflow_name: str    # Name of current workflow
ctx.current_step: int     # Current step number (1-indexed)
ctx.total_steps: int      # Total number of steps

# Shared data storage
ctx.data: Dict[str, Any]  # Shared between steps
ctx.get(key, default)
ctx.set(key, value)
ctx.has(key)
```

**IMPORTANT: Optional Service Clients**

Service clients like `ctx.jira`, `ctx.ai`, `ctx.git`, `ctx.github` are **plugin-specific** and **optional**.

**✅ DO (when creating plugin steps):**
- Only access service clients your plugin needs
- Other plugins' service clients will be `None` - **this is expected and safe**
- You don't need to handle or check service clients from other plugins

**Example:**
```python
# JIRA plugin step - only accesses ctx.jira
def search_issues_step(ctx: WorkflowContext) -> WorkflowResult:
    if not ctx.jira:  # Check YOUR plugin's client
        return Error("JIRA client not available")

    # ctx.github might be None - that's OK, ignore it
    # ctx.ai might be None - that's OK, ignore it
    results = ctx.jira.search_issues(...)
    return Success("Found issues", metadata={"issues": results})

# GitHub plugin step - only accesses ctx.github
def create_pr_step(ctx: WorkflowContext) -> WorkflowResult:
    if not ctx.github:  # Check YOUR plugin's client
        return Error("GitHub client not available")

    # ctx.jira might be None - that's OK, ignore it
    pr = ctx.github.create_pull_request(...)
    return Success("PR created", metadata={"pr_url": pr.url})
```

**How it works:**
- The `WorkflowContextBuilder` injects service clients using `.with_jira()`, `.with_github()`, etc.
- Each plugin only requires its own client to be available
- Steps from other plugins will see `None` for clients they don't use
- This is by design - no special handling needed

---

## 🎨 UI Components

### Component vs View

**Components** (`ui/components/`):
- Pure wrappers around Rich library
- NO composition of other project components
- Examples: `PanelRenderer`, `TextRenderer`, `TableRenderer`

**Views** (`ui/views/`):
- Composite components that USE other components
- Can have business logic
- Examples: `PromptsRenderer`, `MenuRenderer`

### Creating a Component

**✅ DO:**
```python
# ui/components/my_component.py
from typing import Optional
from rich.console import Console
from ..console import get_console

class MyComponentRenderer:
    """Brief description."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or get_console()  # Theme-aware console

    def render(self, data: str) -> None:
        # Use theme styles
        self.console.print(f"[success]{data}[/success]")
```

**Create preview:**
```python
# ui/components/__previews__/my_component_preview.py
from titan_cli.ui.components.my_component import MyComponentRenderer

def preview_all():
    renderer = MyComponentRenderer()
    renderer.render("test data")

if __name__ == "__main__":
    preview_all()
```

**Add preview command:**
```python
# preview.py
@preview_app.command("my_component")
def preview_my_component():
    """Preview MyComponent."""
    runpy.run_module("titan_cli.ui.components.__previews__.my_component_preview")
```

**❌ DON'T:**
- Use `print()` instead of `console.print()`
- Hardcode colors (use theme styles)
- Compose other components in `components/` (use `views/` instead)

### Theme & Styling

**Available theme styles:**
- `success` - Bold green
- `error` - Bold red
- `warning` - Bold yellow
- `info` - Bold cyan
- `primary` - Bold blue
- `dim` - Dimmed text

**✅ DO:**
```python
from titan_cli.ui.components.typography import TextRenderer

text = TextRenderer()
text.success("Success!")
text.error("Error!")
text.body("Normal text", style="dim")

# Multi-style (inline)
text.styled_text(
    ("  1. ", "primary"),
    ("Label", "bold"),
    (" - ", "dim"),
    ("description", "dim")
)
```

**❌ DON'T:**
- Hardcode colors: `console.print("[green]text[/green]")`
- Use color names directly: `style="green"`
- Skip semantic styles

---

## 📝 Messages & i18n

### Centralized Messages

**⚠️ CRITICAL RULES:**
1. **ALL user-facing strings MUST be in `messages.py`**
2. **Message strings MUST NOT contain emojis or icons** (plain text only)

**Core messages:**
```python
# titan_cli/messages.py
class Messages:
    class UI:
        LOADING = "Loading..."  # ✅ Plain text
        DONE = "Done"

    class Prompts:
        INVALID_INPUT = "Invalid input. Please try again."

msg = Messages()
```

**Plugin messages:**
```python
# plugins/my-plugin/my_plugin/messages.py
class Messages:
    class MyPlugin:
        OPERATION_SUCCESS = "Operation completed"  # ✅ No emojis
        OPERATION_FAILED = "Operation failed: {error}"
        GIT_NOT_AVAILABLE = "Git client is not available"

    class Prompts:
        ENTER_VALUE = "Enter value:"

msg = Messages()
```

**Usage:**
```python
from ..messages import msg

# In steps
return Success(msg.MyPlugin.OPERATION_SUCCESS)
return Error(msg.MyPlugin.OPERATION_FAILED.format(error=str(e)))

# In UI
ctx.ui.text.success(msg.MyPlugin.OPERATION_SUCCESS)
prompt = ctx.views.prompts.ask_text(msg.Prompts.ENTER_VALUE)
```

**✅ DO:**
- Put ALL strings in messages.py
- Use `.format()` for variable substitution
- Group messages by category (nested classes)
- Export single `msg` instance

**❌ DON'T:**
- Hardcode strings in steps: `return Success("Done")`
- Hardcode strings in UI: `ctx.ui.text.success("Success!")`
- Scatter messages across multiple files
- Use f-strings in message definitions

---

## 🎨 Code Style

### Python Style

**Standards:**
- **Black** for formatting (line length: 88)
- **Ruff** for linting
- **Type hints** required for all function signatures
- **Docstrings** for all public classes and methods (Google style)

### Naming Conventions

- **snake_case**: files, functions, variables
- **PascalCase**: classes
- **UPPER_CASE**: constants

### Import Order

**✅ DO:**
```python
# 1. Standard library
from typing import Optional
from pathlib import Path

# 2. Third-party
from rich.console import Console
from pydantic import BaseModel

# 3. Local
from titan_cli.ui.console import get_console
from titan_cli.messages import msg
```

### Dependency Injection

**✅ DO:**
```python
class MyRenderer:
    def __init__(
        self,
        console: Optional[Console] = None,
        text_renderer: Optional[TextRenderer] = None
    ):
        self.console = console or get_console()
        self.text = text_renderer or TextRenderer(console=self.console)
```

**Why:** Enables testing with mocks

---

## 🧪 Testing

### Test Structure

```
tests/
├── commands/           # CLI command tests
├── core/               # Core logic tests
├── engine/             # Workflow engine tests
└── ui/
    ├── components/     # Component tests
    └── views/          # View tests
```

### Writing Tests

**✅ DO:**
```python
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_console():
    return MagicMock()

def test_my_component(mock_console):
    from titan_cli.ui.components.my_component import MyComponentRenderer

    renderer = MyComponentRenderer(console=mock_console)
    renderer.render("test")

    assert mock_console.print.called
    mock_console.print.assert_called_once()
```

**Running tests:**
```bash
poetry run pytest                                      # All tests
poetry run pytest --cov=titan_cli                      # With coverage
poetry run pytest tests/ui/components/test_typography.py  # Specific file
```

**❌ DON'T:**
- Skip tests for new features
- Test implementation details
- Mock everything (test real behavior when possible)

---

## 🚫 Common Mistakes

### ❌ DON'T: Use print() or console directly

**Wrong:**
```python
print("Success!")
console.print("[green]Success![/green]")
```

**Correct:**
```python
from titan_cli.ui.components.typography import TextRenderer
text = TextRenderer()
text.success("Success!")
```

### ❌ DON'T: Hardcode user-facing strings

**Wrong:**
```python
return Success("Commit created")
ctx.ui.text.success("Operation completed")
```

**Correct:**
```python
from ..messages import msg
return Success(msg.Git.COMMIT_CREATED)
ctx.ui.text.success(msg.Git.OPERATION_COMPLETED)
```

### ❌ DON'T: Mix business logic with UI

**Wrong:**
```python
def create_commit(ctx: WorkflowContext):
    ctx.ui.text.info("Creating commit...")
    result = ctx.git.commit()
    if result:
        ctx.ui.text.success("Done!")
    return Success("Commit created")
```

**Correct:**
```python
def create_commit(ctx: WorkflowContext):
    # Show step header
    if ctx.views:
        ctx.views.step_header("create_commit", ctx.current_step, ctx.total_steps)

    # Business logic
    try:
        commit_hash = ctx.git.commit()

        # Show success (if appropriate for this step)
        if ctx.ui:
            ctx.ui.text.success(msg.Git.COMMIT_CREATED)

        return Success(msg.Git.COMMIT_CREATED, metadata={"commit_hash": commit_hash})
    except Exception as e:
        return Error(msg.Git.COMMIT_FAILED.format(error=str(e)), exception=e)
```

### ❌ DON'T: Skip error handling in steps

**Wrong:**
```python
def my_step(ctx: WorkflowContext):
    result = ctx.git.do_something()  # Can raise exception
    return Success("Done")
```

**Correct:**
```python
def my_step(ctx: WorkflowContext):
    try:
        result = ctx.git.do_something()
        return Success(msg.MyPlugin.SUCCESS)
    except Exception as e:
        return Error(msg.MyPlugin.FAILED.format(error=str(e)), exception=e)
```

### ❌ DON'T: Forget to validate context requirements

**Wrong:**
```python
def my_step(ctx: WorkflowContext):
    result = ctx.git.status()  # ctx.git might be None
    return Success("Done")
```

**Correct:**
```python
def my_step(ctx: WorkflowContext):
    if not ctx.git:
        return Error(msg.MyPlugin.GIT_NOT_AVAILABLE)

    result = ctx.git.status()
    return Success(msg.MyPlugin.SUCCESS)
```

### ❌ DON'T: Handle plugin initialization errors

**Wrong:**
```python
def initialize(self, config, secrets):
    try:
        self.client = MyClient()
    except Exception as e:
        print(f"Failed to initialize: {e}")
        self.client = None
```

**Correct:**
```python
def initialize(self, config, secrets):
    # Raise exceptions - PluginRegistry will handle them
    validated_config = MyPluginConfig(**config_data)
    self.client = MyClient(validated_config.api_url)
```

### ❌ DON'T: Create components in ui/components/ that use other components

**Wrong:**
```python
# ui/components/my_component.py
class MyComponent:
    def __init__(self):
        self.text = TextRenderer()  # ❌ Composing other components
```

**Correct (move to views/):**
```python
# ui/views/my_view.py
class MyView:
    def __init__(self):
        self.text = TextRenderer()  # ✅ Views can compose components
```

---

## ✅ Pre-Commit Checklist

Before committing code, verify:

- [ ] All user-facing strings are in `messages.py`
- [ ] No hardcoded colors/styles (using theme)
- [ ] Type hints on all function signatures
- [ ] Docstrings on public classes/methods (in English)
- [ ] Step functions return `WorkflowResult` (Success/Error/Skip)
- [ ] Step headers shown if `ctx.views` available
- [ ] Context requirements validated (`ctx.git`, `ctx.ui`, etc.)
- [ ] Exceptions handled and returned as `Error`
- [ ] Tests added for new features
- [ ] Preview commands added for new UI components
- [ ] Plugin config models in `core/plugins/models.py`
- [ ] No `print()` statements (use `ctx.ui`)
- [ ] Import order correct (stdlib → third-party → local)
- [ ] Code formatted with Black
- [ ] Linting passes with Ruff
- [ ] Documentation and comments in English

---

## 📖 Documentation Standards

### AGENTS.md Structure

Every plugin and the main project **MUST** have an `AGENTS.md` file following this structure:

**Purpose:** Provide context and instructions for AI coding agents (not human developers - that's what README.md is for).

**Required Sections (in order):**

```markdown
# AGENTS.md - [Plugin/Project Name]

Documentation for AI coding agents working on [name].

---

## 📋 [Plugin/Project] Overview

- **Brief description** (1-2 paragraphs)
- **Dependencies** (other plugins/packages required)
- **Requirements** (external services, APIs, credentials)

---

## 📁 Project Structure

```
project/
├── file1.py           # Brief description
├── directory/
│   └── file2.py       # Brief description
```

---

## 🤖 Core Components

### Component 1 (`path/to/file.py`)

- Description of what it does
- Key methods/functions
- Usage examples

### Component 2 (`path/to/file.py`)

[Same pattern...]

---

## 🔧 Configuration

### Interactive Configuration
```bash
# Installation commands
```

### Manual Configuration
```toml
# Config file examples
```

---

## 🧪 Testing

**Test Structure:**
```
tests/
├── unit/
└── integration/
```

**Running Tests:**
```bash
# Test commands
```

**Test Helpers:**
- Document any test utilities
- Explain mocking patterns

---

## 🔐 Security

- Security considerations
- Secrets management
- API token handling

---

## 📚 Additional Notes

### [Subsection 1]
Important details about the project

### Extending the [Project/Plugin]
How to add new features

---

## 📝 Recent Updates

**YYYY-MM-DD:**
- ✅ Change 1
- ✅ Change 2

---

**Last Updated**: YYYY-MM-DD
**Maintainers**: @username1, @username2
```

**✅ DO:**
- Keep it focused on **what agents need to know**
- Include **build and test commands**
- Document **code style guidelines**
- Explain **security considerations**
- Provide **testing instructions**
- Include **what you'd tell a new teammate**
- Use **standard Markdown** (no special fields required)
- For monorepos: Use **nested AGENTS.md** in subdirectories
- **Write in English** (project documentation language)

**❌ DON'T:**
- Duplicate README.md content
- Include marketing/sales information
- Make it too verbose (agents have token limits)
- Forget to update the "Last Updated" date
- Skip security considerations
- Write documentation in Spanish or other languages

**Validation Checklist:**
- [ ] All required sections present
- [ ] Project structure is up to date
- [ ] Test commands are documented
- [ ] Security section covers secrets/tokens
- [ ] Recent Updates section has latest changes
- [ ] Last Updated date is current
- [ ] Maintainers list is accurate
- [ ] **Written in English**

---

## 📚 References

- [AGENTS.md](AGENTS.md) - Complete development guide
- [DEVELOPMENT.md](DEVELOPMENT.md) - High-level architecture
- [.github/pull_request_template.md](.github/pull_request_template.md) - PR template

---

## 🤖 Automated Code Review

### Claude Code Skill: `/code-review`

An automated code review skill is available for Claude Code users that checks all standards in this document.

**Location**: `.claude/skills/code-review.md` (local configuration, not in repo)

**Usage**:
```bash
/code-review          # Review uncommitted changes
/code-review HEAD     # Review last commit
/code-review HEAD~3   # Review last 3 commits
```

**Checks**:
1. 🚨 **Critical Issues** (blocking):
   - Hardcoded strings with emojis (not in messages.py)
   - Missing error handling in steps
   - Fragile AI response parsing
   - Security vulnerabilities

2. ⚠️ **Warnings** (should fix):
   - Missing input validation
   - Token tracking magic numbers
   - No docstrings
   - Missing type hints

3. 💡 **Suggestions** (optional):
   - Add unit tests
   - Extract large prompts to separate modules
   - Use type aliases for complex types
   - Add logging for debugging

**Output Format**:
```
🚨 Critical Issues: 1
⚠️ Warnings: 2
💡 Suggestions: 1
Status: ⚠️ NEEDS CHANGES
```

**Based on**: Real code review experience (PR #74, feat/release-notes-workflow)

**Benefits**:
- ✅ Catches common mistakes before PR
- ✅ Ensures consistent code quality
- ✅ Reduces review iteration time
- ✅ Teaches best practices through examples

**Note**: The skill is part of local Claude Code configuration. To use it, copy `.claude/skills/code-review.md` from a teammate or create it based on this document.

---

**Version:** 1.2.0
**Last Updated:** 2026-01-21
**Latest Addition:** Automated code review skill documentation
