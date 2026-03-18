# Community Plugin Installer

## Overview

Titan supports installing plugins from user-provided git repositories, not just the official ones bundled with the CLI. Installation always uses `pipx inject` to keep the plugin isolated in Titan's own venv.

Community plugins are tracked separately in `~/.titan/community_plugins.toml` (global, not per-project).

---

## Key Files

| File | Role |
|------|------|
| `titan_cli/core/plugins/community.py` | All business logic: URL parsing, host detection, pyproject.toml fetch, pipx install/uninstall, tracking file I/O |
| `titan_cli/ui/tui/screens/install_plugin_screen.py` | 4-step install wizard |
| `titan_cli/ui/tui/screens/plugin_management.py` | Modified: install button (`i`), uninstall (`u`), `[community]` badge |
| `titan_cli/ui/tui/widgets/wizard.py` | Shared wizard widgets: `StepStatus`, `WizardStep`, `StepIndicator` |

---

## URL Format

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

## Install Flow (4 steps)

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
Runs `pipx inject titan-cli git+<url>.git@<version>` as a subprocess (async, non-blocking).

Requires Titan to be running inside a pipx environment (`is_running_in_pipx()`). If not, shows an error and blocks install.

On success:
1. Saves record to `~/.titan/community_plugins.toml`
2. Calls `self.config.load()` → auto-reloads registry + re-initializes all plugins (no restart needed)

On failure: shows pipx stderr + actionable suggestions.

### 4. Done
Success or failure summary. "Finish" dismisses the wizard.

---

## Tracking File

`~/.titan/community_plugins.toml` — global, one record per installed community plugin:

```toml
[[plugins]]
repo_url = "https://github.com/user/titan-plugin-custom"
version = "v1.2.0"
package_name = "titan-plugin-custom"
titan_plugin_name = "custom"
installed_at = "2026-03-06T10:30:00+00:00"
```

Key functions in `community.py`:
- `load_community_plugins()` → `list[CommunityPluginRecord]`
- `save_community_plugin(record)` → appends to file
- `remove_community_plugin(package_name)` → removes by package name
- `get_community_plugin_names()` → `set[str]` of titan_plugin_names (used for `[community]` badge)
- `get_community_plugin_by_titan_name(name)` → `Optional[CommunityPluginRecord]`

---

## Uninstall Flow

In Plugin Management, pressing `u` (or clicking "Uninstall") on a community plugin:
1. Runs `pipx runpip titan-cli uninstall -y <package_name>`
2. Calls `remove_community_plugin(package_name)`
3. Calls `self.config.load()` to reload registry
4. Refreshes the plugin list

Only community plugins show the Uninstall button/keybinding.

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
