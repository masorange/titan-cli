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

The plugin ships the `git` [mod](../../concepts/mods.md): a side-panel pane with the branch you are on, read through `GitClient` on timers and refreshed after every workflow. It shows the branch, how it stands against its upstream (`↑ahead ↓behind`), how many lines are uncommitted, and the branch's card with what can be done with it, plus `Open Git workspace` for everything else (the history, the branch switcher and the worktrees). The same card is the top of the workspace's left column.

The card is one fold on the branch name. Unfolded, the branch you are on shows three small cards: **Working tree** (`Commit with AI`, `Stash changes`, `Pop stash`), **Remote** (`Pull`, `Push`, `Create PR`) and **Branch** (`New branch from it…`, `Merge a branch into it…`). Any other branch is one card with `Switch to it`. What each does:

- `Commit with AI` — the `commit_workflow` (`commit-ai`), first while the tree is dirty. While the working tree has modified or staged files the card turns amber and says so above everything; untracked files never block a switch.
- `Pull origin/<branch>` and `Push origin/<branch>`. From the press until git answers, the options are replaced by a `… pulling origin/<branch>` line, so a second press cannot start the same thing twice. A push git refuses is reported as git worded it, with the reason — nothing here forces one, since that would drop the remote's commits; the pull stays with a dirty tree, since git decides for itself whether it is safe.
- `Create PR` — the `create_pr_workflow` (`create-pr-ai` from titan-plugin-github by default), or the project workflow extending it where the repo has one, shown only when this Titan has one; the commit and the push are that workflow's, so a dirty tree does not hide it.
- `Stash changes` (only while the tree is dirty) and `Stashes (N)…` (only while there is a stash): the list, newest first, each by its message, branch and age; a line apart, last, `Clear stash list…` drops them all after a confirmation. Pressing a stash in the workspace selects it: its changes show on the right as file cards, like a commit's, under a **Stash** card with `Apply, keep it`, `Pop: apply and remove` and `Drop…` (behind a second press). A popped or dropped stash sends the screen back to the uncommitted changes. In the mod's pane, pressing a stash opens the workspace on it. The changes shown are those to tracked files; files stashed as untracked are not previewed. Stashing takes new, untracked files too, so the tree ends up clean; if git refuses a pop (a conflict, say) it says so and keeps the stash.
- `New branch from it…` — a field for the name, `✦ Suggest with AI` (reads the uncommitted diff under the prefixes this repo names its branches with, and, where the github plugin is installed, the labels its pull requests carry) and `Create <name> and switch`, the only thing that creates anything: a suggestion just fills the field. The name is put in the shape git accepts and judged before git is asked. The new branch starts at the branch you are on and carries the uncommitted work with it, so it is offered with a dirty tree too — the way out of having worked on the wrong branch.
- `Merge a branch into it…` — a picker led by the project's configured base branch, which runs the `merge_workflow`.


Options (`[mods.git.options]` in `~/.titan/config.toml`): `repo_refresh_seconds` (30), `branches_refresh_seconds` (60), `refresh_key` (`f5`, empty for none), `recent_branches` (8), `commit_workflow` (`commit-ai`), `create_pr_workflow` (`create-pr-ai`), `merge_workflow` (`merge-branch`), `suggestion_diff_chars` (4000).

## Workspace

The plugin also ships the `git` [workspace](../../concepts/workspaces.md): a full screen opened from the **Git** dock tile (`Esc` goes back), a gitk for Titan. On the left, above the history, are the branch card of the mod's pane (commit, pull, push, Create PR, stash, merge, new branch; they use the same workflows and AI task), the branch switcher and the worktrees. The switcher lists the branches you worked on most recently (reflog first, then last commit date) under the same large search field as the GitHub and Jira workspaces (`✕ Clear search` empties it): typing searches every branch a checkout reaches, remote-only ones marked `· remote`, and Enter switches to the branch the text names, exactly or as the only branch containing it; when several match, none does, or uncommitted work blocks the switch, it says so under the field and checks nothing out. Any other branch unfolds into `Switch to it` and `Merge a branch into it…`. The worktrees card lists every worktree; one unfolds into its path and a two-press removal (the main worktree and the one Titan runs in are refused), a forced removal is offered only after git has refused one, and `Prune stale records` clears what git keeps for folders deleted by hand. Under them the commit graph (every branch and tag, `graph_max_lanes` before it falls back to a plain list) is led by **Uncommitted changes**; the files of what you pick sit on the right (the two stack when the window is narrow; drag the border between them to give either more room, and the width is remembered). Uncommitted changes list **Staged** and **Unstaged** files apart, new files included; a commit lists the files it changed, compared with its first parent when it is a merge. Each file is a card that folds into its diff, drawn as code: line numbers, a bar and a tinted background on added and removed lines, syntax colours by file extension, and a sideways scroll for long lines. The first file of a selection opens on its own; a diff shows `diff_lines` lines and "＋ Show more lines" adds that many again. History and uncommitted files are read again every `refresh_seconds`, when a workflow ends and with the refresh key; the open diffs of uncommitted files are read again with them. Options (`[workspaces.git.options]` in `~/.titan/config.toml`): `refresh_seconds` (30), `refresh_key` (`f5`, empty for none), `commits_shown` (40), `graph_max_lanes` (8), `context_lines` (3), `diff_lines` (200), `recent_branches` (8), `commit_workflow` (`commit-ai`), `create_pr_workflow` (`create-pr-ai`), `merge_workflow` (`merge-branch`), `suggestion_diff_chars` (4000). The mod's `Open Git workspace` button opens it. The workspace reads through `get_commit_files`, `get_commit_file_diff`, `get_uncommitted_files` and `get_worktree_file_diff` (see [Client API](./client-api.md)).

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
