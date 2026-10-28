# Mod checklist

Check before handing a mod over.

## Manifest
- [ ] `name` matches the folder (letters, digits, `_`, `-`); not `dirs`.
- [ ] Every event hooked in `mod.py` is listed in `events`; otherwise `register` fails and nothing loads.
- [ ] Each option has `type` and `default`; `choice` has `values`; `min`/`max` only on `int`/`float`; the name is not `sections`.
- [ ] `icon` is one character or emoji; `ai_task` set when `m.ai` is used.

## Hooks
- [ ] Every hook returns `next(e)` (or an answer); `next` is called at most once.
- [ ] `workflow.run` ignores `e.nested` unless it wants the inner runs, and acts in `finally` so an aborted run (Ctrl+C raises through `next`) is covered.
- [ ] A `step.call` guard knows hooks fail open: a crash lets the step run.
- [ ] `ui.render` has `match={"component": "Pane", "pane": "<id>"}` and returns an element tree built from `m.state` only.

## Threads
- [ ] No `m.client(...)`, `m.ai.complete` or other blocking call in a hook, a `Button.on_press` or a key handler: use `m.run` / `m.clock.every`.
- [ ] Sections: a switched-off section stops polling and drawing; `section.change` refreshes one that turns on.
- [ ] Anything needing a start root reads it from `AppStart.project_root`.

## Slots
- [ ] `m.ui.open` is called once (on `app.start`); the badge is at most three characters.
- [ ] Keys bound with `m.keys.bind` handle a `False` return (key already taken).
- [ ] Dock / home card / pane may differ in content; none is required.

## Errors
- [ ] Every error the pane shows is an `error_card` (copyable, with `actions` such as Retry), never a bare red `Text`; a failed read has a Retry that reruns it.
- [ ] A failure after a button press is a toast with `severity="error"` (the host opens the error card for it), not silence.

## Quality
- [ ] Logic in plain functions with tests over fake clients; no Textual mounting tests.
- [ ] No raw secret in `m.state`, `m.store`, panes or logs.
- [ ] Docs updated if the mod ships with an official plugin (`docs/plugins/<plugin>/overview.md`).
