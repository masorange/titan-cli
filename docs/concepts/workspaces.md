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

Official plugins ship their workspaces, and they load while the plugin is enabled:

| Workspace | Plugin | Shows |
|---|---|---|
| `github` | github | The repo's pull requests (search, review, approve, merge, conflicts, check diagnosis), the merge queue and the latest workflow runs, in two columns that stack into one when the window is narrow |
| `jira` | jira | Jira issues narrowed by project, status, components, starred filters or a search, with the open issue's description, comments, AI summary, Move, Fix version, Plan and Take, in two columns that stack when the window is narrow |

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
