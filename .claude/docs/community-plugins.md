# Community Plugins

## Overview

Titan supports community plugins in addition to the official plugins bundled with the CLI.

There are two source channels:

- `stable`: a shared project pin stored in `.titan/config.toml`
- `dev_local`: a user-local override stored in `~/.titan/config.toml`

Titan itself can remain globally installed, while project-pinned community plugins are prepared in isolated local runtimes.

---

## Key Files

| File | Role |
|------|------|
| `titan_cli/core/plugins/community_sources.py` | URL parsing, metadata preview, ref resolution, update checks |
| `titan_cli/core/plugins/runtime.py` | Isolated runtime/cache manager for `stable` community plugins |
| `titan_cli/core/plugins/models.py` | Plugin source config model |
| `titan_cli/core/plugins/plugin_registry.py` | Resolves effective source and loads `dev_local` or cached `stable` plugin code |
| `titan_cli/ui/tui/screens/install_plugin_screen.py` | Adds a stable community plugin to the current project |
| `titan_cli/ui/tui/screens/plugin_management.py` | Displays source state and handles update/remove/dev override actions |

---

## Source Model

### Shared project pin (`stable`)

The shared stable source lives in `.titan/config.toml`:

```toml
[plugins.custom]
enabled = true

[plugins.custom.source]
channel = "stable"
repo_url = "https://github.com/user/titan-plugin-custom"
requested_ref = "v1.2.0"
resolved_commit = "0123456789abcdef0123456789abcdef01234567"
```

Notes:
- `requested_ref` stores the exact tag/ref used by that repository
- `resolved_commit` is the operational truth
- this block is meant to be committed and reviewed in PRs

### User-local override (`dev_local`)

The active local development override lives in `~/.titan/config.toml`:

```toml
[plugins.custom.source]
channel = "dev_local"
path = "/absolute/path/to/local/plugin/repo"
```

Notes:
- this is not committed to the project
- if present, it wins over the project's `stable` pin on that machine
- when switching back to `stable`, the remembered `path` may stay in global config as UX state, but it is ignored

---

## Resolution Rules

Titan resolves the effective source in this order:

1. global `dev_local` override
2. project `stable` pin

If neither exists, the plugin is treated as a normal installed plugin with no community source metadata.

---

## Stable Install Flow

### 1. URL

The user enters a URL with an explicit ref:

```text
https://github.com/user/titan-plugin-custom@v1.2.0
https://github.com/user/titan-plugin-custom@abc123def456
```

Bare repository URLs without `@ref` are rejected.

### 2. Preview

Titan fetches `pyproject.toml` from that source and shows:
- package name
- version
- description
- authors
- Titan entry points
- Python dependencies

### 3. Pin + runtime

Titan resolves the requested ref to a full commit SHA and then:

1. writes the shared stable pin into the current project's `.titan/config.toml`
2. prepares an isolated runtime for that plugin commit
3. reloads config/registry so the plugin becomes available immediately

### 4. Done

The wizard shows the pinned ref/commit and the Titan plugin name if found.

---

## Runtime Layout

Stable community plugins are prepared in a cache like:

```text
~/.titan/plugin-cache/<plugin_name>/<resolved_commit>/
  src/
  venv/
```

The runtime manager:

1. checks out the pinned commit into `src/`
2. creates a dedicated `venv/`
3. installs the plugin into that isolated environment

The plugin registry then loads the plugin from:
- the cached source directory, **prepended** to `sys.path`
- the cached `site-packages`, **appended** to `sys.path`

### Import resolution: the host always wins

That ordering is the whole contract, and it is not symmetric on purpose
(`_extend_import_path`, plugin_registry.py).

A cached venv is not a sandbox. Plugins run in Titan's interpreter, which has one
`sys.modules`: whatever a directory wins, it wins for **everyone**, not just for the
plugin that brought it. So the cached `site-packages` is searched **last** — it fills
gaps (a library Titan does not ship, e.g. `PyJWT`) and never overrides. The plugin's own
source is searched **first**, which is what makes a `dev_local` checkout beat an
installed copy of the same plugin.

The reverse ordering caused a real incident: a community plugin declaring `titan-cli` as
an ordinary dependency got Titan installed inside its venv, official plugins and AI SDKs
included. With that directory searched first, every `titan_plugin_*` import in the whole
application resolved to the plugin's frozen copies, so edits to official plugins were
silently ignored — for months, under both `titan` and `titan-dev`. The core escaped only
because `titan_cli` is already in `sys.modules` before any plugin loads, which made the
symptom look arbitrary: core changes applied, plugin changes did not.

The trade-off is deliberate. A plugin cannot be guaranteed the exact dependency versions
it was tested against, because granting that means imposing them on the application.
A plugin that breaks under the host's version is a contained, explainable failure;
Titan breaking underneath the user is not.

---

## Plugin Dependency Rules

For anyone authoring a community plugin:

**`titan-cli` is the host, never an install dependency.** Titan is already running and
already imported when it loads the plugin. Declare it as optional so pip never installs
a second copy:

```toml
[tool.poetry.dependencies]
titan-cli = {version = ">=0.9.0,<1.0.0", optional = true, python = ">=3.11"}

[tool.poetry.extras]
# Only for working on the plugin repo: `poetry install --extras host`.
host = ["titan-cli"]
```

Do **not** simply delete the declaration. Titan reads that very constraint to decide
whether the running version may load the plugin (see Version Compatibility below), and an
absent requirement silently disables that gate.

Everything else the plugin genuinely needs is declared normally. Two cases:

| The library is... | What happens |
|---|---|
| Not shipped by Titan (`PyJWT`) | Loaded from the plugin's cached venv. This is what the venv is for |
| Also shipped by Titan (`requests`) | Titan's version is used, whatever the plugin pinned |

Pin ranges that are compatible with what Titan ships (`pyproject.toml`, `[tool.poetry.dependencies]`).
A plugin that needs a conflicting major version of a shared library cannot be satisfied
in-process today.

---

## Update Flow

Only `stable` community plugins can be updated. A plugin whose load failed can still be
updated: the pin lives in project config, not in the loaded plugin, and update is the
standard way out of a broken pinned version.

Update behavior:

1. check latest release/tag from the repo host
2. resolve that ref to a full SHA
3. compatibility gate: fetch the candidate's `pyproject.toml` at that SHA and check its
   declared `titan-cli` requirement against the running version — a positively-detected
   incompatibility aborts the update with an explanatory notify (fetch/parse failures do
   not block)
4. update the current project's `.titan/config.toml`
5. prepare the runtime for the new commit
6. reload Titan config/registry

`dev_local` has no update flow by design.

---

## Version Compatibility

The compatibility contract between a plugin and titan-cli is the plugin's declared
`titan-cli` dependency in its `pyproject.toml`.

- `parse_plugin_metadata` (community_sources.py) extracts it as `titan_requirement`
  (PEP 621 and Poetry layouts, including `^`/`~` translation).
- `get_titan_incompatibility(metadata, current_version)` returns a message or `None`.
  Absent/unparseable requirements never block.
- Enforced in three places: `_load_local_plugin` (plugin_registry.py, before import;
  raises `PluginIncompatibleError`), the install screen (blocking panel before writing
  the pin), and the update flow (step 3 above).
- Fallback heuristic: a `ModuleNotFoundError` for a `titan_cli.*` module during plugin
  import is re-raised as `PluginIncompatibleError` — a missing Titan API means the
  plugin was built for a different titan-cli, and the raw traceback misleads.
- UI: failed plugins show as "Load failed" (not "Not installed") in Plugin Management,
  with the error in the details panel and Update still available.

Contributor rule for breaking `titan_cli.*` changes (deprecation aliases, coordinated
plugin releases): see `docs/contributing/architecture.md`, "Plugin API Compatibility
Rule".

---

## Remove Flow

In Plugin Management:

- if the active source is `dev_local`, remove the local override from global config
- if the active source is `stable`, remove the plugin from the current project's config

This no longer uninstalls a package from Titan's global environment, because `stable` community plugins are no longer managed with `pipx inject`.

---

## Important Notes

- `~/.titan/community_plugins.toml` is no longer used
- `community.py` was replaced by `community_sources.py`
- official plugins can still follow their own global install path; the per-project runtime model here is specifically for community plugins
- official plugins are immune to the shadowing described under Runtime Layout: they are
  installed into Titan's own environment (path dependencies in development, bundled
  packages in the published wheel), never into a separate venv that competes for imports

---

## Known Limits

- community plugins still run in-process after being imported
- there is no true dependency isolation: the cached venv only supplies what the host
  lacks, so a plugin needing a different version of a library Titan ships cannot get it
- execution is not sandboxed in a subprocess
- a future architecture could move plugin execution out-of-process, which is the only way
  to give a plugin its own dependency versions without imposing them on Titan
