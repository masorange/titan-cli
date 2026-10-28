# AGENTS.md - Titan Git Plugin

Rules specific to `titan-plugin-git`. The repo-wide rules and guides are in the root
[`AGENTS.md`](../../AGENTS.md); user-facing docs in [`docs/plugins/git/`](../../docs/plugins/git/).

## What it is

Git integration over the system `git` binary, with no dependency on other plugins. Other
plugins (github) get the repository through its client.

## Layout

5-layer: `steps/ → operations/ → clients/git_client.py → clients/services/ → clients/network/`,
with `models/{network,view,mappers}`. User-facing strings in `messages.py`. Also ships the
`git` mod (`mods/git/`) and the `commit-ai`, `merge-branch`, `switch-branch` workflows.

## Plugin-specific rules

- Every git command goes through the network layer; steps and mods never shell out.
  Worktree commands too: add a service method instead of calling `run_in_worktree` from a step.
- Config: `GitPluginConfig` (`main_branch`, `default_remote`) in `titan_cli/core/plugins/models.py`.
- The repository may be in an unusual state (unborn branch, detached HEAD, rename in the
  index). Return a `ClientError` with a clear message, never assume a branch exists.
- Tests: `tests/{services,operations,steps,unit}`.
