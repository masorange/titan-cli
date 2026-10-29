# Mods (contributor guide)

User docs: `docs/concepts/mods.md` (using) and `docs/concepts/writing-mods.md` (authoring: manifest,
events, `m` API, elements, testing). Read those first; this page is only what a contributor
changing Titan itself needs. Building a mod: the `titan-mod-builder` skill.

## Where the code is

- `titan_cli/core/mods/` — the system, UI-free: `bus.py` (`ModBus`, `ModAPI`, `ModHost` protocol,
  `DockSlot`, `HomeCardSlot`), `loader.py` (sources, manifest, load/reload), `events.py`,
  `elements.py`, `options.py`, `sections.py`, `settings.py`, `state.py`, `store.py`, `keys.py`,
  `status.py`. Public names are re-exported from `titan_cli/core/mods/__init__.py`.
- TUI side: `ui/tui/mods_ui.py` (`TitanModHost`, the `ModHost` implementation),
  `widgets/mod_side_panel.py`, `widgets/dock.py`, the home card in `screens/main_menu.py`,
  `screens/mods_screen.py`, `screens/task_ai_picker.py`.
- Events are dispatched from `app.py` (`app.start`), `textual_workflow_executor.py`
  (`workflow.run`, `step.call`), `mods_ui.py` (`ui.render`) and `ModBus.set_section`
  (`section.change`).

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
