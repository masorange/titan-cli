

## 🎨 UI Architecture and Theming

The UI components are organized to ensure consistency, reusability, and maintainability.

### 📦 Component Structure (`titan_cli/ui/`)

The `ui/` directory is structured as follows:

```
titan-cli/titan_cli/ui/
├── __init__.py
│
├── console.py          # Singleton Rich Console instance
├── messages.py         # Centralized user-facing strings
│
├── components/         # Basic, reusable UI wrappers (e.g., Panel, Table)
│   ├── __init__.py
│   ├── panel.py        # Wrapper for rich.panel.Panel
│   └── ... (other atomic components)
│
└── views/              # Composite UI elements (e.g., Banner, Menus)
    ├── __init__.py
    ├── banner.py       # The application's main banner
    └── ... (other complex views)
```

-   **`components/`**: Contains simple, atomic wrappers around single `rich` elements (e.g., a styled Panel, a custom Table). These are the "building blocks" of your UI.
-   **`views/`**: Contains more complex, composite UI elements that typically use multiple components. These represent larger portions of the UI that users interact with (e.g., the application banner, interactive menus, status displays).

### 🎨 Centralized Theming (`titan_cli/ui/theme.py`)

All styling throughout the CLI should be driven from a single source of truth: `titan_cli/ui/theme.py`.

This file defines:
-   **`TITAN_THEME`**: A `rich.theme.Theme` object that centralizes custom styles (e.g., `success`, `error`, `info`, `primary`) used by `rich.Console` and components like `PanelRenderer`.
-   **`BANNER_GRADIENT_COLORS`**: A list of hex codes for the application's banner gradient.
-   **`SyntaxTheme` & `ThemeManager`**: Your original implementation for managing syntax highlighting themes (e.g., "dracula", "nord").

**How to use:**
-   **For console output and components:** Ensure your `Console` instance is initialized with `TITAN_THEME` (this is handled by `titan_cli/ui/console.py`). Then, simply use style names (e.g., `console.print("Success!", style="success")`).
-   **For banner:** The `render_ascii_banner` function automatically pulls colors from `BANNER_GRADIENT_COLORS`.
-   **For syntax highlighting:** Use `ThemeManager.get_syntax_theme()` when creating `rich.syntax.Syntax` objects.

### 👁️ Previewing UI Components (`__previews__/` directory)

To efficiently develop and debug UI components, you can preview them in isolation without running the entire CLI application. This is achieved using scripts placed in a `__previews__/` subdirectory alongside the components.

**Structure:**
-   Each component or view (`panel.py`, `banner.py`) that you want to preview will have a corresponding preview script (e.g., `panel_preview.py`) in:
    `titan_cli/ui/components/__previews__/`
    `titan_cli/ui/views/__previews__/`

**How to create a preview:**
1.  Create a file like `panel_preview.py` in the `__previews__/` directory.
2.  Inside this file, import the component you want to test (e.g., `from titan_cli.ui.components.panel import PanelRenderer`).
3.  Write code to instantiate and render your component in various states or with different arguments.

**How to run a preview:**
To run a preview script, always execute it as a Python module from the project root using `poetry run python -m ...` (if using poetry) or `python -m ...`:

```bash
# Example for panel_preview.py
poetry run python -m titan_cli.ui.components.__previews__.panel_preview
```
This command ensures that Python correctly resolves internal package imports.
