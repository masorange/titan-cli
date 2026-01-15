# Titan CLI

> Development Tools Orchestrator

Titan CLI is a modular development tools orchestrator that streamlines your workflow through plugins, configuration management, and an intuitive terminal UI.

## ✨ Features

- 🔧 **Project Configuration Management** - Centralized `.titan/config.toml` for project settings
- 🔌 **Plugin System** - Extend functionality via entry points (GitHub, Git, Jira, AI)
- 🎨 **Rich Terminal UI** - Theme-aware components for beautiful CLI experiences
- 🤖 **AI Integration** - Optional AI assistance for code reviews and automation
- ⚡ **Workflow Engine** - Compose atomic steps into powerful workflows

## 🚀 Quick Start

### Installation

```bash
# Install with pipx (recommended)
pipx install titan-cli

# Or with pip
pip install titan-cli
```

### Basic Usage

```bash
# Initialize global configuration
titan init

# List available projects
titan projects list

# Preview UI components
titan preview panel
titan preview menu
```

## 🔌 Plugin Marketplace

Titan CLI features a plugin marketplace that makes it easy to discover and install plugins directly from GitHub.

### Browse & Install Plugins

```bash
# Interactive marketplace (recommended)
titan plugins discover

# Or install directly by name
titan plugins install git
titan plugins install github
titan plugins install jira
```

### Plugin Management

```bash
# List installed plugins
titan plugins list

# Update a plugin
titan plugins update git

# Update all plugins
titan plugins update --all

# Uninstall a plugin
titan plugins uninstall jira

# Get plugin info
titan plugins info github
```

### Available Official Plugins

- **git** - Git operations and repository management
- **github** - GitHub integration with AI-powered PR descriptions
- **jira** - JIRA issue tracking with AI-powered requirements analysis

All plugins feature:
- ✅ Automatic configuration wizard on first install
- ✅ Project-level installation (`.titan/plugins/`)
- ✅ Secure secret management via OS keyring
- ✅ Dynamic JSON Schema-based configuration

## 📚 Documentation

- **For AI Agents & Contributors**: See [AGENTS.md](AGENTS.md)
- **For Development**: See [DEVELOPMENT.md](DEVELOPMENT.md)
- **For Guides**: See [docs/guides/](docs/guides/)

## 🤝 Contributing

Contributions are welcome! Please see [AGENTS.md](AGENTS.md) for:
- Development setup
- Code style guidelines
- Testing requirements
- UI component patterns

## 📄 License

MIT License - see [LICENSE](LICENSE) for details

## 🙏 Acknowledgments

Built with:
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Rich](https://rich.readthedocs.io/) - Terminal UI
- [Pydantic](https://docs.pydantic.dev/) - Data validation
