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

**Used by built-in workflows:** `read-remoteconfig`, `set-remoteconfig-value`, `set-remoteconfig-value-multibrand`

**Available to later steps:** `firebase_account`, `firebase_credential_kind`, `firebase_credential_is_user`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_account` | Optional[str] | Account the credentials belong to. |
| `firebase_credential_kind` | str | user, service_account, impersonated, ... |
| `firebase_credential_is_user` | bool | Whether publishes get a real author. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_account`, `firebase_credential_kind`, `firebase_credential_is_user` | If credentials resolve and can mint a token. |
| `Error` | - | If no ADC session exists or it cannot be refreshed. |

## Project and Brand Selection

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

**Used by built-in workflows:** `read-remoteconfig`, `set-remoteconfig-value`

**Available to later steps:** `firebase_project_id`, `firebase_brand`, `firebase_environment`, `firebase_target_label`

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `project_id` | str, optional | Explicit Firebase project ID. |
| `brand` | str, optional | Brand to resolve through the plugin config. |
| `environment` | str, optional | Environment for multi-environment configs. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_project_id` | str | Resolved project ID. |
| `firebase_brand` | Optional[str] | Brand behind the project, when known. |
| `firebase_environment` | Optional[str] | Environment, when configured. |
| `firebase_target_label` | str | User-facing reference for the target. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_project_id`, `firebase_brand`, `firebase_environment`, `firebase_target_label` | If a project could be resolved. |
| `Error` | - | If the plugin is unavailable, the user cancels, or nothing resolves. |

### `firebase_select_targets`

Resolve several Firebase projects, one per brand.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_select_targets
```

**Used by built-in workflows:** `set-remoteconfig-value-multibrand`

**Available to later steps:** `firebase_targets`, `firebase_environment`, `firebase_target_failures`

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `brands` | list[str] | str, optional | Brands to target; a comma-separated string is accepted. |
| `environment` | str, optional | Environment for multi-environment configs. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_targets` | list[FirebaseProjectTarget] | Resolved targets. |
| `firebase_environment` | Optional[str] | Environment in use. |
| `firebase_target_failures` | dict[str, str] | Unresolved brands and reasons. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_targets`, `firebase_environment`, `firebase_target_failures` | If at least one target resolved. |
| `Error` | - | If nothing is configured, the user cancels, or no brand resolved. |

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

**Used by built-in workflows:** `read-remoteconfig`, `set-remoteconfig-value`

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

Choose one Remote Config parameter.

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

**Available to later steps:** `firebase_key`, `firebase_value_type`, `firebase_current_value`

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

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_key`, `firebase_value_type`, `firebase_current_value` | If a parameter is selected. |
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
| `firebase_target_label` | Optional[str] | Brand/environment label. |

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

## Writing Several Brands

### `firebase_remoteconfig_fanout_plan`

Build the per-brand plan for one parameter change.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_fanout_plan
```

**Used by built-in workflows:** `set-remoteconfig-value-multibrand`

**Available to later steps:** `firebase_fanout_plan`, `firebase_fanout_rejected`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_targets` | list[FirebaseProjectTarget] | From firebase_select_targets. |
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
| `Success` | `firebase_fanout_plan`, `firebase_fanout_rejected` | If at least one brand is selected for publishing. |
| `Exit` | - | If no brand can take the change, or the user selects none. |
| `Error` | - | If inputs are missing. |

### `firebase_remoteconfig_fanout_publish`

Publish the planned change to each selected brand.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_fanout_publish
```

**Used by built-in workflows:** `set-remoteconfig-value-multibrand`

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
| `firebase_fanout_outcomes` | list[UIFanoutOutcome] | Per-brand results. |
| `firebase_fanout_published` | int | Brands published. |
| `firebase_fanout_failed` | int | Brands that failed. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_fanout_outcomes`, `firebase_fanout_published`, `firebase_fanout_failed` | If at least one brand published (or validated, in a dry run). |
| `Error` | - | If the plan is missing or every brand failed. |
