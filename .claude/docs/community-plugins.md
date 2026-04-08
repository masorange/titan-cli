# Community Plugins

## Overview

Titan supports community plugins in addition to the official plugins bundled with the CLI.

There are currently two source channels:

- `stable`: install from a git repository at an explicit tag or commit
- `dev_local`: use a local plugin checkout during development

Community plugin installs are tracked globally in `~/.titan/community_plugins.toml`, while the active source selection for a given project is stored in that project's `.titan/config.toml`.

---

## Key Files

| File | Role |
|------|------|
| `titan_cli/core/plugins/community.py` | Business logic for URL parsing, metadata preview, stable/dev-local install helpers, updates, uninstall, tracking file I/O |
| `titan_cli/core/plugins/models.py` | Plugin source config model (`source.channel`, `source.path`) |
| `titan_cli/core/plugins/plugin_registry.py` | Applies `dev_local` source overrides before plugin initialization |
| `titan_cli/ui/tui/screens/install_plugin_screen.py` | Stable community plugin install wizard |
| `titan_cli/ui/tui/screens/plugin_management.py` | Source display, update/uninstall actions, stable reset for `dev_local` |
| `titan_cli/ui/tui/widgets/wizard.py` | Shared wizard widgets: `StepStatus`, `WizardStep`, `StepIndicator` |

---

## Channels

### `stable`

This is the normal community-plugin flow. The user installs from a git repository URL and must include an explicit version selector:

```text
https://github.com/user/titan-plugin-custom@v1.2.0
https://github.com/user/titan-plugin-custom@abc123def456
```

Titan resolves that ref to a concrete commit SHA and installs from that pinned revision. After install, the current project stores:

```toml
[plugins.custom]
enabled = true

[plugins.custom.source]
channel = "stable"
```

### `dev_local`

This is the development channel. It is not a remote dev feed or prerelease registry. It means "load this plugin from a local repository path".

The current project stores:

```toml
[plugins.custom]
enabled = true

[plugins.custom.source]
channel = "dev_local"
path = "/absolute/path/to/local/plugin/repo"
```

When `dev_local` is active, the plugin registry loads the plugin directly from that repo:

1. Reads `pyproject.toml`
2. Parses the `titan.plugins` entry points
3. Finds the requested Titan plugin name
4. Prepends the repo to `sys.path`
5. Imports and instantiates the plugin class

This override is applied before plugin initialization, so the local checkout wins over any installed stable version for that project.

If `channel = "dev_local"` is set without a `path`, the plugin is marked as failed to load.

---

## Stable URL Format

Users must always include an explicit version — bare URLs without `@version` are rejected:

```
# Accepted
https://github.com/user/titan-plugin-custom@v1.2.0
https://github.com/user/titan-plugin-custom@abc123def456

# Rejected
https://github.com/user/titan-plugin-custom
```

Internally this becomes: `git+https://github.com/user/titan-plugin-custom.git@v1.2.0`

---

## Stable Install Flow (4 steps)

### 1. URL
User enters `https://repo@version`. Validated with `validate_url()` before advancing.

### 2. Preview
Fetches `pyproject.toml` from the repo at that exact version and shows:
- Package name, version, description, authors
- Titan entry points registered (`[titan.plugins]`)
- Python dependencies

**Host detection** (`PluginHost` StrEnum): `GITHUB`, `GITLAB`, `BITBUCKET`, `UNKNOWN`

Raw URL patterns per host:
```
GitHub:    https://raw.githubusercontent.com/{path}/{version}/pyproject.toml
GitLab:    https://gitlab.com/{path}/-/raw/{version}/pyproject.toml
Bitbucket: https://bitbucket.org/{path}/raw/{version}/pyproject.toml
Unknown:   fetch skipped — warning shown, install still allowed
```

Error cases (all allow proceeding):
- HTTP 404 → URL or version not found
- Network error → connection problem
- No `[titan.plugins]` entry point → warns plugin won't be visible in Titan
- Unparseable pyproject.toml → warns metadata unreadable

A **security warning** is always shown regardless of outcome.

### 3. Install
Runs a package install in Titan's active Python environment:

- pipx environment: `pipx inject titan-cli git+<url>.git@<resolved_commit>`
- non-pipx environment: `python -m pip install git+<url>.git@<resolved_commit>`

The requested tag or short ref is resolved to a full commit SHA first. This is the security anchor for stable installs: updates only happen when the user explicitly installs or updates again.

On success:
1. Saves record to `~/.titan/community_plugins.toml`
2. Writes the project source override as `channel = "stable"`
3. Calls `self.config.load()` → auto-reloads registry + re-initializes all plugins (no restart needed)

On failure: shows pipx stderr + actionable suggestions.

### 4. Done
Success or failure summary. "Finish" dismisses the wizard.

---

## Tracking File

`~/.titan/community_plugins.toml` is global and stores installed/tracked community plugin records. It is not the same as project source selection.

Current stable records look like this:

```toml
[[plugins]]
repo_url = "https://github.com/user/titan-plugin-custom"
package_name = "titan-plugin-custom"
titan_plugin_name = "custom"
installed_at = "2026-03-06T10:30:00+00:00"
channel = "stable"
requested_ref = "v1.2.0"
resolved_commit = "0123456789abcdef0123456789abcdef01234567"
```

`dev_local` records use the same structure but store the local path instead of git revision metadata:

```toml
[[plugins]]
repo_url = ""
package_name = "titan-plugin-custom"
titan_plugin_name = "custom"
installed_at = "2026-03-06T10:30:00+00:00"
channel = "dev_local"
dev_local_path = "/absolute/path/to/local/plugin/repo"
```

Key functions in `community.py`:
- `load_community_plugins()` → `list[CommunityPluginRecord]`
- `save_community_plugin(record)` → appends to file
- `remove_community_plugin_by_name(titan_plugin_name)` → removes all tracked channels for a Titan plugin name
- `remove_community_plugin_by_channel(titan_plugin_name, channel)` → removes one tracked channel only
- `get_community_plugin_names()` → `set[str]` of titan_plugin_names (used for `[community]` badge)
- `get_community_plugin_by_titan_name(name)` → `Optional[CommunityPluginRecord]`
- `get_community_plugin_by_name_and_channel(name, channel)` → specific channel lookup

---

## Uninstall Flow

In Plugin Management, pressing `u` (or clicking "Uninstall") on a community plugin:
1. If the active source is `dev_local`, Titan does not uninstall a package. It only resets the project source override back to `stable` and removes `path`.
2. If the active source is a tracked stable community plugin, Titan uninstalls the package from the active environment.
3. Removes the tracked record(s) as needed.
4. Calls `self.config.load()` to reload the registry.
5. Refreshes the plugin list.

Only stable community plugins can be updated. `dev_local` intentionally has no update flow.

---

## Dev-Local Install Helper

The codebase includes `install_community_plugin_dev_local(local_path)`, which performs an editable install:

- pipx environment: `pipx runpip titan-cli install -e <path>`
- non-pipx environment: `python -m pip install -e <path>`

This is useful for plugin development, but the current TUI install wizard is specifically built around the `stable` git URL flow. The active `dev_local` behavior is primarily driven by project config source overrides.

---

## Wizard Widgets (`titan_cli/ui/tui/widgets/wizard.py`)

Shared by `install_plugin_screen.py` and `plugin_config_wizard.py`:

```python
class StepStatus(StrEnum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"

@dataclass
class WizardStep:
    id: str
    title: str

class StepIndicator(Static):
    def __init__(self, step_number: int, step: WizardStep, status: StepStatus): ...
```

Exported from `titan_cli/ui/tui/widgets/__init__.py`.

---

## Known Technical Debt

`plugin_config_wizard.py` still uses plain dicts (`{"id": ..., "title": ...}`) for its steps instead of `WizardStep`. It wraps them with `WizardStep(id=step["id"], title=step["title"])` when calling `StepIndicator`. Full refactor is pending a future PR.

The public docs are still sparse on community plugins, and some older references still describe only the stable install flow. When updating docs, treat `dev_local` as a first-class source channel and avoid describing it as a remote development release channel.
