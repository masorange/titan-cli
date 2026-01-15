# 🚀 Titan CLI v1.0.0 - Release Instructions

---

## 📦 Files Ready for Distribution

```
dist/
├── titan_cli-1.0.0-py3-none-any.whl  (115KB) ← Use this for installation
└── titan_cli-1.0.0.tar.gz            (84KB)  ← Source distribution
```

---

## 🎯 GitHub Release - Step by Step

### Step 1: Create Git Tag

```bash
git tag -a v1.0.0 -m "Release Titan CLI v1.0.0 - First stable release"
git push origin v1.0.0
```

### Step 2: Create GitHub Release

1. Go to: https://github.com/masmovil/titan-cli/releases/new
2. **Tag:** `v1.0.0`
3. **Title:** `v1.0.0 - First Stable Release`
4. **Description:**

```markdown
# Titan CLI v1.0.0 🎉

First stable release of Titan CLI - Modular development tools orchestrator.

## 🌟 Features

- **CLI Framework:** Built with Typer + Rich for beautiful terminal UI
- **Plugin System:** Extensible architecture with Git, GitHub, and JIRA plugins
- **AI Integration:** Support for Claude (Anthropic) and Gemini (Google)
- **Workflow Engine:** Execute complex workflows with YAML configuration
- **Secret Management:** Secure storage using OS keyring

## 📦 Installation

### Quick Start

```bash
# Install pipx (once)
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Install Titan CLI
pipx install https://github.com/masmovil/titan-cli/releases/download/v1.0.0/titan_cli-1.0.0-py3-none-any.whl

# Verify installation
titan version
```

### Full Installation Guide

See [INSTALLATION.md](INSTALLATION.md) for complete instructions.

## 🔧 What's Included

- Core CLI with workflow engine
- Terminal UI components
- Configuration management
- Plugin discovery system
- AI provider integration (Claude + Gemini)

## 📚 Documentation

- [Installation Guide](INSTALLATION.md)
- [User Guide](README.md)
- [Development Guide](DEVELOPMENT.md)
- [Agent Development](AGENTS.md)

## 🎯 Next Steps

After installation:

1. Initialize: `titan init`
2. Explore: `titan --help`
3. Install plugins as needed

## 📊 Stats

- **Python:** 3.10+
- **Platform:** Windows, macOS, Linux
- **Package Size:** 115KB (wheel)
- **Dependencies:** Core packages (no plugins)
```

5. **Attach Files:**
   - Click "Attach binaries"
   - Upload: `dist/titan_cli-1.0.0-py3-none-any.whl`
   - Upload: `dist/titan_cli-1.0.0.tar.gz`

6. **Publish Release**

---

## 👥 For End Users - Installation

Share this with your team:

### Option A: Direct URL Install

```bash
pipx install https://github.com/masmovil/titan-cli/releases/download/v1.0.0/titan_cli-1.0.0-py3-none-any.whl
```

### Option B: Download + Install

```bash
# 1. Download wheel
curl -LO https://github.com/masmovil/titan-cli/releases/download/v1.0.0/titan_cli-1.0.0-py3-none-any.whl

# 2. Install
pipx install titan_cli-1.0.0-py3-none-any.whl

# 3. Verify
titan version
# Output: Titan CLI v1.0.0
```

---

## 🔄 Updating to Future Versions

When v1.1.0 is released:

```bash
# Uninstall old version
pipx uninstall titan-cli

# Install new version
pipx install <new-wheel-url>
```

Or use upgrade:

```bash
pipx upgrade titan-cli
```

---

## 🐛 Troubleshooting

### Command not found after installation

```bash
# Ensure pipx is in PATH
python3 -m pipx ensurepath

# Restart terminal
# Try again
```

### Python version too old

Titan CLI requires Python 3.10+:

```bash
python3 --version
# Should show 3.10.x or higher
```

---

## 📋 Checklist Before Release

### ✅ Package Preparation (Completed)
- [x] Version bumped to 1.0.0
- [x] Build successful
- [x] Wheel generated (115KB)
- [x] Plugins removed from core distribution
- [x] jinja2 dependency added
- [x] Metadata updated (homepage, repository, keywords)

### ✅ Testing & Validation (Completed)
- [x] Installation tested in clean venv
- [x] Installation tested with pipx
- [x] Verified no plugins bundled
- [x] All 10 automated tests passed (validate.sh)
- [x] `titan version` shows v1.0.0
- [x] `titan plugins list` shows "No plugins installed"
- [x] All core commands functional

### ✅ Documentation (Completed)
- [x] RELEASE.md created
- [x] DISTRIBUTION_GUIDE.md updated
- [x] INSTALLATION.md created
- [x] VALIDATION_CHECKLIST.md created
- [x] VALIDATION_REPORT.md generated
- [x] RELEASE_README.md created
- [x] validate.sh script created

### 🚀 Release Process (Pending)
- [ ] Git tag created: `v1.0.0`
- [ ] GitHub Release created
- [ ] Wheel uploaded to GitHub
- [ ] Source tarball uploaded to GitHub
- [ ] Release notes published
- [ ] Installation instructions shared with team

---

**Ready to release? Follow the steps above!**

Release Date: 2026-01-12
