# Titan CLI

**Modular development tools orchestrator** — Automate Git, GitHub, and Jira workflows through a plugin system with an intuitive terminal UI and optional AI assistance.

---

## What is Titan?

Titan is a CLI tool that lets you define and run **workflows** — sequences of automated steps that combine Git operations, GitHub API calls, Jira queries, shell commands, and AI-generated content into a single, repeatable action.

Instead of running five commands manually every time you open a PR, you run `titan` and pick a workflow from the menu.

---

## Key features

- **Workflow engine** — Compose atomic steps into automated flows defined in YAML
- **Modern TUI** — Interactive terminal interface powered by [Textual](https://textual.textualize.io/)
- **Plugin system** — Built-in Git, GitHub, and Jira plugins; extensible with your own
- **AI integration** — Optional AI connections for commit messages, PR descriptions, and issue analysis
- **Project-scoped** — Per-project configuration in `.titan/config.toml`; no global state

---

## Install

```bash
pipx install titan-cli
```

Then launch from inside any project:

```bash
cd /path/to/your-project
titan
```

On first run, Titan guides you through setting up global preferences and enabling plugins for your project.

---

## Where to go next

<div class="grid cards" markdown>

- **New to Titan?**

    Start here to get Titan installed and run your first workflow.

    [→ Getting Started](getting-started/installation.md)

- **Understand how workflows work**

    Learn what a workflow is, how steps connect, and how results control execution.

    [→ Workflow Concepts](concepts/workflows.md)

- **Build your own workflow**

    Hands-on tutorial: extend a built-in workflow with a custom step.

    [→ Your First Workflow](getting-started/your-first-workflow.md)

- **Contribute to Titan**

    Set up a development environment and understand the codebase.

    [→ Contributing](contributing/development-setup.md)

</div>
