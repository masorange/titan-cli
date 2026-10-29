# DEVELOPMENT.md

> High-Level Architecture Overview for Titan CLI

**For architecture rules and the task guides, see [AGENTS.md](AGENTS.md).**

---

## 🛠️ Development Setup

> **Important:** This guide is for contributors who want to develop Titan CLI. If you just want to use Titan, see [README.md](README.md) for user installation.

### Prerequisites

- Python 3.11+
- `poetry` (dependency management)
- `pipx` (optional, for production version)

### Installation for Development

```bash
# 1. Clone the repository
git clone https://github.com/masorange/titan-cli.git
cd titan-cli

# 2. Install dependencies and create titan-dev launcher
make dev-install

# 3. Verify installation
titan-dev --version
```

**What this does:**
- Installs all dependencies with Poetry in a local virtualenv (`.venv/`)
- Creates a `~/.local/bin/titan-dev` script that points to your local codebase
- Allows you to test changes immediately without reinstalling

**Note:** The `titan-dev` command is **only for developers**. End users who install from PyPI with `pipx install titan-cli` only get the `titan` command.

### Initial Configuration

After installation, configure Titan for your projects:

```bash
# 1. Navigate to your projects directory (parent of all your projects)
cd ~/projects  # or wherever you keep your projects

# 2. Launch Titan interactive menu
titan

# 3. Follow the setup wizard:
#    - Set project root (e.g., ~/projects)
#    - Configure a project from the "Project Management" menu
#    - Install plugins from the "Plugin Management" menu
#      (plugins will be installed from local ./plugins/ directory automatically)
```

**Note:** With editable installation (`-e` flag), Titan will automatically detect local plugins in the repository and install them from there. No need to manually inject plugins.

---

## 🎨 UI Architecture

The TUI is built with Textual (`titan_cli/ui/tui/`: `screens/`, `widgets/`,
`textual_components.py`). Steps draw through the `ctx.textual` API, never Textual directly.

See the [Textual guide](.claude/docs/textual.md) for step structure and scrolling rules (it links the API and widget references), and
[AGENTS.md](AGENTS.md) for the rest of the guides.
