# Git Workflow Steps

The Git plugin exposes reusable public workflow steps through `GitPlugin.get_steps()`. These steps are grouped here by workflow intent so authors can discover related building blocks more easily.

## Functional groups

- [Status and Inspection](#status-and-inspection)
- [Commits](#commits)
- [Branching](#branching)
- [Diff Summaries](#diff-summaries)
- [Worktrees](#worktrees)

## Summary

| Step | Group | Used by built-in workflows |
|------|-------|----------------------------|
| `get_status` | Status and Inspection | `commit-ai` |
| `get_current_branch` | Status and Inspection | `create-pr-ai` |
| `get_base_branch` | Status and Inspection | - |
| `create_commit` | Commits | `commit-ai` |
| `push` | Commits | `commit-ai`, `create-pr-ai` |
| `ai_generate_commit_message` | Commits | `commit-ai` |
| `save_current_branch` | Branching | - |
| `restore_original_branch` | Branching | - |
| `checkout` | Branching | - |
| `pull` | Branching | - |
| `create_branch` | Branching | - |
| `show_uncommitted_diff_summary` | Diff Summaries | `commit-ai` |
| `show_branch_diff_summary` | Diff Summaries | `create-pr-ai` |
| `create_worktree` | Worktrees | - |
| `remove_worktree` | Worktrees | - |
| `worktree_commit` | Worktrees | - |
| `worktree_push` | Worktrees | - |

## Status and Inspection

Use these steps to inspect repository state and expose branch metadata to later steps.

- `get_status`: retrieve repository status and expose `git_status` to the workflow context
- `get_current_branch`: resolve the currently checked out branch name
- `get_base_branch`: resolve the base branch used by Git workflows

## Commits

Use these steps to prepare commit content and publish branch changes.

- `create_commit`: create a commit from workflow commit message data
- `push`: push the current branch to the configured remote
- `ai_generate_commit_message`: generate a commit message from local changes using AI

## Branching

Use these steps to switch, create, and restore branches during a workflow.

- `save_current_branch`: save the current branch in workflow context
- `restore_original_branch`: restore the saved branch later in the workflow
- `checkout`: switch to a branch from workflow context or params
- `pull`: update the current branch from the configured remote
- `create_branch`: create a new branch from workflow-provided branch data

## Diff Summaries

Use these steps when a workflow needs human-readable or AI-friendly summaries of Git changes.

- `show_uncommitted_diff_summary`: summarize local uncommitted changes
- `show_branch_diff_summary`: summarize branch-level changes relative to the base branch

## Worktrees

Use these steps to isolate workflow work in dedicated worktrees.

- `create_worktree`: create a worktree for isolated work
- `remove_worktree`: remove a worktree when finished
- `worktree_commit`: commit changes inside a specific worktree
- `worktree_push`: push a branch from a specific worktree

## Docstring-based reference

The semiautomated step inventory reads public step docstrings from code and validates that each exposed step documents:

- `Requires`
- `Inputs (from ctx.data)` when applicable
- `Outputs (saved to ctx.data)` when applicable
- `Returns`

The generated machine-readable inventory lives under `docs/plugins/_generated/`.

For this project, the inventory is maintained through:

- `.titan/workflows/sync-plugin-docs.yaml`
- `.titan/workflows/validate-plugin-docs.yaml`
- `.titan/steps/sync_plugin_docs.py`
- `.titan/steps/validate_plugin_docs.py`
