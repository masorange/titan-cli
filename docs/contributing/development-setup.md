# Development Setup

This guide is for contributors who want to work on Titan CLI itself.

---

## Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/) for dependency management
- Git

```bash
# Install Poetry if you don't have it
pipx install poetry
```

---

## Clone and install

```bash
git clone https://github.com/masorange/titan-cli.git
cd titan-cli

make dev-install
```

`make dev-install` does two things:

1. Runs `poetry install` — creates a virtualenv at `.venv/` with all dependencies, including the three plugins in editable mode
2. Creates `~/.local/bin/titan-dev` — a wrapper script that runs Titan from your local source

---

## Run your changes

```bash
titan-dev
```

`titan-dev` always runs from your local codebase. No reinstall needed after editing Python files.

### Logging in `titan-dev`

- `titan-dev` enables development logging.
- During TUI execution, logs are written to `~/.local/state/titan/logs/titan.log`.
- If you want live visual debugging with Textual, run `titan-dev --devtools`
  and start `textual console` in another terminal.

!!! note
    `titan-dev` is only for contributors. End users who install from PyPI get only the `titan` command.

---

## Run tests

```bash
make test
# or
poetry run pytest
```

The test suite covers the main package and all three plugins.

---

## Project structure

```
titan-cli/
├── titan_cli/              # Core engine, TUI, CLI
│   ├── engine/            # Workflow execution
│   └── ui/tui/            # Textual TUI interface
├── plugins/
│   ├── titan-plugin-git/
│   ├── titan-plugin-github/
│   └── titan-plugin-jira/
├── tests/
└── pyproject.toml
```

Each plugin is an independent Python package installed in editable mode during development.

---

## Docs

To work on this documentation site locally:

```bash
make docs-serve
```

Opens a live-reloading preview at `http://localhost:8000`. Changes to any file in `docs/` are reflected instantly.

### Public plugin step documentation

Official plugins expose a public workflow-step API through `plugin.py -> get_steps()`.

When you add or change a public plugin step, you must update both code and docs:

1. Update the step docstring using the canonical sections:
   - `Requires:`
   - `Inputs (from ctx.data):`
   - `Outputs (saved to ctx.data):`
   - `Returns:`
2. Update the relevant pages under `docs/plugins/`
3. Update the grouping metadata under `docs/plugins/_meta/` if you add or rename a public step
4. Regenerate and validate the machine-readable inventories under `docs/plugins/_generated/`

This repository maintains the generated inventory through project workflows in `.titan/workflows/`:

- `sync-plugin-docs`
- `validate-plugin-docs`

The generated inventories are not a replacement for the human-facing docs pages, but they are the source of truth for validation and consistency checks.
