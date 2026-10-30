---
name: titan-mod-builder
description: Design and build a Titan mod - a change to Titan's own interface or behaviour such as a side-panel pane, a dock tile, a home card, a toast, a key binding, or a hook on workflows and steps. Use when the user wants to make, change or debug a mod (mod.toml + mod.py), or asks what a mod can do. Not for a full-screen workspace (use titan-workspace-builder) nor for workflows or steps (use the titan-*-workflow-builder skills).
disable-model-invocation: false
---

# Titan Mod Builder

Build a mod: a folder with `mod.toml` and `mod.py` (`register(on, options)`) that hooks Titan's
events and draws in named slots. The docs are the source of truth; this skill is the procedure.
Read them instead of restating them:

- `docs/concepts/mods.md` - what a mod is, where it lives, how the user switches it off.
- `docs/concepts/writing-mods.md` - manifest, events, the `m` API, elements, slots, AI, testing.
- `.claude/docs/mods.md` - only when changing the mod system itself (`titan_cli/core/mods/`).

## 1. Decide it is a mod

| The ask | Use |
|---|---|
| Something always visible or reacting to what Titan does (PR count, branch, a card) | **Mod** |
| The whole service on its own screen, with lists, search and actions | Workspace (`titan-workspace-builder`); keep the mod as its summary |
| A sequence of actions the user runs | Workflow (`titan-project-workflow-builder`) |
| A reusable action inside workflows | Step / plugin |

If a mod only needs to run a workflow on a button, it still is a mod: `m.workflows.run`.

## 2. Choose where it lives

| For | Folder |
|---|---|
| Yourself | `~/.titan/mods/<name>/` |
| The team (committed, runs for everyone) | `<repo>/.titan/mods/<name>/` |
| A mod an official plugin ships | the plugin's `mods_path` (see `.claude/docs/mods.md`) |
| One Titan ships | `titan_cli/mods/<name>/` |
| Developing from its own checkout | any folder, loaded with `titan --mod-dir <folder>` |

Folder name = `mod.toml` name (except a `--mod-dir` checkout). Most personal source wins on a name
clash. Ask only if the user's intent is ambiguous between yourself and the team.

## 3. Reuse before inventing

1. Look at an existing mod close to the ask: `plugins/titan-plugin-git/titan_plugin_git/mods/git/` is
   the smallest, `.../github/mods/github/` shows a badge, toasts and the way into a workspace; the
   github workspace (`.../github/workspaces/github/`) shows sections, AI and workflows.
2. Data comes from a plugin client (`m.client("github")`) and the plugin's operations and UI models.
   If the plugin lacks something generally useful, add it to the plugin (with docs), not to the mod.
   A personal mod may build what a plugin lacks.

## 4. Write it

1. `mod.toml`: name, version, `icon`, description, `requires_plugins`, **`events` it will hook**
   (enforced), `slots`, typed `[options.*]` with defaults, `[sections.*]` for parts the user may
   switch off, `ai_task` if it calls AI.
2. `mod.py`: `register(on, options)`. Pick the event from the ask:

| The ask | Event |
|---|---|
| A panel, tile, timer, key set up when Titan opens | `app.start` (+ `ui.render` for a pane) |
| React when a workflow ends | `workflow.run` (`try/finally` around `next(e)`; skip `e.nested`) |
| Block or rewrite a step | `step.call` (`m.deny(...)` or `next(replace(e, params=...))`) |
| Start work when a section is switched on | `section.change` |

3. Keep reading and drawing as **plain functions** in their own modules (`draw.py`, `models.py`,
   `sections/<name>/`); `register` only wires them.
4. Follow the threading rules, which are the usual source of bugs:
   - Network, client and AI calls only from `m.clock.every` or `m.run`, never from a hook or a
     button handler (UI thread).
   - `ui.render` reads only `m.state`; a timer fills it.
   - Always `return next(e)` unless the hook answers on its own.
5. No raw secrets in `m.state`, `m.store`, panes or logs.

Full checklist of pitfalls: [references/mod-checklist.md](references/mod-checklist.md).

## 5. Test it

Test the pure functions with fake clients, as `plugins/titan-plugin-git/titan_plugin_git/mods/git/tests/`
does: `import_mod(folder)` imports the mod as Titan does, `ModBus().api(name)` gives the `m`, and a
`SimpleNamespace` host with only the methods the mod calls drives `bus.dispatch(...)`. No Textual
mounting tests. Run: `poetry run pytest <mod folder>`.

## 6. Verify live

Restart `titan-dev --mod-dir <folder>` (mods load at start, Titan does not watch the folder), then
check `~/.local/state/titan/logs/titan.log` for `mod_loaded` / `mod_load_failed` / `mod_hook_failed`, and
look at the slot itself. A UI slot cannot be proved by tests; say plainly when you did not see it.

## 7. Hand off

Tell the user where the mod is, how to load it, which options and sections it has, and that a
project mod is shared with everyone who runs Titan in that repo. If it ships with an official
plugin, update `docs/plugins/<plugin>/overview.md` too.
