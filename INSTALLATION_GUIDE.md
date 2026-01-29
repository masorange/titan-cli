# Installation and Usage Guide - Titan CLI

**Version**: v0.1.0
**Date**: 2026-01-20

---

## Installation Completed

Titan CLI is already installed globally with pipx and can be executed from any directory.

### Locations:

```bash
# Titan command
which titan
# → /Users/rpedraza/.local/bin/titan

# Pipx virtual environment
~/.local/pipx/venvs/titan-cli/

# Installed plugins
~/.local/pipx/venvs/titan-cli/lib/python3.13/site-packages/
├── titan_plugin_git/
├── titan_plugin_github/
└── titan_plugin_jira/
```

---

## How to Use Titan CLI

### Project-Based Model

**IMPORTANT**: Titan CLI now works with a project-based model. You must execute it **from within the project directory**:

```bash
# CORRECT
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios
titan  # Launches the TUI

# INCORRECT
cd /Users/rpedraza/Documents/MasMovil/titan-cli
titan  # Won't find project workflows
```

### Main Commands

#### 1. **Launch TUI (Textual Interface)**

```bash
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios
titan  # Or titan tui
```

**What it does**:
- Shows interactive menu with all options
- Allows workflow execution
- Plugin configuration
- AI provider management

#### 2. **Execute Workflow (from TUI)**

```bash
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios
titan  # Opens TUI
# Navigate with arrows → Select "Workflows" → "release-notes-ios"
```

#### 3. **Legacy Mode (Rich Menu)**

```bash
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios
titan menu
```

**Note**: Legacy mode still uses the old configuration system.

#### 4. **Configuration Commands**

```bash
# View version
titan version

# Configure AI providers
titan ai

# Manage plugins
titan plugins

# Initialize global configuration
titan init
```

---

## Configuration Structure

### Global Config (`~/.titan/config.toml`)

**Only stores AI provider configuration** (shared across projects):

```toml
[ai.providers.default]
name = "My Claude"
type = "individual"
provider = "anthropic"
model = "claude-sonnet-4-5"

[ai]
default = "default"
```

### Project Config (`.titan/config.toml` in each project)

**Project-specific configuration** (plugins, JIRA, GitHub):

```toml
# ragnarok-ios/.titan/config.toml
[project]
name = "ragnarok-ios"
type = "generic"

[plugins.github]
enabled = true
[plugins.github.config]
repo_owner = "masmovil"
repo_name = "ragnarok-ios"

[plugins.jira]
enabled = true
[plugins.jira.config]
base_url = "https://jiranext.masorange.es"
email = "raul.pedraza@masmovil.com"
default_project = "ECAPP"

[plugins.git]
enabled = true
[plugins.git.config]
protected_branches = ["develop"]
```

### Project Workflows (`.titan/workflows/*.yaml`)

**Project-specific workflows**:

```yaml
# ragnarok-ios/.titan/workflows/release-notes-ios.yaml
name: "Generate Release Notes (iOS)"
description: "Generate multi-brand weekly release notes..."

params:
  project_key: "ECAPP"
  platform: "iOS"
  notes_directory: "ReleaseNotes"

steps:
  - id: list_versions
    plugin: jira
    step: list_versions
    # ... etc
```

---

## Complete Example: Generate Release Notes

### For Ragnarok iOS

```bash
# 1. Navigate to project
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios

# 2. Verify configuration exists
ls -la .titan/config.toml
ls -la .titan/workflows/release-notes-ios.yaml

# 3. Launch Titan
titan

# 4. In the TUI:
#    - Navigate with ↑↓ to "Workflows"
#    - Press Enter
#    - Select "release-notes-ios"
#    - Press Enter
#    - Follow on-screen instructions

# 5. The workflow will:
#    - List JIRA versions
#    - Prompt to select version (e.g., 26.4.0)
#    - Create branch: release-notes/26.4.0
#    - Query JIRA issues
#    - Generate release notes with AI
#    - Show preview and ask for confirmation
#    - Create file: ReleaseNotes/release-notes-26.4.0.md
#    - Commit and push
#    - Create Pull Request
```

### For Ragnarok Android

```bash
# 1. Navigate to project
cd /Users/rpedraza/Documents/MasMovil/ragnarok-android

# 2. Launch Titan
titan

# 3. Execute "release-notes-android" workflow
#    - Creates file at: docs/release-notes/release-notes-26.4.0.md
```

---

## Update Titan CLI

When making changes to titan-cli code:

```bash
cd /Users/rpedraza/Documents/MasMovil/titan-cli

# Reinstall titan-cli
pipx install --force .

# Reinstall plugins
pipx inject --force titan-cli \
  ./plugins/titan-plugin-git \
  ./plugins/titan-plugin-github \
  ./plugins/titan-plugin-jira

# Verify
titan version
```

---

## Troubleshooting

### "No workflows found"

**Cause**: Not in project directory or missing `.titan/workflows/`

**Solution**:
```bash
# Verify location
pwd
# Should be: /Users/rpedraza/Documents/MasMovil/ragnarok-ios

# Verify workflows
ls -la .titan/workflows/
```

### "Plugin not initialized"

**Cause**: Missing plugin configuration in `.titan/config.toml`

**Solution**:
```bash
# Verify config
cat .titan/config.toml

# Should have:
# [plugins.jira]
# enabled = true
```

### "JIRA authentication failed"

**Cause**: Missing JIRA_API_TOKEN

**Solution**:
```bash
# Configure token
titan menu  # Or titan ai
# Follow configuration wizard
```

### "Command not found: titan"

**Cause**: PATH doesn't include ~/.local/bin

**Solution**:
```bash
# Verify PATH
echo $PATH | grep -q ".local/bin" && echo "OK" || echo "Missing .local/bin"

# Add to PATH (if missing)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

---

## Comparison: Before vs Now

### Before (old version)

```bash
# Global config with active_project
~/.titan/config.toml:
  [core]
  project_root = "/Users/rpedraza/Documents/MasMovil"
  active_project = "ragnarok-ios"

# Execute from anywhere
cd /tmp
titan workflow run release-notes-ios  # Worked
```

### Now (v0.2.0 - PR #110)

```bash
# No global project configuration
~/.titan/config.toml:
  [ai.providers.default]
  provider = "anthropic"

# Each project has its own config
ragnarok-ios/.titan/config.toml:
  [project]
  name = "ragnarok-ios"

# MUST be in the project
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios
titan  # Works

cd /tmp
titan  # Doesn't find workflows
```

---

## Resources

- **Documentation**: `/Users/rpedraza/Documents/MasMovil/titan-cli/CLAUDE.md`
- **Workflow Examples**: `/Users/rpedraza/Documents/MasMovil/titan-cli/examples/`
- **Project Setup**: `/Users/rpedraza/Documents/MasMovil/titan-cli/SETUP_RAGNAROK_PROJECTS.md`

---

## Verification Checklist

Before using Titan in a project:

- [ ] `.titan/config.toml` exists in the project
- [ ] `.titan/workflows/*.yaml` exists in the project
- [ ] Plugins enabled in `.titan/config.toml`
- [ ] Secrets configured (JIRA_API_TOKEN, GITHUB_TOKEN, ANTHROPIC_API_KEY)
- [ ] You're in the correct directory (`pwd` shows the project)
- [ ] `titan version` works

---

**Last updated**: 2026-01-20
**By**: Pipx installation
**Titan version**: v0.1.0
