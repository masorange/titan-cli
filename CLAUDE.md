# Titan CLI - Claude Development Guide

Documentation for the Titan CLI project to assist Claude in development.

## Project Overview

Titan CLI is a command-line tool with a Textual-based TUI (Terminal User Interface) that enables automated workflows for Git, GitHub, Jira, and other services, with AI integration for intelligent assistance.

## Architecture

### Main Components

```
titan-cli/
├── titan_cli/                 # Core application
│   ├── engine/               # Workflow engine
│   ├── ui/tui/              # Textual TUI interface
│   │   ├── screens/         # TUI screens
│   │   ├── widgets/         # Custom widgets
│   │   ├── textual_components.py  # API for steps
│   │   └── textual_workflow_executor.py
│   └── external_cli/        # External CLI integration
│
└── plugins/                  # Plugin system
    ├── titan-plugin-git/    # Git plugin
    ├── titan-plugin-github/ # GitHub plugin
    ├── titan-plugin-jira/   # Jira plugin
    └── ...
```

### Workflow Framework

Workflows are defined in YAML files and executed through steps that can:
- Execute Git commands
- Interact with APIs (GitHub, Jira, etc.)
- Request user input
- Use AI to generate content
- Display information in the TUI

## Technical Documentation

### Workflow Steps Development

To create new workflow steps using the Textual TUI framework:

**📖 [Textual Workflow Steps Development Guide](.claude/docs/textual.md)**

This guide includes:
- Basic step structure
- Complete `ctx.textual` API reference
- Available widgets (Panel, Table, etc.)
- Complete usage examples
- Code file references
- Scroll behavior guidelines

### Common Pitfalls ⚠️

**1. Step Function Naming Mismatch**

The function name in your Python file MUST match the `step:` field in the YAML workflow exactly.

❌ **WRONG**:
```python
# File: .titan/steps/my_step.py
def my_step_function(ctx: WorkflowContext) -> WorkflowResult:
    ...
```
```yaml
# Workflow YAML
- plugin: project
  step: my_step  # ← This won't find the function!
```

✅ **CORRECT**:
```python
# File: .titan/steps/my_step.py
def my_step(ctx: WorkflowContext) -> WorkflowResult:  # ← Exact match
    ...
```
```yaml
# Workflow YAML
- plugin: project
  step: my_step  # ← Found!
```

**Convention**: Don't add `_step` suffix to function names in project steps. The function name IS the step name.

### Scroll Behavior Guidelines

**IMPORTANT: Scroll management rules for consistent UX**

1. **Widgets NEVER auto-scroll**
   - Custom widgets (Panel, Markdown, etc.) must NOT call scroll methods
   - Prevents conflicts and unpredictable scroll behavior

2. **Steps CAN manually scroll (rarely)**
   - Only use `ctx.textual.scroll_to_end()` when:
     - Step displays very large content (exceeds full screen)
     - AND needs to show interactive widget immediately after
   - Example: Large PR description → scroll → show Use/Edit/Reject buttons

3. **Screen ALWAYS auto-scrolls on step completion**
   - Happens automatically when `ctx.textual.end_step()` is called
   - Default behavior - no action needed from step developers
   - Redundant if step already scrolled, but safe

**Default approach:** Don't use manual scroll - let the screen handle it automatically.

### Plugins

Each plugin is an independent Python package that can register:
- **Steps**: Functions that implement workflow logic
- **Workflows**: YAML files with step sequences
- **Clients**: Wrappers for external APIs (GitHub, Jira, etc.)
- **AI Agents**: Specialized logic for LLM analysis

#### Plugin Structure

```
titan-plugin-{name}/
├── titan_plugin_{name}/
│   ├── steps/          # Workflow steps
│   ├── workflows/      # YAML definitions
│   ├── clients/        # API clients (optional)
│   ├── agents/         # AI agents (optional)
│   └── plugin.py       # Plugin registration
└── pyproject.toml
```

## Tech Stack

- **Python 3.11+**
- **Textual**: TUI framework
- **Anthropic SDK**: Claude integration
- **Google GenAI SDK**: Gemini integration
- **PyGithub**: GitHub API client
- **Requests**: HTTP client for APIs

## Project Setup

### Development Installation

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install plugins
pip install -e plugins/titan-plugin-git
pip install -e plugins/titan-plugin-github
pip install -e plugins/titan-plugin-jira
```

### Configuration

Titan uses a two-level configuration system:

1. **Global Configuration** (`~/.titan/config.toml`):
   - AI provider settings (shared across all projects)
   - Global preferences

2. **Project Configuration** (`./.titan/config.toml` in each project):
   - Project name and settings
   - Plugin enablement (per project)
   - Plugin configuration (per project)

**Important:** Titan must be run from within a project directory. It no longer uses a global `project_root` setting.

Example global config:
```toml
[ai.providers.default]
name = "My Claude"
type = "individual"
provider = "anthropic"
model = "claude-sonnet-4-5"

[ai]
default = "default"
```

Example project config:
```toml
[project]
name = "my-awesome-project"

[plugins.git]
enabled = true

[plugins.github]
enabled = true
```

## Main Commands

```bash
# Launch interactive TUI (run from project directory)
cd /path/to/your/project
titan

# First run will show:
# 1. Global setup wizard (if ~/.titan/config.toml doesn't exist)
# 2. Project setup wizard (if ./.titan/config.toml doesn't exist)

# After setup, the main menu will appear with options for:
# - Workflows
# - Plugin management
# - AI configuration
# - External CLI tools

# Other commands:
titan version           # Show version
titan tui               # Explicitly launch TUI

# Development (from repo):
poetry run titan        # Run from source
```

## Current Project Status

### Completed ✅

- ✅ Workflow framework with engine
- ✅ Textual-based TUI
- ✅ Git plugin (commits, branches, etc.)
- ✅ GitHub plugin (PRs, issues with AI)
- ✅ Jira plugin (search, AI-powered analysis)
- ✅ Claude integration (Anthropic)
- ✅ Gemini integration (Google)
- ✅ All workflow steps migrated to Textual

### Features

- **Declarative Workflows**: Define flows in YAML
- **Integrated AI**: Use Claude or Gemini to generate commit messages, PR descriptions, issue analysis
- **Interactive TUI**: Modern interface with Textual
- **Extensible**: Plugin system
- **Multi-Provider**: Supports multiple AI providers

## Recent Important Commits

- `75050d4`: feat(jira): add JiraAgent with AI-powered issue analysis and customizable Jinja2 templates
- `a63e0ab`: Migrate git and github plugin steps to new Textual context
- `45d82cb`: Migrate git and github workflows to textual TUI framework
- `e3d6889`: Migrate create pull request step to textual TUI components

## Current Branch

**Branch**: `master`
**Main Branch**: `master`

## Recent Architecture Changes

### Project-Based Configuration (2026-01-19)

Titan has been redesigned to work on a per-project basis:

- **Removed**: Global `project_root` and `active_project` settings from `[core]` configuration
- **New Flow**: Titan must be run from within a project directory
- **Global Config**: Now only stores AI provider settings (shared across projects)
- **Project Config**: Each project has its own `.titan/config.toml` with:
  - Project name
  - Enabled plugins
  - Plugin-specific configuration

### Setup Wizards

Two new wizards guide users through initial setup:

1. **Global Setup Wizard**: Runs on first launch (when `~/.titan/config.toml` doesn't exist)
   - Welcome screen
   - Optional AI configuration
   - Creates global configuration

2. **Project Setup Wizard**: Runs when Titan is launched in an unconfigured directory
   - Detects project type (Git repo, etc.)
   - Project naming
   - Plugin selection
   - Creates `.titan/config.toml` in project directory

### Migration Notes

- Old configurations with `[core]` settings will still load but those fields are ignored
- The application uses exclusively the Textual TUI framework for all user interaction

## Additional Resources

- **Textual Documentation**: https://textual.textualize.io/
- **Anthropic API**: https://docs.anthropic.com/
- **Google GenAI**: https://ai.google.dev/

---

**Last updated**: 2026-02-05
