# Workspace checklist

Check before handing a workspace over. The mod checklist (`../../titan-mod-builder/references/mod-checklist.md`)
applies too for threads, errors and quality; this adds what is specific to a screen.

## Manifest
- [ ] The folder is named like the manifest's `name`; the files are `workspace.toml` and `workspace.py`.
- [ ] `register(w, on, options)`: the three arguments, in that order.
- [ ] A hook on an event the manifest does not list makes `register` fail. The events a workspace has are `workflow.run`, `step.call` and `section.change`; `app.start` and `ui.render` do not exist here.
- [ ] `ai_task` set when `w.ai.complete` is used, `ai_assist_task` when an assist button is.

## Start and open
- [ ] The dock tile, timers and keys are in `w.on_start`, not in `register`.
- [ ] A hook that must wait for the screen checks it started (as `workspace.py` of github does with `started`).
- [ ] `w.on_open` tolerates `focus` being `None` or a shape it does not know.
- [ ] Opening state in `on_open` is set before the screen draws; nothing there blocks.

## View
- [ ] `fn(width)` reads `w.state` only and never raises on a half-loaded state (`None` -> "Loading…").
- [ ] Every section a user can switch off is checked in the view and stops polling.
- [ ] Two columns go through `responsive_columns`, each builder using the width it is given.
- [ ] Text fields sit outside `Columns`.
- [ ] A line that can be long is one line in the list and whole once opened.
- [ ] Every error shown is an `error_card` with a Retry that rereads.

## Shared with a mod
- [ ] Readers and snapshots live in a plugin package both import; neither imports the other.
- [ ] A mod row that opens the workspace sends a `focus` the workspace handles.
- [ ] Both can be switched off alone and nothing breaks.

## Proven by one service only
Written from the GitHub workspace; a second workspace may show these are not generic:
- `w.on_start` / `w.on_open`, and `focus` as a free-form dict.
- Hooks limited to `workflow.run`, `step.call`, `section.change`: a service that needs `app.start` or `ui.render` would extend the bus, not work around it.
- A single `view` per workspace (no tabs or nested screens).
- `Columns` with a fixed `collapse_below`; one threshold, no per-column minimum width.
- Not listed in the Mods screen: switching off is by hand in the config.
