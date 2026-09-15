# Firebase Built-in Workflows

The Firebase plugin ships three built-in workflows.

## `read-remoteconfig`

Read a brand's Remote Config template, see its conditions, and inspect one parameter.

**Source workflow:** `plugins/titan-plugin-firebase/titan_plugin_firebase/workflows/read-remoteconfig.yaml`

### Default flow

1. `firebase.firebase_auth_check`
2. `firebase.firebase_select_target`
3. `firebase.firebase_remoteconfig_get`
4. `firebase.firebase_remoteconfig_conditions`
5. `firebase.firebase_remoteconfig_select_key`

### Typical usage

- check what a flag is actually set to in one brand, without opening the console
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

Change one Remote Config parameter — boolean, string, JSON or number — in one brand's
project, for the default value or for a specific condition.

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

- flip a kill switch in one brand
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

## `set-remoteconfig-value-multibrand`

Apply one parameter change across several brands, confirming brand by brand.

**Source workflow:** `plugins/titan-plugin-firebase/titan_plugin_firebase/workflows/set-remoteconfig-value-multibrand.yaml`

### Params

| Param | Default | What it does |
|-------|---------|--------------|
| `brands` | `""` | Brands to target, comma-separated. Empty means pick them interactively. |
| `key` | `""` | Parameter to change. Empty means pick it interactively. |
| `value` | `""` | New value. Empty means enter it interactively. |
| `condition` | `""` | Condition to write instead of the default value. |
| `dry_run` | `false` | Validate in every brand and publish nothing. |

### Default flow

1. `firebase.firebase_auth_check`
2. `firebase.firebase_select_targets`
3. `firebase.firebase_remoteconfig_fanout_plan`
4. `firebase.firebase_remoteconfig_fanout_publish`

### Typical usage

- roll one flag out to every brand that has it
- see, before writing anything, which brands already have the target value and which ones
  cannot take the change at all

### Scope constraints

- each brand is a separate Firebase project with its own template: the parameter, its
  declared type, and the conditions can all differ, so the change is validated per brand
  and the brands that cannot take it are reported rather than skipped silently
- when `key` or `value` are not passed, the prompts are built from the first selected
  brand's template — that project is the reference for the type and the available
  conditions
- publishing is not transactional across brands: each publish is its own Remote Config
  version, and a failure in one brand does not roll back the others. The final table says
  what each brand did

### Related public steps

- `firebase_select_targets`
- `firebase_remoteconfig_fanout_plan`
- `firebase_remoteconfig_fanout_publish`
