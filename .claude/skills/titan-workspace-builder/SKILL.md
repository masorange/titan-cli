---
name: titan-workspace-builder
description: Design and build a Titan workspace - a full screen dedicated to one service, opened from a dock tile (GitHub's PRs, queue and runs, say). Use when asked to create, modify or troubleshoot a workspace (workspace.toml + workspace.py), or to choose between a mod and a workspace. The side-panel summary is titan-mod-builder's; workflows and steps belong to the workflow-builder skills.
disable-model-invocation: false
---

# Titan Workspace Builder

Build a workspace: a folder with `workspace.toml` and `workspace.py` (`register(w, on, options)`)
that answers `w.ui.view` with an element tree for a whole screen. It is loaded by the mods' own
loader, so everything in `titan-mod-builder` about state, timers, threads and tests holds here.
The docs hold the facts and this skill holds the order of work; open them rather than copying:

- `docs/concepts/writing-workspaces.md` - what differs from a mod: view, `on_start`, `on_open`, events, testing.
- `docs/concepts/writing-mods.md` - the handle (`state`, `clock`, `keys`, `store`, `ai`, `workflows`), elements, options, sections.
- `docs/concepts/workspaces.md` - where workspaces live and how the user switches one off.
- `.claude/docs/mods.md` - only when changing the loader or the host (`titan_cli/core/mods/`).

## 1. Decide it is a workspace

| The ask | Use |
|---|---|
| Work on one service on a whole screen: lists, search, actions, several sections | **Workspace** |
| A glance that is always at hand, on every screen (a count, a branch, a short list) | Mod (`titan-mod-builder`) |
| Both: the glance and the full screen | A mod **and** a workspace of the same name; the mod's rows open the workspace on them with `m.ui.open_workspace(name, focus=...)` |
| A sequence of actions the user runs | Workflow (`titan-project-workflow-builder`) |

A workspace decides its own layout, shortcuts and data; Titan only provides the screen, `Esc`,
the header, toasts and error cards. Do not build a generic "sections" framework first: build the
service's screen, then extract what a second service proves to be shared.

## 2. Choose where it lives

| For | Folder |
|---|---|
| Yourself | `~/.titan/workspaces/<name>/` |
| The team (committed, runs for everyone) | `<repo>/.titan/workspaces/<name>/` |
| A workspace an official plugin ships | the plugin's `workspaces_path` (`plugin_base.py`) |
| Developing from its own checkout | any folder, loaded with `titan --workspace-dir <folder>` |

Folder name = `workspace.toml` name (except a `--workspace-dir` checkout). The Mods screen does not
list workspaces: the user switches one off in `~/.titan/config.toml` under `[workspaces.<name>]`.

## 3. Reuse before inventing

1. Look at the one that exists: `plugins/titan-plugin-github/titan_plugin_github/workspaces/github/`
   (`workspace.py` wires, `draw.py` draws, `sections/` holds the actions, `tests/`), and its mod beside
   it in `mods/github/`. It is the only workspace so far: what it does is proven for one service only
   (see [references/workspace-checklist.md](references/workspace-checklist.md), "Proven by one service").
2. Data comes from a plugin client (`w.client("github")`) and the plugin's operations and UI models.
   If the plugin lacks something, that is `titan-plugin-capability`, not the workspace.
3. If a mod of the same service reads the same data, put the readers and snapshots in an ordinary
   package of the plugin (`titan_plugin_github/readers/`) and import them from both. Neither imports the other.
4. Elements and cards are Titan's: `Box`, `Text`, `Button`, `Input(size="normal")`, `Columns` /
   `responsive_columns`, `choice_card`, `error_card`, `ai_assist_button`. A missing look is a widget
   property or a registered `Component`, not a raw Textual widget.

## 4. Write it

1. `workspace.toml`, as a mod's manifest minus `slots` (a workspace has one screen): the **`events`**
   it hooks are enforced, `[options.*]` are typed with defaults, `[sections.*]` are parts the user
   may switch off, and `ai_task` / `ai_assist_task` name its AI calls.
2. `workspace.py`: `register(w, on, options)`:
   - `w.ui.view(fn, title)` - `fn(width)` reads `w.state` only and answers with the tree.
   - `w.on_start(fn)` - the dock tile (`w.ui.dock(label, on_click=w.ui.open_workspace)`), timers, keys.
     `register` runs before there is a screen, so a `w.ui` call there goes nowhere.
   - `w.on_open(fn)` - `fn(w, focus)` when the screen opens: unfold what a mod's row pointed at.
   - `@on("workflow.run")` and friends, only for events the manifest lists (`try/finally` around `next(e)`).
3. Keep reading, drawing and acting as **plain functions** in their own modules; `register` only wires.
4. Draw for the width it gets: `responsive_columns(width, [left, right], ratio=(3, 2), collapse_below=120)`
   with each builder given its column's width; keep text fields **outside** the columns, crossing the
   threshold rebuilds what is inside.
5. Threading, as for mods: network, client and AI calls only from `w.clock.every` or `w.run`, never
   from the view, a hook or a button handler. The view never waits.
6. No raw secrets in `w.state`, `w.store`, the tree or logs.

## 5. Test it

Pure functions over fake clients, no Textual mounting tests. `import_mod(folder, kind=WORKSPACES)`
imports it as Titan does; `ModBus(prefix="workspace.", store_dir="workspaces")` gives the bus and
`bus.api(name)` the `w`; a `SimpleNamespace` host with only the methods it calls records `dock`, `every`,
`run`, `toast`. Drive `bus.start()` (the `on_start` functions), `bus.opened(name, focus)`, `bus.dispatch(...)`
and `bus.render_view(name, width)`, then read the tree. See `workspaces/github/tests/` for the pattern.
Run: `poetry run pytest <workspace folder>`.

## 6. Verify live

Restart `titan-dev` (workspaces load at start; `--workspace-dir <folder>` for a checkout), then check
`~/.local/state/titan/logs/titan.log` for `workspace_loaded` / `workspace_load_failed` /
`workspace_start_failed` / `workspace_open_failed`, and open the screen: the dock tile shows, `Esc`
comes back, resize the window across `collapse_below`, press a mod's row if there is one. Tests cannot
prove a screen: if you did not open it, tell the user so.

## 7. Hand off

Say where the workspace is and how to load it, its options and sections, and how to switch it off
under `[workspaces.<name>]`. A workspace in `.titan/workspaces/` is shared with whoever runs Titan in
that repo: say so. One shipped with an official plugin also needs `docs/plugins/<plugin>/overview.md`.
If the loader, the host or a widget changed, run the `titan-architecture-reviewer` agent on the diff.
