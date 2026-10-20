# Git Plugin

The Git plugin provides Titan's core Git workflow surface. It exposes:

- a high-level `GitClient` for direct use from Titan code
- reusable workflow `steps` such as `get_status`, `create_commit`, and `push`
- the built-in `commit-ai` and `merge-branch` workflows

## Requirements

To use the Git plugin in a project:

- Enable the `git` plugin in `.titan/config.toml`
- Install the `git` CLI and make sure it is available in `PATH`
- Run Titan inside a Git repository

Example project configuration:

```toml
[plugins.git]
enabled = true

[plugins.git.config]
main_branch = "main"
default_remote = "origin"
```

## Public surfaces

- [Client API](./client-api.md): direct Python methods exposed by `GitClient`
- [Workflow Steps](./workflow-steps.md): public reusable workflow steps grouped by functionality
- [Built-in Workflows](./built-in-workflows.md): workflows shipped by the plugin

## Mod

The plugin ships the `git` [mod](../../concepts/mods.md): a side-panel pane of three cards, read through `GitClient` on timers and refreshed after every workflow. Each card is a section you can switch off on the Mods screen.

- `repo` — the current branch, its upstream, ahead/behind and the latest commits.
- `branches` — the branch you are on at the top, unfolding into its merges only (there is nothing to switch to), and under it the branches you worked on most recently (reflog first, then last commit date), with a filter. Any branch unfolds into `Merge <base branch> into it` and `Merge another branch…`, and the others also into `Switch to it`; both merges run a workflow. While the working tree has modified or staged files the card turns amber, says so above everything and offers the commit workflow instead: untracked files never block a switch.
- `worktrees` — every worktree of the repository. One unfolds into its path and a two-press removal (the main worktree and the one Titan runs in are refused); a forced removal is offered only after git has refused one, and `Prune stale records` clears what git keeps for folders deleted by hand.

Options (`[mods.git.options]` in `~/.titan/config.toml`): `repo_refresh_seconds` (30), `branches_refresh_seconds` (60), `worktrees_refresh_seconds` (120), `refresh_key` (`f5`, empty for none), `recent_commits` (10), `recent_branches` (8), `branch_filter_threshold` (8), `commit_workflow` (`commit-ai`), `merge_workflow` (`merge-branch`).

## Accessing the client

In Titan code, the public entry point is the Git plugin client:

```python
git_plugin = config.registry.get_plugin("git")
client = git_plugin.get_client()
```

The client returns `ClientResult[...]` values. In practice, this means each call can succeed with data or return an error result.

## Public workflow steps

The Git plugin exposes these reusable public steps through `get_steps()`:

- `get_status`
- `create_commit`
- `push`
- `get_current_branch`
- `get_base_branch`
- `ai_generate_commit_message`
- `show_uncommitted_diff_summary`
- `show_branch_diff_summary`
- `save_current_branch`
- `restore_original_branch`
- `checkout`
- `pull`
- `create_branch`
- `resolve_merge_target`
- `fetch_merge_source`
- `merge_source_branch`
- `complete_merge`
- `create_worktree`
- `remove_worktree`
- `worktree_commit`
- `worktree_push`

These steps are intended for workflow authors. Their inputs, outputs, and return behavior are documented in [Workflow Steps](./workflow-steps.md).
