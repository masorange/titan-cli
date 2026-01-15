# 📦 Titan CLI - Installation Guide

Complete installation guide for Titan CLI v1.0.0

---

## Prerequisites

- **Python 3.10+** must be installed on your system
- **pipx** for isolated CLI tool installation (recommended)

---

## Installation Methods

### Method 1: Using pipx (Recommended)

`pipx` installs Titan CLI in an isolated environment while making the `titan` command globally available.

#### Step 1: Install pipx

**macOS/Linux:**
```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

**Windows:**
```powershell
python -m pip install --user pipx
python -m pipx ensurepath
```

Close and reopen your terminal after installation.

#### Step 2: Install Titan CLI

**Core installation (no AI providers):**
```bash
pipx install titan-cli
```

**With AI support (Anthropic Claude + Google Gemini):**
```bash
pipx install titan-cli[ai]
```

**Full installation (all features):**
```bash
pipx install titan-cli[all]
```

#### Verify Installation

```bash
titan --version
# Output: Titan CLI version 1.0.0

titan --help
# Shows all available commands
```

---

### Method 2: From Source (Development)

For contributors or if you want to modify Titan CLI:

#### Step 1: Clone Repository

```bash
git clone https://github.com/masmovil/titan-cli.git
cd titan-cli
```

#### Step 2: Install Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

#### Step 3: Install Dependencies

```bash
poetry install
```

#### Step 4: Run from Source

```bash
poetry run titan --help
```

Or activate the virtual environment:
```bash
poetry shell
titan --help
```

---

## Installing Plugins

Titan CLI uses a plugin system. Plugins are installed separately after core installation.

### Available Official Plugins

| Plugin | Description | Installation |
|--------|-------------|--------------|
| **titan-plugin-git** | Git operations and workflows | `pipx inject titan-cli titan-plugin-git` |
| **titan-plugin-github** | GitHub integration + PR AI agent | `pipx inject titan-cli titan-plugin-github` |
| **titan-plugin-jira** | JIRA issue analysis with AI | `pipx inject titan-cli titan-plugin-jira` |

### Example: Install GitHub Plugin

```bash
# Install GitHub plugin into Titan CLI's environment
pipx inject titan-cli titan-plugin-github

# Verify plugin is loaded
titan plugins list
```

---

## Configuration

### Initial Setup

Run the initialization wizard:
```bash
titan init
```

This creates:
- `~/.titan/config.toml` - Global configuration
- `~/.titan/secrets.env` - Encrypted secrets (optional)

### Project-Specific Configuration

Navigate to your project directory and run:
```bash
cd /path/to/your/project
titan init
```

This creates:
- `.titan/config.toml` - Project-specific configuration
- `.titan/workflows/` - Custom workflow definitions

---

## Upgrading

### Upgrade to Latest Version

```bash
pipx upgrade titan-cli
```

### Upgrade Plugins

```bash
pipx inject --force titan-cli titan-plugin-github
pipx inject --force titan-cli titan-plugin-jira
```

---

## Uninstallation

```bash
pipx uninstall titan-cli
```

This removes Titan CLI and all installed plugins from the isolated environment.

---

## Troubleshooting

### Command Not Found

If `titan` command is not recognized after installation:

1. Ensure pipx is in your PATH:
   ```bash
   python3 -m pipx ensurepath
   ```

2. Restart your terminal

3. Verify installation:
   ```bash
   pipx list
   ```

### Python Version Issues

Titan CLI requires Python 3.10+. Check your version:
```bash
python3 --version
```

If you have an older version, install Python 3.10+ from:
- macOS: `brew install python@3.10`
- Ubuntu/Debian: `sudo apt install python3.10`
- Windows: Download from [python.org](https://www.python.org/downloads/)

### Permission Errors

On macOS/Linux, you might need to add `--user` flag:
```bash
python3 -m pip install --user pipx
```

---

## Advanced Installation

### Custom Installation Location

```bash
# Set custom pipx home directory
export PIPX_HOME=~/.local/pipx
export PIPX_BIN_DIR=~/.local/bin

pipx install titan-cli
```

### Development with Editable Install

```bash
cd /path/to/titan-cli
pipx install --editable .
```

Changes to source code are immediately reflected without reinstalling.

---

## Next Steps

After installation:

1. **Initialize Configuration:**
   ```bash
   titan init
   ```

2. **View Available Commands:**
   ```bash
   titan --help
   ```

3. **Install Plugins:**
   ```bash
   pipx inject titan-cli titan-plugin-github
   ```

4. **Explore Workflows:**
   ```bash
   titan workflows list
   ```

5. **Read Documentation:**
   - [User Guide](README.md)
   - [Development Guide](DEVELOPMENT.md)
   - [Agent Development](AGENTS.md)

---

## Getting Help

- **GitHub Issues:** [Report bugs or request features](https://github.com/masmovil/titan-cli/issues)
- **Documentation:** [Full documentation](https://github.com/masmovil/titan-cli)
- **In-CLI Help:** `titan --help` or `titan <command> --help`

---

**Installation Guide for Titan CLI v1.0.0**
Last Updated: 2026-01-12
