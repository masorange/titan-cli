# Development vs Production: Understanding `titan` vs `titan-dev`

> Quick reference for contributors

---

## 🎯 TL;DR

- **End users:** Install with `pipx install titan-cli` → Get `titan` command only
- **Contributors:** Clone repo + `make dev-install` → Get both `titan` (production) and `titan-dev` (development)

---

## 📦 What Gets Installed Where

### End Users (PyPI Installation)

```bash
pipx install titan-cli
```

**What they get:**
```
~/.local/bin/titan → ~/.local/share/pipx/venvs/titan-cli/bin/titan
```

**Defined in:** `pyproject.toml`
```toml
[tool.poetry.scripts]
titan = "titan_cli.cli:app"  # ✅ Only titan, no titan-dev
```

**They can only use:** `titan`

---

### Contributors (Repository Clone)

```bash
git clone https://github.com/masorange/titan-cli.git
cd titan-cli
make dev-install
```

**What they get:**
```
~/.local/bin/titan     → pipx installation (optional, production version)
~/.local/bin/titan-dev → bash script → ~/git/titan-cli/.venv/bin/titan
~/git/titan-cli/.venv/ → poetry virtualenv with editable install
```

**The titan-dev script content:**
```bash
#!/bin/bash
# titan-dev - Development version of Titan CLI
exec /home/alex/git/titan-cli/.venv/bin/titan "$@"
```

**They can use:** Both `titan` (stable) and `titan-dev` (local changes)

---

## 🔒 Security: Ensuring titan-dev Stays Local

### ✅ What We Do Right

1. **Not in pyproject.toml scripts:**
   ```toml
   [tool.poetry.scripts]
   titan = "titan_cli.cli:app"  # ✅ Only titan
   # NO titan-dev here
   ```

2. **Created only by Makefile:**
   - `make dev-install` creates `~/.local/bin/titan-dev`
   - This target is NOT run during `poetry build` or `poetry publish`
   - Script is never part of the distributed package

3. **Not in .gitignore:**
   - The script lives in `~/.local/bin/`, not in the repo
   - Nothing to accidentally commit

4. **Clear documentation:**
   - README.md clearly separates "For Users" vs "For Contributors"
   - DEVELOPMENT.md explicitly states it's for contributors only
   - This guide explains the architecture

### ❌ What Would Be Wrong

```toml
# DON'T DO THIS:
[tool.poetry.scripts]
titan = "titan_cli.cli:app"
titan-dev = "titan_cli.cli:app"  # ❌ Would ship to all users!
```

---

## 🧪 Testing the Separation

### Test 1: Fresh PyPI Install (Simulating End User)

```bash
# In a different machine or clean environment
pipx install titan-cli

# Should work:
titan --version  # ✅ Works

# Should NOT work:
titan-dev --version  # ❌ Command not found
```

### Test 2: Development Install (Contributor)

```bash
# Clone and setup
git clone https://github.com/masorange/titan-cli.git
cd titan-cli
make dev-install

# Both should work:
titan --version      # ✅ Production (if installed)
titan-dev --version  # ✅ Development
```

### Test 3: Build and Check Package

```bash
# Build the package
cd ~/git/titan-cli
poetry build

# Extract and check
cd dist
tar -tzf titan_cli-0.1.11.tar.gz | grep bin
# Should NOT contain any bin/titan-dev

# Check wheel
unzip -l titan_cli-0.1.11-py3-none-any.whl | grep scripts
# Should only list titan, not titan-dev
```

---

## 🔄 Development Workflow

### Making Changes

```bash
# 1. Edit code
vim ~/git/titan-cli/titan_cli/some_file.py

# 2. Test immediately (no reinstall needed)
titan-dev

# Changes are reflected immediately because:
# - Poetry installs in editable mode (-e flag)
# - titan-dev points to .venv/bin/titan
# - .venv/bin/titan uses the source code directly
```

### Releasing to Production

```bash
# 1. Bump version in pyproject.toml
vim pyproject.toml  # Update version = "0.1.12"

# 2. Build package
poetry build

# 3. Publish to PyPI
poetry publish

# 4. Users update
pipx upgrade titan-cli

# They ONLY get 'titan' command, never 'titan-dev'
```

---

## 📁 File Locations Summary

### End User Installation

| What | Location |
|------|----------|
| Binary | `~/.local/bin/titan` → `~/.local/share/pipx/venvs/titan-cli/bin/titan` |
| Config | `~/.titan/config.toml` |
| Project config | `./.titan/config.toml` (in each project) |
| Logs (future) | `~/.local/state/titan/logs/` |

### Development Installation

| What | Location |
|------|----------|
| Source code | `~/git/titan-cli/` (or wherever cloned) |
| Virtualenv | `~/git/titan-cli/.venv/` |
| Dev binary | `~/.local/bin/titan-dev` (bash wrapper script) |
| Config | Same as end user (`~/.titan/config.toml`) ⚠️ |
| Project config | Same as end user (`./.titan/config.toml`) ⚠️ |

**⚠️ Warning:** Both `titan` and `titan-dev` share the same configuration files. Be careful when testing breaking config changes.

---

## 🚨 Common Mistakes to Avoid

### ❌ Mistake 1: Adding titan-dev to pyproject.toml

```toml
# WRONG:
[tool.poetry.scripts]
titan-dev = "titan_cli.cli:app"  # ❌ Ships to all users!
```

### ❌ Mistake 2: Committing the titan-dev script to repo

```bash
# WRONG:
git add ~/.local/bin/titan-dev  # ❌ Lives outside repo
```

### ❌ Mistake 3: Documenting titan-dev in README without warning

```markdown
# WRONG in README.md:
Run `titan-dev` to start the application.
# ❌ End users don't have titan-dev!
```

### ✅ Correct: Separate documentation

- **README.md**: Only mentions `titan` for end users
- **DEVELOPMENT.md**: Explains `titan-dev` for contributors
- **This guide**: Architecture details for maintainers

---

## 🎓 For New Contributors

When you start contributing to Titan CLI:

1. **Read DEVELOPMENT.md first** - Understand the development setup
2. **Run `make dev-install`** - Sets up titan-dev for you
3. **Use `titan-dev` for testing** - Your local changes
4. **Keep `titan` for daily work** - Stable version (optional)

When you see `titan-dev` in documentation, it means:
- ✅ You're reading contributor documentation
- ✅ You need to have cloned the repo
- ✅ You need to have run `make dev-install`
- ❌ This command doesn't exist for end users

---

**Last updated:** 2026-02-17
