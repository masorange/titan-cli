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
