# Firebase Built-in Workflows

The Firebase plugin ships seven workflow definitions. Titan's workflow picker shows only
the product-level Remote Config workflows by default:
`create-remoteconfig-key`, `list-remoteconfig-keys-multiproject`, and
`set-remoteconfig-value-multiproject`.

The single-project and diagnostic definitions below remain available for compatibility,
composition, and direct execution by name, but they are intentionally hidden from the
default picker so the Firebase menu stays focused on the multimarca use case.

## `list-projects`

List Firebase projects available to the active Google credentials.

**Source workflow:** `plugins/titan-plugin-firebase/titan_plugin_firebase/workflows/list-projects.yaml`

### Params

| Param | Default | What it does |
|-------|---------|--------------|
| `project_filter` | `""` | Optional case-insensitive words used to filter by project ID, display name, resource name, or project number. For example, `Prepago, National`. |

### Default flow

1. `firebase.firebase_auth_check`
2. `firebase.firebase_projects_list`

### Typical usage

- check which Firebase projects the current ADC session can see
- copy or feed project IDs into a later Remote Config workflow

### Scope constraints

- read-only: nothing in this workflow writes
- the list comes from Firebase Management, so it contains Firebase projects rather than
  generic Google Cloud projects

### Related public steps

- `firebase_auth_check`
- `firebase_projects_list`

## `list-remoteconfig-keys`

List one project's Remote Config parameter keys with their default and condition values.

**Source workflow:** `plugins/titan-plugin-firebase/titan_plugin_firebase/workflows/list-remoteconfig-keys.yaml`

### Default flow

1. `firebase.firebase_auth_check`
2. `firebase.firebase_select_target`
3. `firebase.firebase_remoteconfig_get`
4. `firebase.firebase_remoteconfig_list_keys`

### Typical usage

- inventory the keys and values available in a project before deciding what to inspect or change
- produce `firebase_remoteconfig_keys` for a later workflow step without parsing screen text
- produce `firebase_remoteconfig_key_values` for later value-aware planning

### Scope constraints

- read-only: nothing in this workflow writes
- one project per run
- values are displayed as compact, type-aware summaries

### Related public steps

- `firebase_auth_check`
- `firebase_select_target`
- `firebase_remoteconfig_get`
- `firebase_remoteconfig_list_keys`

## `list-remoteconfig-keys-multiproject`

List and compare Remote Config parameter keys and values across several Firebase projects.

**Source workflow:** `plugins/titan-plugin-firebase/titan_plugin_firebase/workflows/list-remoteconfig-keys-multiproject.yaml`

### Params

| Param | Default | What it does |
|-------|---------|--------------|
| `project_ids` | `""` | Projects to inspect, comma-separated. Leave empty when an earlier step publishes `firebase_project_ids` instead; in the TUI, an empty value asks for the list. |
| `project_set` | `""` | Configured project set to inspect. Empty means use `plugins.firebase.config.default_project_set` when present. |
| `project_groups` | `""` | Optional group tags, comma-separated, used to inspect only part of the configured project set. |
| `environment` | `""` | Optional environment such as `dev` or `pro`, used to inspect only matching configured projects. |
| `project_filter` | `""` | Optional case-insensitive words used to reduce the TUI project catalogue before choosing projects. For example, `Prepago, National`. |
| `condition_group` | `""` | Optional configured Remote Config condition group used to filter the value table, such as `android` or `ios`. |

### Default flow

1. `firebase.firebase_auth_check`
2. `firebase.firebase_select_targets`
3. `firebase.firebase_remoteconfig_fanout_list_keys`

### Typical usage

- build a multi-brand inventory before deciding which Remote Config key to change
- find keys that are missing from one or more brand projects
- detect value-type conflicts for the same key across projects
- compare the default and condition-specific values each brand currently has
- confirm which value types are present in the real templates before adding parser support

### Scope constraints

- read-only: nothing in this workflow writes
- projects are read one by one, so a failure in one project is reported without discarding
  the projects that were read successfully
- values are displayed per project as compact, type-aware summaries
- the inventory builds deterministic type profiles, using the declared `valueType` when
  present and all explicit stored values for legacy keys without one
- values managed by Firebase personalization, experiments, rollouts, or future unknown
  value-source fields are preserved and reported, but marked unsafe for bulk writes

### Related public steps

- `firebase_auth_check`
- `firebase_select_targets`
- `firebase_remoteconfig_fanout_list_keys`

## `create-remoteconfig-key`

Create one Remote Config key in selected Firebase projects where it is missing.

**Source workflow:** `plugins/titan-plugin-firebase/titan_plugin_firebase/workflows/create-remoteconfig-key.yaml`

### Params

| Param | Default | What it does |
|-------|---------|--------------|
| `project_ids` | `""` | Projects to inspect, comma-separated. Leave empty to use a configured project set or TUI selection. |
| `project_set` | `""` | Configured project set to inspect. Empty means use `plugins.firebase.config.default_project_set` when present. |
| `project_groups` | `""` | Optional group tags, comma-separated, used to inspect only part of the configured project set. |
| `environment` | `""` | Optional environment such as `dev` or `pro`, used to inspect only matching configured projects. |
| `project_filter` | `""` | Optional case-insensitive words used to reduce the TUI project catalogue before choosing projects. |
| `condition_group` | `""` | Optional configured Remote Config condition group used to filter inventory value previews, such as `android` or `ios`. |
| `key` | `""` | Key to create. Empty means enter it interactively. |
| `value_type` | `""` | New key type: `BOOLEAN`, `JSON`, `NUMBER` or `STRING`. Empty means choose it interactively. |
| `default_value` | `""` | Default value to store. Empty means enter it interactively. |
| `conditional_values` | `""` | Optional condition values, as a mapping, JSON object, or `condition=value` list. |
| `description` | `""` | Optional Remote Config parameter description. |
| `target_project_ids` | `""` | Missing target projects where the key should be created. Empty means confirm them interactively. |
| `dry_run` | `false` | Validate the new payloads with Firebase and publish nothing. |

### Default flow

1. `firebase.firebase_auth_check`
2. `firebase.firebase_select_targets`
3. `firebase.firebase_remoteconfig_fanout_list_keys`
4. `firebase.firebase_remoteconfig_create_key_plan`
5. `firebase.firebase_remoteconfig_create_key_publish`

### Typical usage

- add a new key to the brands where it is missing without overwriting brands that already
  have it
- create a typed default value plus selected condition values across selected environments
- validate a production payload with `dry_run` before publishing

### Scope constraints

- only missing keys are created; existing keys are never overwritten
- `value_type` controls validation and input shape: booleans, JSON, numbers and strings
  are handled differently
- condition values can only target conditions that exist in every selected destination
- creation writes literal `value` payloads only; it does not create Firebase-managed
  personalization, experiment or rollout values
- each target publish is independent, serial, and guarded by its own ETag
- selected targets may include several configured environments; publishing remains
  independent, serial, and confirmed per project

### Related public steps

- `firebase_select_targets`
- `firebase_remoteconfig_fanout_list_keys`
- `firebase_remoteconfig_create_key_plan`
- `firebase_remoteconfig_create_key_publish`

## `read-remoteconfig`

Read a project's Remote Config template, see its conditions, and inspect one parameter.

**Source workflow:** `plugins/titan-plugin-firebase/titan_plugin_firebase/workflows/read-remoteconfig.yaml`

### Default flow

1. `firebase.firebase_auth_check`
2. `firebase.firebase_select_target`
3. `firebase.firebase_remoteconfig_get`
4. `firebase.firebase_remoteconfig_conditions`
5. `firebase.firebase_remoteconfig_select_key`

### Typical usage

- check what a flag is actually set to, without opening the console
- see which conditions a project declares, and which parameters override them
- see who published the active version and when

### Scope constraints

- read-only: nothing in this workflow writes
- one project per run

### Related public steps

- `firebase_auth_check`
- `firebase_select_target`
- `firebase_remoteconfig_get`
- `firebase_remoteconfig_conditions`
- `firebase_remoteconfig_select_key`

## `set-remoteconfig-value`

Change one Remote Config parameter — boolean, string, JSON or number — in one project, for
the default value or for a specific condition.

**Source workflow:** `plugins/titan-plugin-firebase/titan_plugin_firebase/workflows/set-remoteconfig-value.yaml`

### Params

| Param | Default | What it does |
|-------|---------|--------------|
| `dry_run` | `false` | Validate the change with Firebase and publish nothing. |

### Default flow

1. `firebase.firebase_auth_check`
2. `firebase.firebase_select_target`
3. `firebase.firebase_remoteconfig_get`
4. `firebase.firebase_remoteconfig_conditions`
5. `firebase.firebase_remoteconfig_select_key`
6. `firebase.firebase_remoteconfig_set_value`
7. `firebase.firebase_remoteconfig_diff`
8. `firebase.firebase_remoteconfig_publish`

### Typical usage

- flip a kill switch in one project
- change a JSON payload for one condition without touching the default value

### Scope constraints

- the parameter and the condition must already exist in the project; this workflow
  changes values, it does not create keys or conditions
- publishing requires the confirmation the diff step asks for, and that confirmation
  defaults to no
- a no-op change exits the workflow instead of publishing an empty version
- publishing needs Remote Config update permission, which production projects often
  restrict; `dry_run` tells you whether the payload is valid without needing it

### Related public steps

- `firebase_remoteconfig_set_value`
- `firebase_remoteconfig_diff`
- `firebase_remoteconfig_publish`

## `set-remoteconfig-value-multiproject`

Apply one parameter change across several Firebase projects, confirming project by project.

**Source workflow:** `plugins/titan-plugin-firebase/titan_plugin_firebase/workflows/set-remoteconfig-value-multiproject.yaml`

### Params

| Param | Default | What it does |
|-------|---------|--------------|
| `project_ids` | `""` | Projects to target, comma-separated. Leave empty when an earlier step publishes `firebase_project_ids` instead. |
| `project_set` | `""` | Configured project set to target. Empty means use `plugins.firebase.config.default_project_set` when present. |
| `project_groups` | `""` | Optional group tags, comma-separated, used to target only part of the configured project set. |
| `environment` | `""` | Optional environment such as `dev` or `pro`, used to target only matching configured projects. |
| `project_filter` | `""` | Optional case-insensitive words used to reduce the TUI project catalogue before choosing projects. For example, `Prepago, National`. |
| `condition_group` | `""` | Optional configured Remote Config condition group used to filter inventory value previews, such as `android` or `ios`. |
| `key` | `""` | Parameter to change. Empty means pick it interactively. |
| `value` | `""` | New value. Empty means enter it interactively. |
| `condition` | `""` | Condition to write instead of the default value. |
| `dry_run` | `false` | Validate in every project and publish nothing. |

### Default flow

1. `firebase.firebase_auth_check`
2. `firebase.firebase_select_targets`
3. `firebase.firebase_remoteconfig_fanout_list_keys`
4. `firebase.firebase_remoteconfig_fanout_plan`
5. `firebase.firebase_remoteconfig_fanout_publish`

### Typical usage

- roll one flag out to every project that has it
- see, before writing anything, which projects already have the target value and which ones
  cannot take the change at all

### Composing it with your own project mapping

The project list comes from workflow data, not configuration, so a plugin that owns a
mapping of its own — one Firebase project per brand, per team, per environment — resolves it
and publishes `firebase_project_ids` (plus optional `firebase_project_labels`). Because
workflows can use steps from any installed plugin, that step chains directly with
`firebase_remoteconfig_fanout_plan` and `firebase_remoteconfig_fanout_publish`, and this
plugin never learns what the names mean.

### Scope constraints

- every project has its own template: the parameter, its declared type, and the conditions
  can all differ, so the change is validated per project and the ones that cannot take it
  are reported rather than skipped silently
- the workflow first builds the deterministic key inventory; a bulk value change is blocked
  when the selected key is missing, unknown, locally mixed, or typed differently between
  projects, or when any selected project has a Firebase-managed value source
- when `key` or `value` are not passed, the prompts are built from the first target's
  template, filtered to bulk-safe keys when the inventory is available
- selected targets may include several configured environments; publishing remains
  independent, serial, and confirmed per project
- publishing is not transactional across projects: each publish is its own Remote Config
  version, and a failure in one does not roll back the others. The final table says what
  each project did

### Related public steps

- `firebase_select_targets`
- `firebase_remoteconfig_fanout_list_keys`
- `firebase_remoteconfig_fanout_plan`
- `firebase_remoteconfig_fanout_publish`
