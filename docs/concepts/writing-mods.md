# Writing a Mod

A mod is a folder with two files:

```text
~/.titan/mods/hello/
├── mod.toml     # what it is, what it needs, which events and slots it uses, its options
└── mod.py       # register(on, options)
```

Titan reads `mod.toml` **without running anything**, so a mod can be listed, explained and switched off before its code ever executes. For where to put the folder (yours, the team's, a plugin's) see [Mods](mods.md#where-mods-live).

## A first mod

```toml
# mod.toml
[mod]
name = "hello"
version = "0.1.0"
icon = "👋"
description = "A pane that counts the workflows run this session"
events = ["app.start", "workflow.run", "ui.render"]
slots = ["pane"]
```

```python
# mod.py
from titan_cli.core.mods import Box, Button, Text


def draw(m, width):
    runs = m.state.get("runs", 0)
    return Box(
        Text(f"Workflows run: {runs}", bold=True),
        Button("Reset", lambda: m.state.set("runs", 0)),
        border="info",
    )


def register(on, options):
    @on("app.start")
    def start(m, e, next):
        m.ui.open("hello", "Hello")          # a pane in the side panel
        m.state.set("runs", 0)
        return next(e)

    @on("workflow.run")
    def counted(m, e, next):
        try:
            return next(e)
        finally:
            if not e.nested:
                m.state.update("runs", lambda n: n + 1)

    @on("ui.render", match={"component": "Pane", "pane": "hello"})
    def render(m, e, next):
        return draw(m, e.width)
```

Restart Titan with `titan --mod-dir ~/code/hello`, or drop the folder in `~/.titan/mods/`. The folder is imported as the package `titan_mod_<name>`, with `mod.py` as its `__init__`, so a big mod splits into modules and imports them relatively (`from .sections import prs`).

## `mod.toml`

```toml
[mod]
name = "github"                       # letters, digits, _ and -, up to 64; must equal the folder name
version = "0.4.0"
icon = "⎇"                            # one character or emoji, on the rail, dock and home card
description = "..."
requires_plugins = ["github"]
events = ["app.start", "ui.render"]   # the only events register() may hook
slots = ["pane"]
ai_task = "PR check diagnosis"        # label of the AI routing task, if the mod uses m.ai

[options.refresh_seconds]             # typed, validated options
type = "int"                          # string | int | float | bool | list | choice
title = "Refresh every (s)"
default = 30                          # required
min = 1                               # int/float only; max too; choice takes `values = [...]`

[sections.queue]                      # a part the user can switch off
title = "Merge queue"
default = true
```

- **`events` is enforced.** Hooking an event not listed makes `register` fail and the mod load not at all.
- **Options** reach `register` as the `options` dict, defaults overridden by the user's `[mods.<name>.options]`. `sections` is reserved as an option name.
- **Sections** reach the mod as `options["sections"]`, a `{name: bool}`. Titan only keeps the switches: the mod decides what a switched-off section stops doing (polling, drawing).

## Events

`register(on, options)` hooks events with `@on(event, match={...})`. A hook is `hook(m, e, next)`:

- `m` is the mod's handle on Titan (below), `e` the event's frozen input.
- `next(e)` runs the hooks below this one and then Titan's own behaviour, and **returns its result**. Call it at most once.
- Return `next(e)` to observe, return something else to answer yourself, or pass `dataclasses.replace(e, ...)` to `next` to rewrite what the rest sees.

| Event | Input | Fires | Typical use |
|---|---|---|---|
| `app.start` | `AppStart(project_root)` | The TUI has mounted | Open panes, start timers, bind keys. Never block. |
| `workflow.run` | `WorkflowRun(workflow, source, nested)` | Around a whole workflow | React when it ends; `outcome(result)` reads the result as `"success"`, `"error"`, `"skip"` or `"exit"` |
| `step.call` | `StepCall(workflow, step_id, step_name, plugin, step, command, nested_workflow, params)` | Around one step | Guard (`return m.deny("reason")`) or rewrite `params` |
| `ui.render` | `UIRender(component, pane, width)` | A slot is drawn | Answer with an element tree |
| `section.change` | `SectionChange(section, enabled)` | The user switches one of *this* mod's sections while Titan runs | Start work when a section turns on |

`match` filters on the event's fields: `@on("ui.render", match={"component": "Pane", "pane": "hello"})`.

!!! note "Aborted workflows"
    A workflow the user aborts (`Ctrl+C`) never returns from `next`: it raises. A hook that must act however the run ends puts that code in a `finally`.

!!! warning "Hooks fail open"
    A hook that raises is logged and the chain carries on as if it had called `next(e)`. There are no fail-closed guards and no per-hook time budget: a `step.call` guard that crashes lets the step run.

## The `m` API

Every hook receives the same `m` for its mod.

| | |
|---|---|
| `m.ui.open(pane, title)` | Give the mod a pane in the side panel, drawn by its `ui.render` hook |
| `m.ui.badge(pane, text, severity)` | Text under the pane's rail icon (three characters at most); `None` removes it |
| `m.ui.dock(label, badge, severity, on_click)` | A tile in the dock; `None` as label removes it |
| `m.ui.home_card(title, text, on_click)` | A card on the home screen; `None` removes it |
| `m.ui.toast(text, severity)` | `information` or `warning`. An `error` is never a toast: it opens an error card (a modal with a copy button), so use `error_card` in your pane when the error belongs there |
| `m.ui.copy(text, what)` | Copy to the clipboard and say so |
| `m.state` | `get(key, default)` / `set` / `update(key, fn, default)`: in-memory values (`default` stands in for a missing key); every change repaints the mod's panes |
| `m.store` | `get` / `set`: small JSON values that survive the session (`~/.local/state/titan/mods/<mod>.json`) |
| `m.clock.every(seconds, fn, immediately=True)` | Run `fn` periodically on a background thread; a run still going is not doubled |
| `m.run(fn)` | Run `fn` once on a background thread |
| `m.client(name)` | The client of an installed, enabled plugin (`"git"`, `"github"`, `"jira"`), or `None` |
| `m.keys.bind(key, description, fn)` | App-wide key in Textual's spelling (`"f5"`, `"ctrl+k"`); refused if Titan or another mod has it, returning `False` |
| `m.workflows.run(name, params)` | Open a workflow as if the user picked it, with `params` over its own; refused while another runs |
| `m.workflows.resolve(name)` | The workflow `run(name)` would open (a repo's extension of it, if any), or None when this Titan has none |
| `m.ai` | See [AI](#ai) |
| `m.deny(reason)` | The answer for a `step.call` hook that blocks a step |
| `m.log` | A structured logger bound to the mod |

### Threading rules

Hooks, button handlers and key handlers run on the **UI thread**. Anything that waits goes elsewhere:

- Network calls (`m.client(...)` methods) and AI calls (`m.ai.complete`) block: make them from a `m.clock.every` callback or inside `m.run(...)`, **never** straight from a hook.
- `ui.render` must read only `m.state`. It never waits on the network: a timer fills `m.state`, the render draws it.
- Button `on_press` should be a state update, or hand slow work to `m.run`.

### Clients

`m.client("github")` returns what steps see: methods returning `ClientResult`, matched with `ClientSuccess` / `ClientError`. A mod uses the plugin's operations and UI models too; it keeps no copy of them. If a plugin lacks something generally useful, it belongs in the plugin (with its docs), not in the mod.

## Elements

`ui.render` answers with a tree of plain values; Titan decides how to draw them. Mods never touch Textual widgets.

```python
from titan_cli.core.mods import Box, Button, Link, Text

Box(
    Text("PRs", bold=True, color="info"),
    Text(Link("#12", url), " fix the thing", Text(" · 2d", dim=True)),
    has_error and Text(err, color="error"),     # falsy children are dropped
    Button("Review", on_review, variant="primary"),
    border="info",
)
```

| Element | Notes |
|---|---|
| `Text(*parts, color, bold, dim, wrap)` | Parts are strings, `Link`s or nested `Text` spans. Truncates with an ellipsis unless `wrap=True`. |
| `Link(label, url)` | Opens an http(s) URL. URLs in any text are links even when wrapped. |
| `Box(*children, border, row, indent, gap)` | Vertical group; `border` is a colour name; `row=True` puts children on one line: the first at the left, the rest pushed to the right (a title with a switch beside it). |
| `Button(label, on_press, dim, variant)` | With a `variant` (`primary`, `default`, `success`, `warning`, `error`) it is Titan's own button, for something that does work; without one it reads as a line of the pane, right for a fold or picker. `label` is a string, or a `Text` when parts of the line need their own style (a name plain, its date dim); a variant button flattens a `Text` to its words. |
| `error_card(message, copy=m.ui.copy, title, details, copy_text, what, actions, color)` | An **ErrorCard**: a bordered box with the error (wrapped, never cut off), its details dim and a "⧉ Copy error" button that puts it on the clipboard. `actions` are your own `Button`s beside Copy (a "✦ Ask AI to fix", say); `copy_text` replaces what is copied. Import it from `titan_cli.core.mods`. Steps show the same card with `ctx.textual.error_card(error, title, actions)`. |
| `choice_card(options, width, title, hint, state, key, close, border)` | A **choice card**: a bordered box that asks the user to pick, the standard way to offer actions to choose from. `options` are `Option(label, on_press, variant)`; pass the `width` your `ui.render` received: options that sit together go on one line when they fit, in a grid of equal cells when they do not, and in a column when only one fits. `Option(label, options=[...])` is a dropdown inside the card (`▸`/`▾`) and `Option(label, content=Box(...), on_open=fn)` one with a body of your own, such as a small form; `state=m.state` and `key` keep which one is open (one at a time; two cards in one pane need two keys) and `close` folds it after a pick. Mix options and dropdowns in one card instead of one card per kind. `None` options are dropped. Import `Option` and `choice_card` from `titan_cli.core.mods`. |
| `Input(value, placeholder, on_change, on_submit)` | A one-line text field. `on_change` fires on every keystroke — keep it to an `m.state` update, never a network or disk call; `on_submit` (optional) fires on Enter, the right place to kick off a search or write to `m.store`. |

Colours are semantic: `primary`, `accent`, `success`, `warning`, `error`, `info`, `subtle`. Lists are flattened and falsy children (`None`, `False`, `""`, `0`, `[]`) dropped, so conditionals and comprehensions read naturally.

## Slots

| Slot | How | Notes |
|---|---|---|
| Side panel pane | `m.ui.open` + `ui.render` | Right of every screen; rail icon from `mod.toml`'s `icon`, with `m.ui.badge` |
| Dock tile | `m.ui.dock` | Bottom bar, always visible |
| Home card | `m.ui.home_card` | Beside Quick launch |
| Toast | `m.ui.toast` | One-off notification |
| Key binding | `m.keys.bind` | Listed in the footer and in `?` |

The three visible slots are independent: a mod fills any mix, with different content in each (a count on the dock, detail in the pane, a summary and an action on the card). Titan's own prompts (`ask_*`) are never drawn by a mod, because their answer authorises an action.

## AI

`m.ai.complete(prompt, system=None, max_tokens=None, model=None, timeout=180)` returns an `AIAnswer` (`.text`, `.model`, `.error`, `.ok`). It goes through Titan's AI routing under the task `mods.<name>`: the user's connection or headless CLI, task pin, and `F2`/`F3` for the session all apply. It blocks, so call it from `m.run` or a timer.

To let the user choose who answers, call `m.ai.configure(title, on_done)` from a button: it opens the same pickers as the AI screen and writes the task pin. `m.ai.pinned()` and `m.ai.describe()` say who answers now (`describe` may probe: call it off the UI thread). Declare `ai_task` in `mod.toml` so the AI screen lists the task with a readable label.

## Secrets

The same rules as steps: no Titan API returns a secret string, and a mod never keeps a raw secret in `m.state`, `m.store` or a pane.

## Testing

Keep reading and drawing as plain functions over fake clients, and test them without mounting anything. `import_mod` imports a mod exactly as Titan does and `ModBus().api(name)` gives the `m` a hook receives:

```python
from pathlib import Path

import pytest
from titan_cli.core.mods import ModBus, Text, import_mod


@pytest.fixture(scope="session")
def mod():
    return import_mod(Path(__file__).resolve().parent.parent)


def test_draw_shows_the_count(mod):
    m = ModBus().api("hello")
    m.state.set("runs", 3)

    tree = mod.draw(m, 40)          # a plain function returning elements

    assert "Workflows run: 3" in tree.children[0].parts
```

To drive hooks, build a `ModBus`, give it a host with the methods your mod calls (`bus.host = SimpleNamespace(...)`), register with `mod.register(bus.on_for("hello"), options)` and fire events with `bus.dispatch("app.start", AppStart(project_root=...), lambda e: None)`. Without a host, `m.ui` only logs, timers never fire and no client is reachable.

A mod shipped by an official plugin keeps its tests beside it; they run with the plugin's own suite.

## Shipping a mod with a plugin

An official plugin ships mods by overriding `mods_path` on its plugin class, returning the folder that holds one subfolder per mod:

```python
@property
def mods_path(self) -> Optional[Path]:
    return Path(__file__).parent / "mods"
```

They load while the plugin is enabled, and the user can still switch any of them off. Add the mods' folder to `testpaths` in `pyproject.toml`, and document the mod in `docs/plugins/<plugin>/overview.md`.

## Verifying live

1. Run `titan-dev --mod-dir <folder>` and watch `~/.local/state/titan/logs/titan.log` for `mod_loaded`, `mod_load_failed` or `mod_hook_failed`.
2. Open the Mods screen (`m` on the home screen) to see the mod's status and switch its sections.
3. Restart after every edit: mods load at start and Titan does not watch their folders.
