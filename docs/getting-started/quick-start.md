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

## The home screen

After launch you land on the home screen: a grid of up to **nine workflow cards**, each one
launchable by pressing its number.

```
⭐ Favorites

╭─ ⭐ 1 ──────────────╮  ╭─ ⭐ 2 ──────────────╮  ╭─ 3 ─────────────────╮
│ Review PR          │  │ Commit with AI     │  │ Create Pull Request │
│ Github             │  │ Git                │  │ Github              │
│                    │  │                    │  │                     │
│ Focused AI review  │  │ Create a commit    │  │ AI-powered PR        │
│ for new findings   │  │ with AI message    │  │ creation             │
╰────────────────────╯  ╰────────────────────╯  ╰─────────────────────╯

  ⚡ All workflows [w]     🔌 Plugins [p]     🤖 AI [a]
```

| Key | Action |
|---|---|
| `1`–`9` | Run the workflow on that card |
| `Tab` / `Shift+Tab` | Move the focus between cards, then `Enter` to run the focused one |
| `w` | Open the full workflow list |
| `p` | Open plugin management |
| `a` | Open AI configuration |
| `q` / `Esc` | Quit |

The cards reflow into fewer columns as the terminal gets narrower, down to one card per row.
**Which workflows are on the grid, and which number each one has, never changes with the
window size** — so a key you have learned keeps working at any width.

### How the nine slots are chosen

Slots are filled in this order, skipping anything already placed:

1. **Your favorites**, in the order you starred them.
2. **Recently used workflows**, most recent first.
3. **A balanced round-robin** across workflow groups (Git, Github, Jira, Project, Personal…),
   one per group per pass, alphabetically — so a plugin with twenty workflows cannot crowd out
   the rest.

The title above the grid tells you which of these you are looking at:

- **⭐ Favorites** — at least one card is a workflow you starred.
- **⚡ Suggested** — you have no favorites yet, so every card is a suggestion.
- If no plugins are enabled there is no grid at all, just a prompt to open plugin management
  with `p`.

### Starring a workflow

Press **`f` while a workflow is running**, or click **☆ Favorite** in that screen's header, to star it. The star
is a toggle — press it again to remove it. Starred workflows move to the front of the grid,
and the home screen picks the change up as soon as you return to it.

If you star more than nine workflows, the grid grows and scrolls to show all of them; the
number keys serve the first nine, and the rest are marked with a star but no number.

!!! note "Favorites and recent workflows are per project"
    Both are stored against the project's path, so starring a workflow in one repository does
    not put it on the home screen of another — even when both repositories have a workflow of
    the same name. Titan remembers the 20 most recently run workflows per project.

Where the cards come from:

- Built-in plugin workflows (Git, GitHub, Jira)
- Your project's own workflows in `.titan/workflows/`

---

## The full workflow list

Press `w` for everything, not just the nine on the home screen. Filter by plugin in the left
panel, then press `Enter` to run. Favorites are sorted to the top here too.

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
[ai]
default_connection = "default"

[ai.connections.default]
name = "My Anthropic"
kind = "direct_provider"
provider = "anthropic"
default_model = "claude-sonnet-4-5"
```

Titan will prompt for your API key on first use and store it securely in your OS keyring.

---

## Next step

[→ Your First Workflow](your-first-workflow.md) — Build a custom workflow from scratch.
