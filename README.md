# Titan CLI

> Modular development tools orchestrator - Streamline your workflows with AI integration and intuitive terminal UI

Titan CLI is a powerful command-line orchestrator that automates Git, GitHub, JIRA workflows through an extensible plugin system with optional AI assistance.

## ✨ Features

- 🔧 **Project Configuration** - Centralized `.titan/config.toml` for project-specific settings
- 🔌 **Plugin System** - Extend functionality with Git, GitHub, JIRA, and custom plugins
- 🎨 **Modern TUI** - Beautiful terminal interface powered by Textual
- 🤖 **AI Integration** - Optional AI assistance (Claude & Gemini) for commits, PRs, and analysis
- ⚡ **Workflow Engine** - Compose atomic steps into powerful automated workflows
- 🔐 **Secure Secrets** - OS keyring integration for API tokens and credentials

## 📦 Installation

### For Users (Recommended)

```bash
# Install with pipx (isolated environment)
pipx install titan-cli

# Verify installation
titan --version

# Launch Titan
titan
```

**Note:** This installs the stable production version. You only get the `titan` command.

### For Contributors (Development Setup)

**See [DEVELOPMENT.md](DEVELOPMENT.md) for complete development setup.**

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

**Note:** Development setup creates a `titan-dev` command that runs from your local codebase, allowing you to test changes immediately. This command is **not available** to end users who install from PyPI.

## 🚀 Quick Start

### First Time Setup

```bash
# Launch Titan (runs setup wizards on first launch)
titan
```

On first run, Titan will guide you through:
1. **Global Setup** - Configure AI providers (optional)
2. **Project Setup** - Enable plugins and configure project settings

### Basic Usage

```bash
# Launch interactive TUI
titan

# Or run specific workflows
titan workflow run <workflow-name>
```

## 🔌 Built-in Plugins

Titan CLI v1.0.0 includes three core plugins:

- **Git Plugin** - Smart commits, branch management, AI-powered commit messages
- **GitHub Plugin** - Create PRs with AI descriptions, manage issues, code reviews
- **JIRA Plugin** - Search issues, AI-powered analysis, workflow automation

## 🤖 AI Integration

Titan supports multiple AI providers:

- **Anthropic Claude** (Sonnet, Opus, Haiku)
- **Google Gemini** (Pro, Flash)

Configure during first setup or later via the TUI settings.

## 📚 Documentation

- **Contributing**: See [DEVELOPMENT.md](DEVELOPMENT.md)
- **AI Agent Guide**: See [CLAUDE.md](CLAUDE.md)
- **Release History**: See [GitHub Releases](https://github.com/masorange/titan-cli/releases)

## 🤝 Contributing

Contributions are welcome! See [DEVELOPMENT.md](DEVELOPMENT.md) for:
- Development setup
- Code style guidelines
- Testing requirements
- Architecture overview

## 📄 License

MIT License - see [LICENSE](LICENSE) for details

## 🙏 Acknowledgments

Built with:
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Textual](https://textual.textualize.io/) - Terminal UI framework
- [Pydantic](https://docs.pydantic.dev/) - Data validation
- [Poetry](https://python-poetry.org/) - Dependency management
