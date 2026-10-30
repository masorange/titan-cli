# Writing a Workspace

A workspace is a folder with two files, the same shape as a [mod](writing-mods.md):

```text
~/.titan/workspaces/hello/
├── workspace.toml   # what it is, what it needs, which events it hooks, its options and sections
└── workspace.py     # register(w, on, options)
```

Read [Writing a Mod](writing-mods.md) first: a workspace uses the same handle, the same `state`, `clock`, `keys`, `store`, `ai` and `workflows`, the same element tree and the same options and sections. This page covers only what differs.

## A first workspace

```toml
# workspace.toml
[workspace]
name = "hello"
version = "0.1.0"
icon = "👋"
description = "A screen that counts the workflows run this session"
events = ["workflow.run"]
```

```python
# workspace.py
from titan_cli.ui.elements import Box, Text


def register(w, on, options):
    w.state.set("runs", 0)

    w.ui.view(lambda width: Box(Text(f"{w.state.get('runs')} workflows run", bold=True)), title="Hello")
    w.on_start(lambda w: w.ui.dock("Hello", on_click=w.ui.open_workspace))

    @on("workflow.run")
    def count(w, e, next):
        try:
            return next(e)
        finally:
            if not e.nested:
                w.state.update("runs", lambda n: (n or 0) + 1)
```

Restart Titan: a "Hello" tile appears in the dock; it opens the screen and `Esc` goes back. Changing `w.state` redraws the screen.

## What differs from a mod

| | Mod | Workspace |
|---|---|---|
| Entry point | `mod.toml` + `mod.py`, `register(on, options)` | `workspace.toml` + `workspace.py`, `register(w, on, options)` |
| What it draws | Panes, dock tile, home card (`ui.render` hook) | One full screen: `w.ui.view(fn, title)` |
| Handle | `m`, given to every hook | `w`, given to `register`; hooks get it as their first argument |
| Config table | `[mods.<name>]` | `[workspaces.<name>]` |
| Events | `app.start`, `workflow.run`, `step.call`, `ui.render`, `section.change` | `workflow.run`, `step.call`, `section.change` |
| Run once the screen exists | `app.start` hook | `w.on_start(fn)` |
| Listed in the Mods screen | Yes | No (edit `~/.titan/config.toml`) |

### The view

`w.ui.view(fn, title=None)` registers `fn(width)`, which answers with an element tree for a screen `width` columns wide. Titan calls it again when the window is resized and whenever `w.state` changes, and patches what is on screen instead of redrawing it, so a focused button or a half-typed field survives. `title` heads the screen (it defaults to the workspace's name). `fn` reads `w.state` only: never the network or the disk.

For two columns that stack on a narrow window use `responsive_columns`, and keep any text field outside the columns:

```python
from titan_cli.ui.elements import Box, responsive_columns

def view(width):
    return Box(
        search_field(),
        responsive_columns(width, [left, right], ratio=(3, 2), collapse_below=120),
    )
```

Each builder gets the width its column has, so a `choice_card` or a wrapped line fits either layout. The elements are in [Writing a Mod](writing-mods.md#elements).

### Starting and opening

`register` runs while Titan is still building, before there is a screen: a `w.ui` call there goes nowhere. Put what needs the screen (the dock tile, timers, keys) in `w.on_start(fn)`, which runs `fn(w)` once the interface is up. `w.ui.view` is fine in `register`: it only stores the function.

`w.on_open(fn)` runs `fn(w, focus)` each time the screen is opened, before it draws. `focus` is whatever the opener passed to `open_workspace(name, focus=...)`, `None` from the dock tile. A mod uses it to point you at the thing it listed:

```python
# in the mod: pressing a PR opens the workspace on it
m.ui.open_workspace("github", focus={"pr": 42})

# in the workspace: unfold that row
def focus(w, what):
    if isinstance(what, dict) and what.get("pr"):
        w.state.update("rows_open", lambda rows: {**(rows or {}), str(what["pr"]): True}, default={})

w.on_open(focus)
```

`open_workspace(name)` returns `False` and shows a toast when there is no such workspace.

### Events

A workspace hooks only the events its `workspace.toml` lists in `events`, with the `on` it receives, exactly as a mod does. A workspace's hooks wrap a workflow outside the mods' ones. `app.start` and `ui.render` are not available: use `w.on_start` and `w.ui.view`.

## Sharing code with a mod

When a mod and a workspace read the same service, put the readers and the snapshots they build in an ordinary package of the plugin and import them from both; neither imports the other, and either may be switched off. The `github` plugin does it with `titan_plugin_github/readers/`.

## Where to put it

| You want | Put it in |
|---|---|
| Yours, for every project | `~/.titan/workspaces/<name>/` |
| The team's, in one repo | `<repo>/.titan/workspaces/<name>/` |
| Shipped with an official plugin | the folder the plugin's `workspaces_path` returns |
| Under development | anywhere, then `titan --workspace-dir <folder>` |

See [Workspaces](workspaces.md) for the full order and the config.

## Testing

Test the view as a pure function: build a `ModBus(prefix="workspace.", store_dir="workspaces")`, take `bus.api(name)`, set `w.state`, call `bus.render_view(name, width)` and read the tree. `import_mod(folder, kind=WORKSPACES)` imports the folder exactly as Titan does. Run `bus.start()` to fire the `w.on_start` functions and `bus.opened(name, focus)` for `w.on_open`.
