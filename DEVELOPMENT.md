# DEVELOPMENT.md

> High-Level Architecture Overview for Titan CLI

**For detailed technical documentation, development guides, and best practices, see [AGENTS.md](AGENTS.md).**

---

## 🛠️ Development Setup

### Prerequisites

- Python 3.10+
- Poetry (for dependency management)
- pipx (recommended for production install)

### Two-Environment Setup (Recommended)

To contribute to Titan CLI while still using a stable version for your daily work, you should maintain **two separate environments**:

1. **Production**: Stable version installed via pipx (`titan`)
2. **Development**: Local repository for testing changes (`titan-dev`)

#### Step 1: Install Production Version (Optional but Recommended)

```bash
# Install stable version for daily use
pipx install titan-cli

# Verify
titan --version
```

#### Step 2: Clone and Setup Development Environment

```bash
# 1. Clone the repository
git clone https://github.com/masmovil/titan-cli.git
cd titan-cli

# 2. Install dependencies with Poetry
poetry install --with dev

# 3. Create an alias for development version
# Add this to your ~/.bashrc or ~/.zshrc:
alias titan-dev='poetry -C /path/to/titan-cli run python -m titan_cli.cli'

# Or create a symlink (alternative approach)
# sudo ln -s /path/to/titan-cli/.venv/bin/python /usr/local/bin/titan-dev

# 4. Verify development version
titan-dev --version
```

#### Step 3: Testing Your Changes

```bash
# Use titan-dev to test your changes
cd ~/your-project
titan-dev  # Launches TUI with your local changes

# Use titan for stable daily work
cd ~/your-project
titan      # Launches stable version from pipx
```

### Alternative: Single Development Environment

If you only want to develop and don't need a stable version:

```bash
# 1. Clone the repository
git clone https://github.com/masmovil/titan-cli.git
cd titan-cli

# 2. Install dependencies
poetry install --with dev

# 3. Run directly with Poetry
poetry run titan

# Or activate the virtual environment
poetry shell
titan
```

### Initial Configuration

When you run Titan (either `titan` or `titan-dev`) for the first time:

```bash
# 1. Navigate to any project directory
cd ~/your-project

# 2. Launch Titan
titan-dev  # or titan

# 3. Follow the setup wizards:
#    - Global setup (only once): Configure AI providers
#    - Project setup (per project): Enable plugins, set project name
```

**Note:** Titan uses a project-based configuration. Each project has its own `.titan/config.toml` file. The global config (`~/.titan/config.toml`) only stores AI provider settings.

---

## 🧪 Testing and Contributing

### Running Tests

```bash
# Run all core tests
poetry run pytest tests/

# Run plugin tests individually (to avoid conftest conflicts)
poetry run pytest plugins/titan-plugin-git/tests
poetry run pytest plugins/titan-plugin-github/tests
cd plugins/titan-plugin-jira && poetry run pytest

# Run with coverage
poetry run pytest tests/ --cov=titan_cli --cov-report=html

# Run specific test file
poetry run pytest tests/test_config.py -v
```

### Code Quality

```bash
# Run linter
poetry run ruff check .

# Auto-fix issues
poetry run ruff check . --fix

# Format code
poetry run ruff format .
```

### Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes** using `titan-dev` for testing

3. **Run tests** to ensure nothing broke
   ```bash
   poetry run pytest tests/
   ```

4. **Commit with conventional commits**
   ```bash
   git commit -m "feat(ui): add new component for X"
   # or
   git commit -m "fix(git): resolve issue with branch detection"
   ```

5. **Push and create PR**
   ```bash
   git push origin feat/your-feature-name
   ```

### Conventional Commit Format

We use conventional commits for automatic changelog generation:

- `feat(scope): description` - New features
- `fix(scope): description` - Bug fixes
- `docs(scope): description` - Documentation changes
- `refactor(scope): description` - Code refactoring
- `chore(scope): description` - Maintenance tasks
- `test(scope): description` - Test changes
- `perf(scope): description` - Performance improvements

**Scopes**: `ui`, `git`, `github`, `jira`, `core`, `cli`, `config`, `engine`, `workflows`

### Development Tips

**Avoiding Conflicts Between `titan` and `titan-dev`:**

- Both versions use the same global config (`~/.titan/config.toml`) ✅ This is fine
- Each project has its own `.titan/config.toml` ✅ This is fine
- User workflows in `~/.titan/` are shared ✅ Be careful when testing user workflows
- Use different projects or branches when testing breaking changes

**Quick Development Workflow:**

```bash
# 1. Make code changes in your editor
vim titan_cli/ui/components/panel.py

# 2. Test immediately without reinstalling
titan-dev

# 3. No need to rebuild or reinstall - Poetry runs directly from source
```

**Debugging:**

```bash
# Add breakpoints in code with pdb
import pdb; pdb.set_trace()

# Run with verbose output
titan-dev --help  # Add debug logging in code as needed

# Check what version is running
titan-dev version  # Should show version from pyproject.toml
titan version      # Should show installed version from pipx
```

---

## 🎨 UI Architecture and Theming

The UI components are organized to ensure consistency, reusability, and maintainability.

**For a complete guide on creating new components, theming, and styling patterns, see [AGENTS.md § UI Architecture](AGENTS.md#-ui-architecture).**

### 📦 Component Structure (`titan_cli/`)

The `titan_cli/` package is structured as follows:

```
titan-cli/titan_cli/
├── __init__.py
├── cli.py              # Main CLI application definition
├── preview.py          # Preview commands module
├── messages.py         # Centralized user-facing strings
│
├── core/               # Core application logic and services
│   ├── __init__.py
│   ├── config.py           # TitanConfig: manages global and project config
│   ├── models.py           # Pydantic models for config validation
│   ├── plugin_registry.py  # Discovers installed plugins
│   └── discovery.py        # Project discovery logic
│
├── commands/           # CLI command implementations
│   ├── __init__.py
│   ├── init.py             # 'titan init' command for global setup
│   └── projects.py         # 'titan projects' command for project management
│
├── ui/                 # User Interface components and views
│   ├── __init__.py
│   ├── console.py          # Singleton Rich Console instance
│   ├── theme.py            # Centralized theming configuration
│   │
│   ├── components/         # Basic, reusable UI wrappers
│   │   ├── __init__.py
│   │   ├── panel.py        # Wrapper for rich.panel.Panel
│   │   ├── table.py        # Wrapper for rich.table.Table
│   │   ├── typography.py   # Wrapper for styled text
│   │   ├── spacer.py       # Wrapper for SpacerRenderer (vertical spacing)
│   │   └── ... (other atomic components)
│   │
│   └── views/              # Composite UI elements (e.g., Banner, Menus)
│       ├── __init__.py
│       ├── banner.py       # The application's main banner
│       ├── prompts.py      # Wrapper for interactive prompts
│       └── menu_components/ # Components for interactive menus
│           ├── __init__.py
│           ├── menu_models.py    # Pydantic models for menu structure (Menu, MenuItem, etc.)
│           ├── menu.py      # MenuRenderer class (renders the menu visually)
│           ├── dynamic_menu.py # Helper to build Menu objects programmatically
│           └── __previews__/
│               └── menu_preview.py # Non-interactive preview of the menu
```

**Key architectural principles:**
-   **`core/`**: Contains the core business logic and foundational services of the Titan CLI, such as configuration management, plugin discovery, and project scanning.
-   **`commands/`**: Houses the implementations for individual CLI commands (e.g., `titan init`, `titan projects`). Each command or group of commands is typically in its own module.
-   **`ui/`**: Contains all user interface related components, abstracting Rich functionalities for consistent visual output.
    -   **`components/`**: Pure wrappers around Rich library (no composition of other project components). These are the "building blocks" of your UI.
    -   **`views/`**: Composite components that USE other components, can have business logic. These represent larger portions of the UI (e.g., the application banner, interactive menus).

For detailed structure and layer descriptions, see [AGENTS.md § Project Structure](AGENTS.md#-project-structure).

### 🎨 Centralized Theming (`titan_cli/ui/theme.py`)

All styling is driven from `titan_cli/ui/theme.py`:
-   **`TITAN_THEME`**: Rich theme with semantic styles (`success`, `error`, `info`, `primary`)
-   **`BANNER_GRADIENT_COLORS`**: Banner gradient colors
-   **`ThemeManager`**: Syntax highlighting themes

**Usage:**
- Use semantic style names: `console.print("Success!", style="success")`
- For multi-styled text: Use `TextRenderer.styled_text()`
- Never hardcode colors or styles

For complete theming guide, see [AGENTS.md § Theming & Styling](AGENTS.md#-theming--styling).

### 👁️ Previewing UI Components

Preview components in isolation using `__previews__/` directories:

```bash
# Preview components
titan preview panel
titan preview menu
titan preview typography
```

**Structure:**
- Preview scripts in `__previews__/` subdirectories
- One preview file per component (e.g., `panel_preview.py`)
- Preview commands defined in `titan_cli/preview.py`

For complete preview guide, see [AGENTS.md § Creating a New Component](AGENTS.md#-ui-architecture).
