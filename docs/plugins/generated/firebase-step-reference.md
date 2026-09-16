# Firebase Step Reference

This page is generated from the public step inventory and shows the documented workflow contract for each public step.

## Authentication

### `firebase_auth_check`

Check that Google Application Default Credentials are usable.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_auth_check
```

**Used by built-in workflows:** `create-remoteconfig-key`, `list-projects`, `list-remoteconfig-keys`, `list-remoteconfig-keys-multiproject`, `read-remoteconfig`, `set-remoteconfig-value`, `set-remoteconfig-value-multiproject`

**Available to later steps:** `firebase_account`, `firebase_credential_kind`, `firebase_credential_is_user`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_account` | Optional[str] | Service account email, when applicable. |
| `firebase_credential_kind` | str | user, service_account, impersonated, ... |
| `firebase_credential_is_user` | bool | Whether publishes get a real author. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_account`, `firebase_credential_kind`, `firebase_credential_is_user` | If credentials resolve and can mint a token. |
| `Error` | - | If no ADC session exists or it cannot be refreshed. |

## Project Selection

### `firebase_projects_list`

List Firebase projects available to the active Google credentials.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_projects_list
```

**Used by built-in workflows:** `list-projects`

**Available to later steps:** `firebase_projects`, `firebase_project_ids`, `firebase_project_labels`, `firebase_project_environments`, `firebase_project_brands`, `firebase_project_group_map`, `firebase_project_catalog_count`, `firebase_project_filter_terms`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `project_filter` | str, optional | Case-insensitive words used to filter project IDs, names, resource names, or numbers. |
| `firebase_project_filter` | str, optional | Same filter, as emitted by earlier steps. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_projects` | list[UIFirebaseProject] | Projects returned by Firebase Management, enriched with configured metadata when available. |
| `firebase_project_ids` | list[str] | Project IDs in display order. |
| `firebase_project_labels` | dict[str, str] | project_id to configured/display label. |
| `firebase_project_environments` | dict[str, str] | project_id to configured environment. |
| `firebase_project_brands` | dict[str, str] | project_id to configured brand. |
| `firebase_project_group_map` | dict[str, list[str]] | project_id to configured groups. |
| `firebase_project_catalog_count` | int | Total projects before filtering. |
| `firebase_project_filter_terms` | list[str] | Normalized filter terms that were applied. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_projects`, `firebase_project_ids`, `firebase_project_labels`, `firebase_project_environments`, `firebase_project_brands`, `firebase_project_group_map`, `firebase_project_catalog_count`, `firebase_project_filter_terms` | If Firebase projects could be listed. |
| `Error` | - | If Firebase is unavailable or the project list request fails. |

### `firebase_select_target`

Resolve the Firebase project to work on.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_select_target
```

**Used by built-in workflows:** `list-remoteconfig-keys`, `read-remoteconfig`, `set-remoteconfig-value`

**Available to later steps:** `firebase_project_id`, `firebase_target_label`, `firebase_environment`, `firebase_project_brand`

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `project_id` | str, optional | Firebase project ID to use. |
| `firebase_project_id` | str, optional | Same value, as emitted by earlier steps. |
| `project_label` | str, optional | Friendlier name to show for it. |
| `project_brand` | str, optional | Brand metadata supplied by an earlier step. |
| `environment` | str, optional | Environment metadata supplied by the workflow. |
| `firebase_environment` | str, optional | Same environment, as emitted by earlier steps. |
| `project_filter` | str, optional | Case-insensitive words used to filter the TUI project catalogue. |
| `firebase_project_filter` | str, optional | Same filter, as emitted by earlier steps. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_project_id` | str | Resolved project ID. |
| `firebase_target_label` | str | User-facing reference for the target. |
| `firebase_environment` | str, optional | Resolved environment, when known. |
| `firebase_project_brand` | str, optional | Resolved brand, when known. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_project_id`, `firebase_target_label`, `firebase_environment`, `firebase_project_brand` | If a project could be resolved. |
| `Error` | - | If the plugin is unavailable or nothing names a project. |

### `firebase_select_targets`

Resolve several Firebase projects from a caller-supplied list.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_select_targets
```

**Used by built-in workflows:** `create-remoteconfig-key`, `list-remoteconfig-keys-multiproject`, `set-remoteconfig-value-multiproject`

**Available to later steps:** `firebase_targets`, `firebase_project_ids`, `firebase_project_set`, `firebase_project_groups`, `firebase_environment`, `firebase_environments`, `firebase_environment_filter`, `firebase_project_environments`, `firebase_project_brands`, `firebase_project_group_map`

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `project_ids` | list or str, optional | Projects to target; a comma- or space-separated string is accepted. |
| `firebase_project_ids` | list or str, optional | Same, as published by an earlier step. |
| `firebase_project_labels` | dict, optional | project_id to label, shown instead of the raw ID. |
| `project_set` | str, optional | Configured project set to use when project IDs are absent. |
| `firebase_project_set` | str, optional | Same project set, as emitted by earlier steps. |
| `project_groups` | list or str, optional | Configured project groups to keep. |
| `firebase_project_groups` | list or str, optional | Same groups, as emitted by earlier steps. |
| `environment` | str, optional | Configured environment(s) to keep, for example dev, pro, or both. |
| `firebase_environment` | str, optional | Same environment, as emitted by earlier steps. |
| `project_filter` | str, optional | Case-insensitive words used to filter the TUI project catalogue. |
| `firebase_project_filter` | str, optional | Same filter, as emitted by earlier steps. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_targets` | list[FirebaseProjectTarget] | Resolved targets. |
| `firebase_project_ids` | list[str] | Normalized, de-duplicated project IDs. |
| `firebase_project_set` | str, optional | Project set used, when resolved from config. |
| `firebase_project_groups` | list[str], optional | Project groups used, when any. |
| `firebase_environment` | str, optional | Single resolved environment, when known. |
| `firebase_environments` | list[str] | Known environments represented by the targets. |
| `firebase_environment_filter` | list[str], optional | Explicitly selected environment filter, when any. |
| `firebase_project_environments` | dict[str, str] | project_id to environment. |
| `firebase_project_brands` | dict[str, str] | project_id to brand. |
| `firebase_project_group_map` | dict[str, list[str]] | project_id to configured groups. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_targets`, `firebase_project_ids`, `firebase_project_set`, `firebase_project_groups`, `firebase_environment`, `firebase_environments`, `firebase_environment_filter`, `firebase_project_environments`, `firebase_project_brands`, `firebase_project_group_map` | If at least one project was named. |
| `Error` | - | If the plugin is unavailable or the list is empty. |

## Reading Remote Config

### `firebase_remoteconfig_get`

Read the active Remote Config template for one project.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_get
```

**Used by built-in workflows:** `list-remoteconfig-keys`, `read-remoteconfig`, `set-remoteconfig-value`

**Available to later steps:** `firebase_project_id`, `firebase_remoteconfig_etag`, `firebase_remoteconfig_version`, `firebase_remoteconfig_template`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_project_id` | str | Project to read, from firebase_select_target. |
| `project_id` | str, optional | Alternative key for the same thing. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_project_id` | str | Project that was read. |
| `firebase_remoteconfig_etag` | Optional[str] | ETag needed to publish over it. |
| `firebase_remoteconfig_version` | Optional[str] | Active version number. |
| `firebase_remoteconfig_template` | UIRemoteConfigTemplate | The template. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_project_id`, `firebase_remoteconfig_etag`, `firebase_remoteconfig_version`, `firebase_remoteconfig_template` | If the template is read. |
| `Error` | - | If Firebase is unavailable, no project is given, or the read fails. |

### `firebase_remoteconfig_list_keys`

List parameter keys and configured values in a Remote Config template.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_list_keys
```

**Used by built-in workflows:** `list-remoteconfig-keys`

**Available to later steps:** `firebase_remoteconfig_keys`, `firebase_remoteconfig_key_values`, `firebase_remoteconfig_key_count`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_remoteconfig_template` | UIRemoteConfigTemplate | From firebase_remoteconfig_get. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_remoteconfig_keys` | list[str] | Parameter keys in template order. |
| `firebase_remoteconfig_key_values` | dict[str, dict] | Default and conditional values per key. |
| `firebase_remoteconfig_key_count` | int | Number of parameter keys. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_remoteconfig_keys`, `firebase_remoteconfig_key_values`, `firebase_remoteconfig_key_count` | If the template is present; empty projects return an empty list. |
| `Error` | - | If the template is missing. |

### `firebase_remoteconfig_fanout_list_keys`

List and compare Remote Config parameter keys and values across projects.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_fanout_list_keys
```

**Used by built-in workflows:** `create-remoteconfig-key`, `list-remoteconfig-keys-multiproject`, `set-remoteconfig-value-multiproject`

**Available to later steps:** `firebase_remoteconfig_keys`, `firebase_remoteconfig_common_keys`, `firebase_remoteconfig_missing_keys`, `firebase_remoteconfig_key_profiles`, `firebase_remoteconfig_project_key_values`, `firebase_remoteconfig_project_conditions`, `firebase_remoteconfig_bulk_safe_keys`, `firebase_remoteconfig_bulk_blocked_keys`, `firebase_remoteconfig_type_conflicts`, `firebase_remoteconfig_value_types`, `firebase_remoteconfig_declared_value_types`, `firebase_remoteconfig_unknown_type_keys`, `firebase_remoteconfig_project_key_counts`, `firebase_remoteconfig_failed_projects`, `firebase_condition_group`, `firebase_condition_group_label`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_targets` | list[FirebaseProjectTarget] | From firebase_select_targets. |
| `condition_group` | str, optional | Configured condition/value group to display. |
| `firebase_condition_group` | str, optional | Same group, as emitted by earlier steps. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_remoteconfig_keys` | list[str] | All keys seen in at least one project. |
| `firebase_remoteconfig_common_keys` | list[str] | Keys present in every readable project. |
| `firebase_remoteconfig_missing_keys` | dict[str, list[str]] | project_id to missing keys. |
| `firebase_remoteconfig_key_profiles` | dict[str, dict] | Deterministic value-free profile per key, including value sources. |
| `firebase_remoteconfig_project_key_values` | dict[str, dict] | project_id to key value snapshots, including value_source and editable. |
| `firebase_remoteconfig_project_conditions` | dict[str, list[dict]] | project_id to template conditions. |
| `firebase_remoteconfig_bulk_safe_keys` | list[str] | Keys present in every readable project with one stable known type. |
| `firebase_remoteconfig_bulk_blocked_keys` | dict[str, list[str]] | key to blocker reasons for bulk edits. |
| `firebase_remoteconfig_type_conflicts` | dict[str, list[str]] | key to observed effective types. |
| `firebase_remoteconfig_value_types` | list[str] | Effective value types observed. |
| `firebase_remoteconfig_declared_value_types` | list[str] | Declared value types observed. |
| `firebase_remoteconfig_unknown_type_keys` | dict[str, list[str]] | project_id to keys whose effective type is UNKNOWN. |
| `firebase_remoteconfig_project_key_counts` | dict[str, int] | project_id to key count. |
| `firebase_remoteconfig_failed_projects` | dict[str, str] | project_id to read error. |
| `firebase_condition_group` | str, optional | Condition group used for the value table view. |
| `firebase_condition_group_label` | str, optional | Display label for the selected condition group. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_remoteconfig_keys`, `firebase_remoteconfig_common_keys`, `firebase_remoteconfig_missing_keys`, `firebase_remoteconfig_key_profiles`, `firebase_remoteconfig_project_key_values`, `firebase_remoteconfig_project_conditions`, `firebase_remoteconfig_bulk_safe_keys`, `firebase_remoteconfig_bulk_blocked_keys`, `firebase_remoteconfig_type_conflicts`, `firebase_remoteconfig_value_types`, `firebase_remoteconfig_declared_value_types`, `firebase_remoteconfig_unknown_type_keys`, `firebase_remoteconfig_project_key_counts`, `firebase_remoteconfig_failed_projects`, `firebase_condition_group`, `firebase_condition_group_label` | If at least one project template could be read. |
| `Error` | - | If the plugin is unavailable, targets are missing, or every read fails. |

### `firebase_remoteconfig_conditions`

Show the template's conditions and choose which value a write targets.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_conditions
```

**Used by built-in workflows:** `read-remoteconfig`, `set-remoteconfig-value`

**Available to later steps:** `firebase_condition`, `firebase_condition_label`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_remoteconfig_template` | UIRemoteConfigTemplate | From firebase_remoteconfig_get. |
| `condition` | str, optional | Preselected condition name, or "default". |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_condition` | Optional[str] | Condition name, None for the default. |
| `firebase_condition_label` | str | User-facing label for the target. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_condition`, `firebase_condition_label` | If a target is chosen (or only the default exists). |
| `Error` | - | If the template is missing or the user cancels. |

### `firebase_remoteconfig_select_key`

Choose one Remote Config parameter while showing its configured values.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_select_key
```

**Used by built-in workflows:** `read-remoteconfig`, `set-remoteconfig-value`

**Available to later steps:** `firebase_key`, `firebase_value_type`, `firebase_current_value`, `firebase_parameter_values`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_remoteconfig_template` | UIRemoteConfigTemplate | From firebase_remoteconfig_get. |
| `firebase_condition` | Optional[str] | Write target, from firebase_remoteconfig_conditions. |
| `key` | str, optional | Preselected parameter key. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_key` | str | Selected parameter key. |
| `firebase_value_type` | str | Effective value type of the parameter. |
| `firebase_current_value` | Optional[str] | Raw current value, None if unset. |
| `firebase_parameter_values` | dict | Default and conditional values for the selected key. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_key`, `firebase_value_type`, `firebase_current_value`, `firebase_parameter_values` | If a parameter is selected. |
| `Error` | - | If the template is missing, the key is unknown, or the user cancels. |

## Writing One Project

### `firebase_remoteconfig_set_value`

Ask for the new value of the selected parameter and validate it.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_set_value
```

**Used by built-in workflows:** `set-remoteconfig-value`

**Available to later steps:** `firebase_change`, `firebase_new_value`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_project_id` | str | Target project. |
| `firebase_key` | str | Parameter to change. |
| `firebase_condition` | Optional[str] | Condition to write, None for the default. |
| `firebase_value_type` | Optional[str] | Type reported by the read. |
| `firebase_current_value` | Optional[str] | Current raw value. |
| `value` | str, optional | New value, for non-interactive runs. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_change` | UIRemoteConfigChange | The validated change. |
| `firebase_new_value` | str | Exact string that will be stored. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_change`, `firebase_new_value` | If the value is valid for the parameter type. |
| `Error` | - | If inputs are missing, the value is invalid, or the user cancels. |

### `firebase_remoteconfig_diff`

Render the pending change and ask the user to confirm it.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_diff
```

**Used by built-in workflows:** `set-remoteconfig-value`

**Available to later steps:** `firebase_change_confirmed`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_change` | UIRemoteConfigChange | From firebase_remoteconfig_set_value. |
| `firebase_project_id` | str | Target project. |
| `firebase_target_label` | Optional[str] | Display label for the project. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_change_confirmed` | bool | Always True when the step succeeds. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_change_confirmed` | If the user confirms the change. |
| `Exit` | - | If the change is a no-op, or the user declines. |
| `Error` | - | If there is no pending change to show. |

### `firebase_remoteconfig_publish`

Publish one confirmed change, validating it with Firebase first.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_publish
```

**Used by built-in workflows:** `set-remoteconfig-value`

**Available to later steps:** `firebase_published_version`, `firebase_published_author`, `firebase_publish_result`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_project_id` | str | Target project. |
| `firebase_change` | UIRemoteConfigChange | The change to publish. |
| `firebase_change_confirmed` | bool | Set by `firebase_remoteconfig_diff`. |
| `dry_run` | bool, optional | Validate only, publish nothing. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_published_version` | Optional[str] | New version number. |
| `firebase_published_author` | Optional[str] | Author Firebase recorded. |
| `firebase_publish_result` | UIRemoteConfigPublishResult | Full outcome. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_published_version`, `firebase_published_author`, `firebase_publish_result` | If Firebase validated (dry run) or published the template. |
| `Error` | - | If inputs are missing, the change is unconfirmed, or the write fails. |

## Writing Several Projects

### `firebase_remoteconfig_create_key_plan`

Build and validate a plan to create one Remote Config key.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_create_key_plan
```

**Used by built-in workflows:** `create-remoteconfig-key`

**Available to later steps:** `firebase_create_key_plan`, `firebase_create_key_rejected`, `firebase_key`, `firebase_value_type`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_targets` | list[FirebaseProjectTarget] | From firebase_select_targets. |
| `firebase_remoteconfig_key_profiles` | dict[str, dict], optional | From firebase_remoteconfig_fanout_list_keys. |
| `firebase_remoteconfig_project_conditions` | dict[str, list[dict]], optional | From firebase_remoteconfig_fanout_list_keys. |
| `firebase_remoteconfig_failed_projects` | dict[str, str], optional | From firebase_remoteconfig_fanout_list_keys. |
| `key` | str, optional | New parameter key. |
| `value_type` | str, optional | New parameter type: BOOLEAN, JSON, NUMBER or STRING. |
| `default_value` | str, optional | Default value to store. |
| `conditional_values` | dict | str, optional | Condition values as a mapping, JSON object, or condition=value list. |
| `description` | str, optional | Parameter description. |
| `target_project_ids` | str | list[str], optional | Projects where the key should be created. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_create_key_plan` | list[UIRemoteConfigKeyCreatePlanEntry] | Entries chosen for publishing. |
| `firebase_create_key_rejected` | list[UIRemoteConfigKeyCreatePlanEntry] | Entries left out. |
| `firebase_key` | str | Key selected for creation. |
| `firebase_value_type` | str | Declared value type. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_create_key_plan`, `firebase_create_key_rejected`, `firebase_key`, `firebase_value_type` | If at least one project is selected for publishing. |
| `Exit` | - | If the key already exists everywhere, no target validates, or the user selects none. |
| `Error` | - | If inputs are missing or invalid. |

### `firebase_remoteconfig_create_key_publish`

Validate and publish planned Remote Config key creations.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_create_key_publish
```

**Used by built-in workflows:** `create-remoteconfig-key`

**Available to later steps:** `firebase_create_key_outcomes`, `firebase_create_key_published`, `firebase_create_key_failed`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_create_key_plan` | list[UIRemoteConfigKeyCreatePlanEntry] | From firebase_remoteconfig_create_key_plan. |
| `dry_run` | bool, optional | Validate everywhere, publish nothing. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_create_key_outcomes` | list[UIRemoteConfigKeyCreateOutcome] | Per-project results. |
| `firebase_create_key_published` | int | Projects published. |
| `firebase_create_key_failed` | int | Projects that failed. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_create_key_outcomes`, `firebase_create_key_published`, `firebase_create_key_failed` | If at least one project published (or validated in a dry run). |
| `Error` | - | If the plan is missing or every project failed. |

### `firebase_remoteconfig_copy_key`

Choose one missing Remote Config key and plan where to create it.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_copy_key
```

**Available to later steps:** `firebase_key`, `firebase_copy_source_project_id`, `firebase_copy_plan`, `firebase_copy_rejected`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_targets` | list[FirebaseProjectTarget] | From firebase_select_targets. |
| `firebase_remoteconfig_key_profiles` | dict[str, dict] | From firebase_remoteconfig_fanout_list_keys. |
| `firebase_remoteconfig_failed_projects` | dict[str, str], optional | From firebase_remoteconfig_fanout_list_keys. |
| `key` | str, optional | Key to copy. |
| `firebase_key` | str, optional | Key to copy, as emitted by an earlier step. |
| `source_project_id` | str, optional | Project to copy the key from. |
| `firebase_source_project_id` | str, optional | Source project emitted by an earlier step. |
| `target_project_ids` | str | list[str], optional | Missing target projects to create the key in. |
| `firebase_target_project_ids` | str | list[str], optional | Target projects emitted by an earlier step. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_key` | str | Key selected for copying. |
| `firebase_copy_source_project_id` | str | Project used as the source. |
| `firebase_copy_plan` | list[UIRemoteConfigKeyCopyPlanEntry] | Entries selected for publishing. |
| `firebase_copy_rejected` | list[UIRemoteConfigKeyCopyPlanEntry] | Missing destinations left out. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_key`, `firebase_copy_source_project_id`, `firebase_copy_plan`, `firebase_copy_rejected` | If at least one missing target is selected. |
| `Exit` | - | If there are no missing keys or no selected destinations. |
| `Error` | - | If inventory, source, or target inputs are invalid. |

### `firebase_remoteconfig_fanout_plan`

Build the per-project plan for one parameter change.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_fanout_plan
```

**Used by built-in workflows:** `set-remoteconfig-value-multiproject`

**Available to later steps:** `firebase_fanout_plan`, `firebase_fanout_rejected`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_targets` | list[FirebaseProjectTarget] | From firebase_select_targets. |
| `firebase_remoteconfig_key_profiles` | dict[str, dict], optional | From firebase_remoteconfig_fanout_list_keys. |
| `firebase_remoteconfig_bulk_safe_keys` | list[str], optional | From firebase_remoteconfig_fanout_list_keys. |
| `firebase_remoteconfig_failed_projects` | dict[str, str], optional | From firebase_remoteconfig_fanout_list_keys. |
| `key` | str | Parameter to change. |
| `value` | str | New value. |
| `condition` | str, optional | Condition to write instead of the default. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_fanout_plan` | list[UIFanoutEntry] | Entries chosen to publish. |
| `firebase_fanout_rejected` | list[UIFanoutEntry] | Entries left out. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_fanout_plan`, `firebase_fanout_rejected` | If at least one project is selected for publishing. |
| `Exit` | - | If no project can take the change, or the user selects none. |
| `Error` | - | If inputs are missing. |

### `firebase_remoteconfig_fanout_publish`

Publish the planned change to each selected project.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_fanout_publish
```

**Used by built-in workflows:** `set-remoteconfig-value-multiproject`

**Available to later steps:** `firebase_fanout_outcomes`, `firebase_fanout_published`, `firebase_fanout_failed`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_fanout_plan` | list[UIFanoutEntry] | From firebase_remoteconfig_fanout_plan. |
| `dry_run` | bool, optional | Validate everywhere, publish nothing. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_fanout_outcomes` | list[UIFanoutOutcome] | Per-project results. |
| `firebase_fanout_published` | int | Projects published. |
| `firebase_fanout_failed` | int | Projects that failed. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_fanout_outcomes`, `firebase_fanout_published`, `firebase_fanout_failed` | If at least one project published (or validated in a dry run). |
| `Error` | - | If the plan is missing or every project failed. |

### `firebase_remoteconfig_sync_plan`

Build a plan to create several missing Remote Config keys.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_sync_plan
```

**Available to later steps:** `firebase_copy_plan`, `firebase_sync_keys`, `firebase_sync_rejected_keys`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_targets` | list[FirebaseProjectTarget] | From firebase_select_targets. |
| `firebase_remoteconfig_key_profiles` | dict[str, dict] | From firebase_remoteconfig_fanout_list_keys. |
| `firebase_remoteconfig_failed_projects` | dict[str, str], optional | From firebase_remoteconfig_fanout_list_keys. |
| `keys` | str | list[str], optional | Keys to synchronize. |
| `firebase_keys` | str | list[str], optional | Keys emitted by an earlier step. |
| `source_project_id` | str, optional | Source project used for every selected key when it contains it. |
| `firebase_source_project_id` | str, optional | Source project emitted by an earlier step. |
| `target_project_ids` | str | list[str], optional | Missing target projects to create keys in. |
| `firebase_target_project_ids` | str | list[str], optional | Target projects emitted by an earlier step. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_copy_plan` | list[UIRemoteConfigKeyCopyPlanEntry] | Entries selected for publishing. |
| `firebase_sync_keys` | list[str] | Keys selected for synchronization. |
| `firebase_sync_rejected_keys` | dict[str, str] | Candidate keys skipped and why. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_copy_plan`, `firebase_sync_keys`, `firebase_sync_rejected_keys` | If at least one copy entry is planned. |
| `Exit` | - | If there are no syncable missing keys or no selected destinations. |
| `Error` | - | If inventory, source, or target inputs are invalid. |

### `firebase_remoteconfig_sync_publish`

Validate and publish planned Remote Config key copies.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_sync_publish
```

**Available to later steps:** `firebase_copy_outcomes`, `firebase_copy_published`, `firebase_copy_failed`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_copy_plan` | list[UIRemoteConfigKeyCopyPlanEntry] | From firebase_remoteconfig_copy_key. |
| `dry_run` | bool, optional | Validate everywhere, publish nothing. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_copy_outcomes` | list[UIRemoteConfigKeyCopyOutcome] | Per-project results. |
| `firebase_copy_published` | int | Projects where the key was copied. |
| `firebase_copy_failed` | int | Projects that failed. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_copy_outcomes`, `firebase_copy_published`, `firebase_copy_failed` | If at least one project published (or validated in a dry run). |
| `Error` | - | If the plan is missing or every project failed. |
