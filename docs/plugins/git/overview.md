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
- `branches` — the branch you are on at the top, and under it the branches you worked on most recently (reflog first, then last commit date), with a filter. Any branch unfolds into `Merge a branch into it…`, a picker led by the project's configured base branch, which runs the merge workflow; the branch you are on also offers `Pull origin/<branch>`, `Push origin/<branch>` and `Create PR`, the others `Switch to it`. `Create PR` runs the `create_pr_workflow` (`create-pr-ai` from titan-plugin-github by default), or the project workflow extending it where the repo has one — the same run its menu entry opens — and shows only when this Titan has one of them; the commit and the push are that workflow's, so a dirty tree does not hide it. From the press until git answers, both buttons are replaced by a `… pulling origin/<branch>` line, so the card says what it is doing and a second press cannot start the same thing twice. A push git refuses is reported as git worded it, with the reason — the pane never forces one, since that would drop the remote's commits. The branch you are on also unfolds into `New branch from it…`: a field for the name, `✦ Suggest with AI` — which reads the uncommitted diff under the prefixes this repo names its branches with (`feat`, `fix`, …, read from the branches themselves) and, where the github plugin is installed, the labels its pull requests carry — and `Create <name> and switch`, which is the only thing that creates anything: a suggestion just fills the field. The name is put in the shape git accepts and judged before git is asked, so a clash or a character git refuses is reported under the field. The new branch starts at the branch you are on and carries the uncommitted work with it, which is why the fold is offered with a dirty tree too — it is the way out of having worked on the wrong branch. While the working tree has modified or staged files the card turns amber, says so above everything and offers the commit workflow instead; the pull stays, since git decides for itself whether it is safe, and untracked files never block a switch.
- `worktrees` — every worktree of the repository. One unfolds into its path and a two-press removal (the main worktree and the one Titan runs in are refused); a forced removal is offered only after git has refused one, and `Prune stale records` clears what git keeps for folders deleted by hand.

Options (`[mods.git.options]` in `~/.titan/config.toml`): `repo_refresh_seconds` (30), `branches_refresh_seconds` (60), `worktrees_refresh_seconds` (120), `refresh_key` (`f5`, empty for none), `recent_commits` (10), `recent_branches` (8), `branch_filter_threshold` (8), `commit_workflow` (`commit-ai`), `create_pr_workflow` (`create-pr-ai`), `merge_workflow` (`merge-branch`), `suggestion_diff_chars` (4000).

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
