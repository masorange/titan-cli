# Development Setup Guide

> **Audience:** Contributors and developers working on Titan CLI codebase

> **For end users:** See [README.md](../../README.md) for installation instructions

---

## 🎯 Overview

When developing Titan CLI, you can run two versions side-by-side:

- **`titan`** - Production version (stable release from PyPI via `pipx install titan-cli`)
- **`titan-dev`** - Development version (your local codebase)

**Important:** The `titan-dev` command is **only for contributors** who clone the repository. It is NOT included in the PyPI package and is NOT available to end users.

This setup allows you to:
- Use stable `titan` for your daily work
- Test changes with `titan-dev` without breaking your workflow
- Switch between versions easily

---

## 📊 Command Availability

| Command | End Users (PyPI) | Contributors (Repo) | How to Get |
|---------|-----------------|---------------------|------------|
| `titan` | ✅ Available | ✅ Available (optional) | `pipx install titan-cli` |
| `titan-dev` | ❌ Not available | ✅ Available | `make dev-install` (repo only) |

**Key points:**
- ✅ `titan` is the production command, available to everyone via PyPI
- ✅ `titan-dev` is ONLY for contributors who clone the repository
- ❌ `titan-dev` is NOT included in the PyPI package
- ⚠️ Both commands share the same config (`~/.titan/config.toml`)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         END USERS (PyPI)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  $ pipx install titan-cli                                      │
│                                                                 │
│  ~/.local/bin/titan ──────┐                                    │
│                           │                                     │
│                           ▼                                     │
│            ~/.local/share/pipx/venvs/titan-cli/bin/titan       │
│                                                                 │
│  ✅ Can use: titan                                             │
│  ❌ Cannot use: titan-dev (doesn't exist)                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    CONTRIBUTORS (Repository)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  $ git clone https://github.com/masorange/titan-cli.git       │
│  $ cd titan-cli                                                │
│  $ make dev-install                                            │
│                                                                 │
│  ~/.local/bin/titan-dev ──────┐                               │
│                               │                                 │
│                               ▼                                 │
│                  ~/git/titan-cli/.venv/bin/titan               │
│                               │                                 │
│                               ▼                                 │
│                  ~/git/titan-cli/titan_cli/  (source code)     │
│                                                                 │
│  Optional (if also installed for daily use):                   │
│  ~/.local/bin/titan ─────> pipx installation                   │
│                                                                 │
│  ✅ Can use: titan-dev (local changes)                         │
│  ✅ Can use: titan (stable, optional)                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 Installation

### Prerequisites

- Python 3.10+
- `pipx` (recommended) or `pip`
- `poetry` (for dependency management)

```bash
# Install pipx if not already installed
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Install poetry
pipx install poetry
```

### 1️⃣ Production Installation (Optional)

Install the stable version from PyPI:

```bash
pipx install titan-cli
```

Verify:
```bash
titan --version
```

**Where it lives:**
- Binary: `~/.local/bin/titan` → `~/.local/share/pipx/venvs/titan-cli/bin/titan`
- Config: `~/.titan/config.toml`
- State: `~/.local/state/titan/` (logs, cache)

### 2️⃣ Development Installation (Required)

Clone the repository and set up the development environment:

```bash
# 1. Clone repository
git clone https://github.com/masorange/titan-cli.git
cd titan-cli

# 2. Install dependencies with Poetry
poetry install

# 3. Create titan-dev launcher (automated)
make dev-install

# OR manually create the script:
cat > ~/.local/bin/titan-dev <<'EOF'
#!/bin/bash
# titan-dev - Development version of Titan CLI
REPO_PATH="$HOME/git/titan-cli"  # Adjust to your clone path
exec "$REPO_PATH/.venv/bin/titan" "$@"
EOF
chmod +x ~/.local/bin/titan-dev

# 4. Verify installation
titan-dev --version
```

**Where it lives:**
- Source: `~/git/titan-cli/` (or your clone location)
- Virtualenv: `~/git/titan-cli/.venv/`
- Binary: `~/.local/bin/titan-dev` (wrapper script)
- Config: `./.titan/config.toml` (in each project)

---

## 🔧 Development Workflow

### Running Titan in Development Mode

```bash
# Option 1: Use titan-dev alias (recommended)
titan-dev

# Option 2: Use poetry run
cd ~/git/titan-cli
poetry run titan

# Option 3: Activate virtualenv and run directly
cd ~/git/titan-cli
poetry shell
titan
```

### Development vs Production Separation

**Key differences:**

| Aspect | Production (`titan`) | Development (`titan-dev`) |
|--------|---------------------|---------------------------|
| **Command** | `titan` | `titan-dev` |
| **Source** | Installed package | Local codebase |
| **Updates** | `pipx upgrade titan-cli` | `git pull` |
| **Plugins** | Installed separately | Included in repo |
| **Config** | `~/.titan/config.toml` | Uses same config |
| **Logs** | `~/.local/state/titan/logs/` | Same location |

**IMPORTANT:** Both versions share the same configuration directory (`~/.titan/`) and project configs (`./.titan/`). Be careful when testing breaking config changes.

### Recommended Setup for Development

1. **Use separate test projects** for development:
   ```bash
   mkdir ~/titan-test-projects
   cd ~/titan-test-projects
   git clone <some-test-repo>
   cd <test-repo>
   titan-dev  # Test your changes here
   ```

2. **Keep production titan for real work**:
   ```bash
   cd ~/work/production-project
   titan  # Use stable version for critical work
   ```

---

## 🧪 Testing Changes

### Quick Test Loop

```bash
# 1. Make changes to code
vim ~/git/titan-cli/titan_cli/some_file.py

# 2. Test immediately (no reinstall needed with poetry)
titan-dev

# 3. Run unit tests
cd ~/git/titan-cli
poetry run pytest

# 4. Run specific plugin tests
poetry run pytest plugins/titan-plugin-git/tests/
```

### Testing with Different Environments

**Test with different Python versions:**
```bash
# Use pyenv to switch Python versions
pyenv install 3.10.0
pyenv local 3.10.0
poetry env use 3.10.0
poetry install
```

**Test with fresh config:**
```bash
# Temporarily rename your config
mv ~/.titan ~/.titan.backup
titan-dev  # Will run first-time setup

# Restore when done
rm -rf ~/.titan
mv ~/.titan.backup ~/.titan
```

---

## 🔍 Debugging

### Development Mode Logging

Enable verbose logging for debugging:

```bash
# When logging architecture is implemented:
titan-dev --debug
titan-dev --verbose
TITAN_DEBUG=1 titan-dev
```

**Future:** When logging is implemented (see architecture proposal), logs will be at:
- `~/.local/state/titan/logs/titan.log` (JSON, rotating)
- Console (colorized when `--verbose` or `--debug`)

### Textual Devtools (TUI Debugging)

For debugging the Textual TUI:

```bash
# Terminal 1: Start devtools console
textual console

# Terminal 2: Run titan-dev
cd ~/git/titan-cli
textual run --dev titan_cli/ui/tui/textual_workflow_executor.py TitanApp

# Logs will appear in Terminal 1
```

See: [Textual Devtools Guide](https://textual.textualize.io/guide/devtools/)

---

## 📁 Project Structure (Development)

```
~/git/titan-cli/                    # Development repository
├── .venv/                          # Poetry virtualenv
│   └── bin/titan                   # Development binary
├── titan_cli/                      # Main package
├── plugins/                        # Built-in plugins
│   ├── titan-plugin-git/
│   ├── titan-plugin-github/
│   └── titan-plugin-jira/
├── tests/                          # Unit tests
├── .claude/                        # Claude Code docs
├── pyproject.toml                  # Poetry config
└── poetry.lock                     # Locked dependencies

~/.local/bin/
├── titan -> ~/.local/share/pipx/venvs/titan-cli/bin/titan  # Production
└── titan-dev                       # Development wrapper script

~/.titan/
└── config.toml                     # Global config (shared)

~/.local/state/titan/               # Runtime data (future)
└── logs/
    └── titan.log                   # Application logs
```

---

## 🚀 Releasing Changes

### Development to Production Flow

```bash
# 1. Develop and test with titan-dev
titan-dev  # Test your changes

# 2. Run full test suite
cd ~/git/titan-cli
poetry run pytest
poetry run pytest --cov

# 3. Update version in pyproject.toml
# Follow semantic versioning

# 4. Create release (maintainers only)
git tag v0.1.12
git push origin v0.1.12

# 5. Build and publish (CI/CD or manual)
poetry build
poetry publish

# 6. Upgrade production version
pipx upgrade titan-cli
```

---

## 🛠️ Troubleshooting

### `titan-dev` not found

```bash
# Check if script exists
ls -la ~/.local/bin/titan-dev

# If not, create it manually
make dev-install

# Ensure ~/.local/bin is in PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Changes not reflected in `titan-dev`

```bash
# Ensure you're using editable install
cd ~/git/titan-cli
poetry install

# Verify virtualenv is active
which titan-dev
# Should show: ~/.local/bin/titan-dev

titan-dev --version
# Should show version from pyproject.toml
```

### Plugin changes not working

```bash
# Plugins are editable by default in Poetry
# Verify in pyproject.toml:
#   [tool.poetry.group.dev.dependencies]
#   titan-plugin-git = {path = "plugins/titan-plugin-git", develop = true}

# If needed, reinstall plugins
cd ~/git/titan-cli
poetry install
```

### Want to test a specific branch

```bash
cd ~/git/titan-cli
git checkout feature/my-feature
poetry install  # Reinstall deps if changed
titan-dev  # Now uses the feature branch
```

---

## 📚 Related Documentation

- [CLAUDE.md](../../CLAUDE.md) - AI development guide
- [DEVELOPMENT.md](../../DEVELOPMENT.md) - Architecture overview
- [Plugin Architecture](.claude/docs/plugin-architecture.md) - Plugin development
- [Textual Guide](.claude/docs/textual.md) - TUI development

---

**Last updated:** 2026-02-17
