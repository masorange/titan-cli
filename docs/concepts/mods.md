# Mods

A **mod** is a small piece of Python that changes Titan's own interface: a live pane in the side panel, a tile in the dock, a card on the home screen, a toast, a key binding. It reacts to what Titan does (the app starting, a workflow running, a step being called) and reads data through the plugins' clients and Titan's AI routing.

This page is for people who **use** mods. To write one, see [Writing a Mod](writing-mods.md).

## Mods, plugins and workflow hooks

| | What it adds | Written in | Runs |
|---|---|---|---|
| **Plugin** | Clients, steps and workflows | Python package | When a workflow calls it |
| **Workflow hook** | Extra steps inside one workflow | YAML | Inside that workflow |
| **Mod** | Things on Titan's screens, reactions to events | One folder, Python + `mod.toml` | For the whole session |

A mod does not add workflow steps and a plugin does not draw on screen. A mod usually *reads* a plugin: the built-in `github` mod shows your PRs by calling the GitHub plugin's client.

## What Titan ships

Official plugins ship their own mods, and they load while the plugin is enabled:

| Mod | Plugin | Shows |
|---|---|---|
| `git` | git | Branch, upstream, recent commits |
| `github` | github | PRs waiting for your review (with a Review button), your PRs, merge queue, AI diagnosis of failed checks |
| `jira_ready` | jira | Issues narrowed by status and filters read from Jira, with description, comments and an AI summary |

## Where you see a mod

- **Side panel** — on the right of every screen, folded to a rail of icons. `F4` or a click on an icon opens it. A mod can badge its icon (the `github` mod shows how many reviews wait for you).
- **Dock** — the bottom bar. Titan's tiles first, then the mods'. `F6` folds it to one row.
- **Home card** — a "🧩 Mods" section under Quick launch, shown only when some mod fills it.
- **Toasts and keys** — a mod may notify you and bind keys (`F5` refreshes the git and github panes). `?` lists every key, mods' included.

## Turning mods and sections on and off

From the home screen press `m` (or use the Mods tile in the dock) to open the **Mods screen**. It lists every mod found, grouped by where it comes from, with a switch per mod and one per *section* (a part of the mod, for example `github`'s `prs` and `queue`). Changes apply at once and are saved per project in your own `~/.titan/config.toml`, so switching a mod off in one repository never touches the team's `.titan/config.toml`.

By hand, in `~/.titan/config.toml`:

```toml
[mods.github]
enabled = true                 # false turns it off everywhere

[mods.github.sections]
queue = false                  # switch one section off

[mods.github.options]
prs_refresh_seconds = 60       # override a declared option
```

An option value that does not fit its declared type, or an option the mod never declared, is dropped with a warning in the log; the mod gets its default.

## Where mods live

Titan looks in several places. When two mods share a name, the **most personal wins**:

| Order | Source | Folder |
|---|---|---|
| 1 (widest) | Titan | `titan_cli/mods/<name>/` |
| 2 | Plugin | the plugin's `mods_path` |
| 3 | Project | `<repo>/.titan/mods/<name>/` — shared with the team |
| 4 | User | `~/.titan/mods/<name>/` — yours |
| 5 (most personal) | Dev folders | any folder, see below |

!!! warning "Mods are trusted code"
    A mod runs inside Titan with your permissions; nothing sandboxes it. Committing a mod to `.titan/mods/` is sharing it with everyone who runs Titan in that repository, exactly like `.titan/steps/`. Only load mods you would run as scripts.

A mod that fails to parse, import or register is logged and left out whole. It never stops Titan from starting. A hook that raises never takes a workflow down either: the error is logged and the chain carries on.

### Developing a mod from its own checkout

Each of these points at **one mod folder**, loaded above every other source (the manifest's name wins over the folder's name):

```bash
titan --mod-dir ~/code/my-mod            # repeatable
TITAN_MOD_DIRS=~/code/a:~/code/b titan   # separated like PATH
```

```toml
# ~/.titan/config.toml (user config only, never the project's)
[mods]
dirs = ["~/code/my-mod"]
```

Titan does not watch these folders: restart it after editing a mod.

## Next

- [Writing a Mod](writing-mods.md) — manifest, events, the `m` API, elements, testing.
