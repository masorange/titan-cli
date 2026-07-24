# Firebase Step Reference

This page is generated from the public step inventory and shows the documented workflow contract for each public step.

## Authentication

### `firebase_login`

Validate that the current user has Firebase OAuth authentication.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_login
```

**Used by built-in workflows:** `list-remoteconfig-keys`

**Available to later steps:** `firebase_account`, `firebase_auth_source`, `firebase_login_command`, `firebase_access_token_saved`, `firebase_oauth_login_completed`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `fail_on_missing_auth` | bool, optional | Return Error when auth is missing. Defaults to True. |
| `prompt_for_missing_auth` | bool, optional | Prompt for Google OAuth setup/login when auth is missing. Defaults to True. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_account` | Optional[str] | Reserved until Firebase token identity can be resolved; currently None. |
| `firebase_auth_source` | Optional[str] | Safe source label for the token Titan will use. |
| `firebase_login_command` | str | Command the user can run to create an ADC session. |
| `firebase_access_token_saved` | bool | Whether this step saved a token to Titan's OAuth token store. |
| `firebase_oauth_login_completed` | bool | Whether this step completed browser OAuth login. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_account`, `firebase_auth_source`, `firebase_login_command`, `firebase_access_token_saved`, `firebase_oauth_login_completed` | If Firebase OAuth auth is available. |
| `Error` | - | If Firebase client or auth is missing and fail_on_missing_auth is True. |
| `Skip` | `firebase_account`, `firebase_auth_source`, `firebase_login_command`, `firebase_access_token_saved`, `firebase_oauth_login_completed` | If auth is missing and fail_on_missing_auth is False. |

### `firebase_status`

Report the current Firebase OAuth authentication status.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_status
```

**Available to later steps:** `firebase_account`, `firebase_auth_source`, `firebase_login_command`, `firebase_access_token_saved`, `firebase_oauth_login_completed`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `fail_on_missing_auth` | bool, optional | Return Error when auth is missing. Defaults to True. |
| `prompt_for_missing_auth` | bool, optional | Prompt for Google OAuth setup/login when auth is missing. Defaults to False. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_account` | Optional[str] | Reserved until Firebase token identity can be resolved; currently None. |
| `firebase_auth_source` | Optional[str] | Safe source label for the token Titan will use. |
| `firebase_login_command` | str | Command the user can run to create an ADC session. |
| `firebase_access_token_saved` | bool | Whether this step saved a token to Titan's OAuth token store. |
| `firebase_oauth_login_completed` | bool | Whether this step completed browser OAuth login. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_account`, `firebase_auth_source`, `firebase_login_command`, `firebase_access_token_saved`, `firebase_oauth_login_completed` | If Firebase OAuth auth is available. |
| `Error` | - | If Firebase client or auth is missing and fail_on_missing_auth is True. |
| `Skip` | `firebase_account`, `firebase_auth_source`, `firebase_login_command`, `firebase_access_token_saved`, `firebase_oauth_login_completed` | If auth is missing and fail_on_missing_auth is False. |

## Remote Config

### `firebase_remoteconfig_get`

Read a Firebase Remote Config template for one project.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_get
```

**Available to later steps:** `firebase_project_id`, `firebase_remoteconfig_template`, `firebase_remoteconfig_etag`, `firebase_remoteconfig_version`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `project_id` | str, optional | Firebase project ID to read. |
| `firebase_project_id` | str, optional | Alternate project ID key from a previous step. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_project_id` | str | Firebase project ID used for the request. |
| `firebase_remoteconfig_template` | dict | Remote Config template JSON payload. |
| `firebase_remoteconfig_etag` | Optional[str] | ETag returned by Firebase for later publishing. |
| `firebase_remoteconfig_version` | Optional[dict] | Remote Config template version payload. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_project_id`, `firebase_remoteconfig_template`, `firebase_remoteconfig_etag`, `firebase_remoteconfig_version` | If the Remote Config template is read successfully. |
| `Error` | - | If Firebase is unavailable, no project ID is provided, or the API request fails. |

### `firebase_remoteconfig_inventory`

Build a key inventory across configured Firebase Remote Config projects.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_remoteconfig_inventory
```

**Used by built-in workflows:** `list-remoteconfig-keys`

**Available to later steps:** `firebase_remoteconfig_inventory`, `firebase_remoteconfig_keys`, `firebase_remoteconfig_targets`, `firebase_remoteconfig_project_count`, `firebase_remoteconfig_key_count`, `firebase_remoteconfig_failures`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `project_targets` | list[dict], optional | Explicit Firebase project targets. |
| `firebase_project_targets` | list[dict], optional | Alternate explicit target key. |
| `projects` | list[dict|str], optional | Firebase project targets or project IDs. |
| `brand_projects` | dict, optional | Brand/environment project mapping override. |
| `brand` | str, optional | Single brand filter. |
| `brands` | list[str]|str, optional | Brand filter list or comma-separated string. |
| `environment` | str, optional | Single environment filter. |
| `environments` | list[str]|str, optional | Environment filter list or comma-separated string. |
| `continue_on_error` | bool, optional | Continue when one project read fails. Defaults to True. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_remoteconfig_inventory` | dict | Aggregated inventory payload. |
| `firebase_remoteconfig_keys` | list[dict] | Unique key inventory rows. |
| `firebase_remoteconfig_targets` | list[dict] | Project targets that were requested. |
| `firebase_remoteconfig_project_count` | int | Number of projects read successfully. |
| `firebase_remoteconfig_key_count` | int | Number of unique keys found. |
| `firebase_remoteconfig_failures` | list[dict] | Project read failures, when any. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_remoteconfig_inventory`, `firebase_remoteconfig_keys`, `firebase_remoteconfig_targets`, `firebase_remoteconfig_project_count`, `firebase_remoteconfig_key_count`, `firebase_remoteconfig_failures` | If at least one project is read and key inventory is built. |
| `Error` | - | If Firebase is unavailable, no targets are configured, or all project reads fail. |
