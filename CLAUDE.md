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

Configuration is located at `~/.titan/config.toml`:

```toml
[ai]
provider = "anthropic"  # or "gemini"
model = "claude-sonnet-4-5"

[github]
token = "ghp_..."

[jira]
base_url = "https://your-domain.atlassian.net"
email = "user@example.com"
api_token = "..."
```

## Main Commands

```bash
# Launch interactive TUI
titan

# Run specific workflow
titan run <workflow-name>

# List available workflows
titan list

# Configure AI providers
titan config ai
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

**Branch**: `feat/analize_jira_textual`
**Main Branch**: `master`

## Additional Resources

- **Textual Documentation**: https://textual.textualize.io/
- **Anthropic API**: https://docs.anthropic.com/
- **Google GenAI**: https://ai.google.dev/

---

**Last updated**: 2026-01-19
