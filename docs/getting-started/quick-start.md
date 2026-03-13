# Quick Start

This guide assumes Titan is already installed. If not, see [Installation](installation.md).

---

## Launch Titan

Run `titan` from inside any configured project:

```bash
cd /path/to/your-project
titan
```

Titan resolves the project root from the git repository root, so you can run it from any subdirectory of a monorepo.

---

## The main menu

After launch you'll see the main menu with a list of available workflows. These come from:

- Built-in plugin workflows (Git, GitHub, Jira)
- Your project's own workflows in `.titan/workflows/`

Use the arrow keys or type to filter, then press `Enter` to run a workflow.

---

## Run a workflow

Workflows are interactive — they guide you through each step with prompts and confirmations.

For example, the **Commit with AI** workflow (from the Git plugin):

1. Shows you the current git diff
2. Lets you stage changes interactively
3. Generates a commit message with AI (if configured)
4. Lets you edit the message before committing

At any point you can press `Escape` or `Ctrl+C` to cancel.

---

## Configuration

### Enable or disable plugins

Edit `.titan/config.toml` in your project root:

```toml
[project]
name = "my-project"

[plugins.git]
enabled = true

[plugins.github]
enabled = true

[plugins.jira]
enabled = false
```

### Configure AI

Edit `~/.titan/config.toml`:

```toml
[ai.providers.default]
name = "Claude"
type = "individual"
provider = "anthropic"
model = "claude-sonnet-4-5"

[ai]
default = "default"
```

Titan will prompt for your API key on first use and store it securely in your OS keyring.

---

## Next step

[→ Your First Workflow](your-first-workflow.md) — Build a custom workflow from scratch.
