# Workspaces

A **workspace** is a full screen dedicated to one service. Where a [mod](mods.md) is a small pane that is always at hand, a workspace is where you work on the service: its own layout, its own shortcuts, its own data. You open it from its tile in the dock and leave it with `Esc`.

This page is for people who **use** workspaces. To write one, see [Writing a Workspace](writing-workspaces.md).

## Workspaces, mods and plugins

| | What it is | Where you see it |
|---|---|---|
| **Mod** | A summary that reacts to what Titan does | Side panel, dock, home card, toasts |
| **Workspace** | The whole service on its own screen | A dock tile that opens a full screen |
| **Plugin** | Clients, steps and workflows | Inside workflows |

A workspace and a mod are loaded the same way and can share a name (`jira` works the same): the `github` mod is the summary in the side panel (what needs you now), and its **Open GitHub workspace** button, or pressing one of its PRs or runs, opens the `github` workspace, with that row already unfolded.

## What Titan ships

Titan itself ships the `cli` workspace, in every project:

| Workspace | Shows |
|---|---|
| `cli` (off by default, with its `cli` mod: `[workspaces.cli] enabled = true` and `[mods.cli] enabled = true`) | A full-screen terminal that runs the active CLI session (Claude, Gemini, Codex, OpenCode, Antigravity, Grok) inside Titan; with no session it lists the installed CLIs to start one. The menu to switch, start and close sessions is the `cli` [mod](mods.md)'s, in the side panel. A session keeps running when you leave the workspace (`ctrl+]`) and is the same one when you come back. The mouse wheel (or `shift+pageup`/`shift+pagedown`) scrolls back through the last 2000 lines and typing returns to the live screen; a CLI that reads the mouse, or runs full-screen, gets the wheel itself. Each session's memory is measured in the border and capped (`memory_limit_mb`, 2048 by default; a watchdog kills it past the limit everywhere, the systemd cgroup cap is Linux-only); every session is stopped when Titan quits |

Official plugins ship theirs, and they load while the plugin is enabled:

| Workspace | Plugin | Shows |
|---|---|---|
| `github` | github | The repo's pull requests (search, review, approve, merge, conflicts, check diagnosis), the merge queue and the latest workflow runs, in two columns that stack into one when the window is narrow |
| `jira` | jira | Jira issues narrowed by project, status, components, starred filters or a search, with the open issue's description, comments, AI summary, Move, Fix version, Plan and Take, in two columns that stack when the window is narrow |

### Recording a session for debugging

Set `TITAN_CLI_RECORD=<folder>` before starting Titan and every CLI session writes the raw bytes the CLI sent to `<folder>/<command>-<session id>.bin`, closed when the session ends. The folder must exist and be writable. The file contains everything the CLI printed, including your conversation and code, so use it only to debug a screen that renders wrong and delete it afterwards.

## Turning a workspace off

The Mods screen lists mods only. A workspace is switched by hand in `~/.titan/config.toml`:

```toml
[workspaces.github]
enabled = false                # false turns it off everywhere

[workspaces.github.sections]
queue = false                  # switch one section off

[workspaces.github.options]
prs_refresh_seconds = 60       # override a declared option
```

A workspace can ship off: `default_enabled = false` in the `[workspace]` of its `workspace.toml` (the `cli` one does). It stays off until `[workspaces.<name>] enabled = true` turns it on.

An option value that does not fit its declared type, or an option the workspace never declared, is dropped with a warning in the log; the workspace gets its default.

## Where workspaces live

Same order as mods, the most personal winning when two share a name:

| Order | Source | Folder |
|---|---|---|
| 1 (widest) | Titan | `titan_cli/workspaces/<name>/` |
| 2 | Plugin | the plugin's `workspaces_path` |
| 3 | Project | `<repo>/.titan/workspaces/<name>/` — shared with the team |
| 4 | User | `~/.titan/workspaces/<name>/` — yours |
| 5 (most personal) | Dev folders | `--workspace-dir <folder>` or `TITAN_WORKSPACE_DIRS`, one workspace each |

!!! warning "Workspaces are trusted code"
    A workspace runs inside Titan with your permissions; nothing sandboxes it. Committing one to `.titan/workspaces/` shares it with everyone who runs Titan in that repository. Only load workspaces you would run as scripts.

A workspace that fails to parse, import or register is logged and left out whole; it never stops Titan from starting.
