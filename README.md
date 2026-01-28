# Titan CLI

> Development Tools Orchestrator

Titan CLI is a modular development tools orchestrator that streamlines your workflow through plugins, configuration management, and an intuitive terminal UI.

## ✨ Features

- 🔧 **Project Configuration Management** - Centralized `.titan/config.toml` for project settings
- 🔌 **Plugin System** - Extend functionality via entry points (GitHub, Git, Jira, AI)
- 🎨 **Modern TUI** - Beautiful terminal interface powered by Textual
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

# Launch TUI
titan
```

## 🔌 Plugins

Extend Titan CLI with plugins:

```bash
# Install a plugin
pipx inject titan-cli titan-plugin-github

# List installed plugins
titan plugins list
```

## Available plugins:

**Not available at the moment**

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
- [Textual](https://textual.textualize.io/) - Terminal UI framework
- [Pydantic](https://docs.pydantic.dev/) - Data validation
