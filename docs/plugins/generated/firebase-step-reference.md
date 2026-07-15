# Firebase Step Reference

This page is generated from the public step inventory and shows the documented workflow contract for each public step.

## Authentication

### `firebase_login`

Validate that the current user has a Firebase ADC session.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_login
```

**Available to later steps:** `firebase_account`, `firebase_login_command`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `fail_on_missing_auth` | bool, optional | Return Error when ADC is missing. Defaults to True. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_account` | Optional[str] | Active gcloud account reported by `gcloud auth list`. |
| `firebase_login_command` | str | Command the user can run to create an ADC session. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_account`, `firebase_login_command` | If gcloud ADC is available. |
| `Error` | - | If Firebase client or ADC auth is missing and fail_on_missing_auth is True. |
| `Skip` | `firebase_account`, `firebase_login_command` | If ADC auth is missing and fail_on_missing_auth is False. |

### `firebase_status`

Report the current Firebase ADC authentication status.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: firebase
  step: firebase_status
```

**Available to later steps:** `firebase_account`, `firebase_login_command`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.firebase` | - | An initialized FirebaseClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `fail_on_missing_auth` | bool, optional | Return Error when ADC is missing. Defaults to True. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `firebase_account` | Optional[str] | Active gcloud account reported by `gcloud auth list`. |
| `firebase_login_command` | str | Command the user can run to create an ADC session. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `firebase_account`, `firebase_login_command` | If gcloud ADC is available. |
| `Error` | - | If Firebase client or ADC auth is missing and fail_on_missing_auth is True. |
| `Skip` | `firebase_account`, `firebase_login_command` | If ADC auth is missing and fail_on_missing_auth is False. |

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
