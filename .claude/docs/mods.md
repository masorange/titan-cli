# Mods (contributor guide)

User docs: `docs/concepts/mods.md` (using) and `docs/concepts/writing-mods.md` (authoring: manifest,
events, `m` API, elements, testing). Read those first; this page is only what a contributor
changing Titan itself needs. Building a mod: the `titan-mod-builder` skill; a workspace: `titan-workspace-builder`.

## Where the code is

- `titan_cli/core/mods/` — the system, UI-free: `bus.py` (`ModBus`, `ModAPI`, `ModHost` protocol,
  `DockSlot`, `HomeCardSlot`), `loader.py` (sources, manifest, load/reload), `events.py`,
  `options.py`, `sections.py`, `settings.py`, `state.py`, `store.py`, `keys.py`,
  `status.py`. Public names are re-exported from `titan_cli/core/mods/__init__.py`.
  Elements (`Box`, `Button`, `Input`, `Link`, `Text`) live in `titan_cli/ui/elements.py` and the
  cards (`Option`, `choice_card`, `error_card`, `fix_with_ai_button`) in `titan_cli/ui/components/`:
  visual pieces any mod, workspace or workflow can use.
- TUI side: `ui/tui/mods_ui.py` (`TitanModHost`, the `ModHost` implementation),
  `widgets/mod_side_panel.py` (the panel) and `widgets/element_widgets.py` (elements as widgets,
  repainted in place through the `Updatable` contract; `widgets/registry.py` holds the widgets mods bring
  with `m.ui.widget`), `widgets/dock.py`, the home card in `screens/main_menu.py`,
  `screens/mods_screen.py`, `screens/task_ai_picker.py`.
- Events are dispatched from `app.py` (`app.start`), `textual_workflow_executor.py`
  (`workflow.run`, `step.call`), `mods_ui.py` (`ui.render`) and `ModBus.set_section`
  (`section.change`).

## Workspaces share the loader

A workspace is loaded by the mods' own code, parametrized by `Kind` in `loader.py` (`MODS`,
`WORKSPACES`): `workspace.toml` + `workspace.py` with `register(w, on, options)`, the same sources
(`workspaces_path` on `plugin_base.py`, `.titan/workspaces/`, `~/.titan/workspaces/`,
`--workspace-dir`, `TITAN_WORKSPACE_DIRS`) and the `[workspaces.<name>]` config table. `w` is a
`ModAPI` and `register` also gets the `on` of its bus (hooks `workflow.run`, `step.call`, `section.change`, only the events its `workspace.toml` lists; the executor runs the workspaces' bus before the mods'); its bus puts `workspace.` before every name it hands the host, so a mod and
a workspace called alike never share timers, keys, store or AI task. `TitanApp.workspaces` is that bus;
it uses the same `TitanModHost`. A workspace answers `w.ui.view(fn, title)` (an element tree for a
width) and its dock tile calls `w.ui.open_workspace`, put there from `w.on_start(fn)`: `register` runs before the
host exists (a `w.ui` call there only logs), `TitanApp.on_mount` runs `workspaces.start()` after it; `screens/workspace_screen.py` draws it with
`reconcile`, and `TitanModHost._repaint_now` redraws it on a `w.state` change. `w.on_open(fn)` runs `fn(w, focus)` when the screen opens (`bus.opened`), with what the opener passed to `ui.open_workspace(name, focus)`. A new capability on `m` is on `w` too: do not fork `ModAPI`. Users' and authors' docs: `docs/concepts/workspaces.md`, `writing-workspaces.md`.

## Rules

- A new `m` capability is a method on `ModAPI`/`_Mod*` **and** on the `ModHost` protocol **and** on
  `_HeadlessHost` (the no-TUI fallback), implemented in `TitanModHost`. Tests drive mods through a
  fake host, so a missing headless method breaks them silently.
- A new event goes in `ModBus.EVENTS`, an input dataclass in `events.py`, and is exported from
  `__init__.py`. Mods hook only what their `mod.toml` `events` lists.
- Mods take plugin clients through `m.client(...)`; a mod never calls network code directly.
  Something generally useful that a plugin lacks goes into the plugin, with tests and
  `docs/plugins/<plugin>/` updated.
- No raw secret through `m` (see [security.md](security.md)).
- Elements stay plain values; Titan draws them with its own widgets. Never hand a mod a Textual
  widget.
- AI goes through `m.ai` only (the user's routing, see [ai-agents.md](ai-agents.md)): a mod never
  names a CLI, a connection or a model. `complete` runs under `mods.<name>`; the help button
  (`ai_assist_button`) under `mods.<name>.assist`, declared as `ai_assist_task` in `mod.toml`.
- No UI-mounting tests: test mod logic as pure functions, verify slots live in `titan-dev`.

## Shipping a mod with an official plugin

Override `mods_path` in the plugin class (`plugin_base.py`) to return the folder with one
subfolder per mod (`mod.toml` + `mod.py`), add that folder to `testpaths` in `pyproject.toml`, and
describe the mod in `docs/plugins/<plugin>/overview.md`. Existing examples:
`plugins/titan-plugin-git/titan_plugin_git/mods/git/`,
`plugins/titan-plugin-github/titan_plugin_github/mods/github/`,
`plugins/titan-plugin-jira/titan_plugin_jira/mods/jira_ready/`.

## Running

Restart `titan-dev` after editing a mod (mods load at start). `titan-dev --mod-dir <folder>` loads one
from a checkout. Logs: `mod_loaded`, `mod_load_failed`, `mod_hook_failed` in
`~/.local/state/titan/logs/titan.log`.
