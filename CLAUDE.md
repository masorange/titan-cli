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
    │   ├── operations/      # Business logic (NEW)
    │   └── steps/           # UI orchestration
    ├── titan-plugin-github/ # GitHub plugin
    │   ├── operations/      # Business logic (NEW)
    │   └── steps/           # UI orchestration
    ├── titan-plugin-jira/   # Jira plugin
    │   ├── operations/      # Business logic (NEW)
    │   └── steps/           # UI orchestration
    └── ...
```

### Plugin Architecture (5-Layer Pattern)

**All official plugins follow a 5-layer architecture (Feb 2026):**

```
Steps → Operations → Client → Services → Network
  ↓         ↓          ↓         ↓          ↓
 UI    Business    Public   Data Access   HTTP
       Logic       API
```

**📖 [Complete Plugin Architecture Guide](.claude/docs/plugin-architecture.md)** ⭐

**Key Features:**
- **Result Wrapper Pattern**: `ClientSuccess`/`ClientError` for type-safe error handling
- **Network Models**: `NetworkJiraIssue`, `NetworkGraphQLPullRequest` (faithful to APIs)
- **UI Models**: `UIJiraIssue`, `UIPullRequest` (pre-formatted for display)
- **Mappers**: Pure functions converting Network → UI
- **Services**: PRIVATE data access layer
- **Operations**: OPTIONAL business logic layer

**Quick Reference:**
- `*API` classes: HTTP/CLI communication (JiraAPI, GitHubRESTAPI)
- `Network*` models: Faithful to API responses
- `UI*` models: Optimized for rendering
- `ClientResult[T]`: Return type for all client methods

> **Note**: This architecture is for **official plugins only** (Jira, GitHub, Git). Custom user steps can use any pattern - the only requirement is `WorkflowContext → WorkflowResult`.

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

#### Modern Plugin Architecture (2026-02)

**📖 [Complete Plugin Architecture Guide](.claude/docs/plugin-architecture.md)**

Plugins now follow a **5-layer architecture** for clean separation of concerns:

```
titan-plugin-{name}/
├── titan_plugin_{name}/
│   │
│   ├── models/                    # DATA MODELS (3 sub-layers)
│   │   ├── network/              # Network layer - API responses
│   │   │   ├── rest/            # REST API models (faithful to API)
│   │   │   │   ├── user.py
│   │   │   │   ├── resource.py
│   │   │   │   └── ...
│   │   │   └── graphql/         # GraphQL models (faithful to schema)
│   │   │       ├── user.py
│   │   │       └── ...
│   │   ├── view/                # View layer - UI models
│   │   │   └── view.py          # UIResource, UIUser, etc.
│   │   ├── mappers/             # Mappers - network → view
│   │   │   ├── resource_mapper.py
│   │   │   └── ...
│   │   └── formatting.py        # Shared formatting utils
│   │
│   ├── clients/                  # CLIENT LAYER
│   │   ├── network/             # Low-level API executors
│   │   │   ├── rest_network.py  # REST executor
│   │   │   ├── graphql_network.py
│   │   │   └── queries.py       # Centralized queries
│   │   ├── services/            # Business logic services
│   │   │   ├── resource_service.py
│   │   │   └── ...
│   │   ├── protocols.py         # Interfaces (for testing)
│   │   └── {name}_client.py     # Public facade
│   │
│   ├── operations/              # OPERATIONS (pure business logic)
│   │   ├── resource_operations.py
│   │   └── ...
│   │
│   ├── steps/                   # STEPS (UI orchestration)
│   ├── workflows/               # WORKFLOWS (YAML)
│   ├── agents/                  # AI AGENTS (optional)
│   └── plugin.py
│
├── tests/
│   ├── operations/              # Unit tests for operations
│   └── ...
└── pyproject.toml
```

**Architectural Layers:**

1. **Models Layer** (3 sub-layers):
   - `network/`: Faithful to API responses (REST/GraphQL)
   - `view/`: UI-optimized (pre-calculated fields)
   - `mappers/`: Conversion logic + presentation

2. **Client Layer**:
   - `network/`: Low-level API calls
   - `services/`: Business logic + model conversion
   - Facade: Public API

3. **Operations**: Pure functions (UI-agnostic)

4. **Steps**: UI orchestration only

5. **Workflows**: Declarative flow definitions

**Key Benefits:**
- ✅ Separation of concerns (network/business/view)
- ✅ Each layer independently testable
- ✅ Faithful network models (stable when API changes)
- ✅ Optimized view models (pre-calculated for UI)
- ✅ Reusable formatters and mappers
- ✅ Hybrid REST/GraphQL where each excels

**Examples:**
- **titan-plugin-github**: REST (gh CLI) + GraphQL
- **titan-plugin-jira**: REST API (same pattern applies)
- **titan-plugin-git**: Command executor (simpler, no API models)

**IMPORTANT: Operations Pattern (see [Operations Guide](.claude/docs/operations.md))**

When creating new steps or refactoring existing ones:
1. Extract ALL business logic to `operations/`
2. Keep steps ONLY for UI orchestration
3. Write unit tests for operations (target: 100% coverage)
4. Steps should call operations and display results

## Tech Stack

- **Python 3.11+**
- **Textual**: TUI framework
- **Anthropic SDK**: Claude integration
- **Google GenAI SDK**: Gemini integration
- **PyGithub**: GitHub API client
- **Requests**: HTTP client for APIs

## Project Setup

### For Contributors (Development Mode)

**📖 [Complete Development Setup Guide](.claude/docs/development-setup.md)**

Quick start:
```bash
# Clone repository
git clone https://github.com/masorange/titan-cli.git
cd titan-cli

# Setup development environment
make dev-install

# Run development version
titan-dev
```

**What this does:**
- Installs dependencies with Poetry (`.venv/`)
- Creates `~/.local/bin/titan-dev` script pointing to local codebase
- Allows immediate testing of code changes

**Important:** The `titan-dev` command is for contributors only. End users who install from PyPI only get `titan`.

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

### For End Users

```bash
# Install from PyPI (production version)
pipx install titan-cli

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
```

### For Contributors (Development)

```bash
# Setup development environment (one-time)
make dev-install

# Run development version (uses local codebase)
titan-dev

# Alternative ways to run:
poetry run titan        # Run from poetry virtualenv
cd ~/git/titan-cli && poetry shell && titan  # Activate venv first

# Run tests
make test               # All tests
poetry run pytest       # Direct pytest
```

**Key difference:** `titan` is the production version from PyPI, `titan-dev` runs your local codebase changes.

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

## Recent Updates (2026-02-16)

### Plugin Architecture Completed ✅

All three official plugins (Git, GitHub, Jira) now follow the 5-layer architecture.

**Key improvements:**
- Pattern matching mandatory for all `ClientResult` handling
- Operations work with UI models, never dicts
- Clean docstrings (no doctest examples)
- Type-safe throughout

See **[Plugin Architecture Guide](.claude/docs/plugin-architecture.md)** for complete details.

---

**Last updated**: 2026-02-16
