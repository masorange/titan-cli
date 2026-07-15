# Firebase Client API

The public client is `titan_plugin_firebase.client.FirebaseClient`.

## Authentication

### `is_available() -> bool`

Returns `True` when `gcloud` is installed and an ADC access token can be
obtained with:

```bash
gcloud auth application-default print-access-token
```

### `get_active_account() -> str | None`

Returns the active account reported by `gcloud auth list`, or `None` when no
active account can be resolved.

### `get_adc_access_token() -> str | None`

Returns the current ADC access token. Tokens are read from the local gcloud ADC
session and are never persisted by Titan.

### `get_login_command() -> str`

Returns the exact login command shown by Firebase auth steps:

```bash
gcloud auth application-default login
```

## Remote Config

### `get_remote_config(project_id: str) -> RemoteConfigTemplate`

Reads:

```text
GET {api_base_url}/projects/{project_id}/remoteConfig
```

The request uses an ADC bearer token and returns a `RemoteConfigTemplate` with:

- `project_id`: Firebase project ID used for the request
- `template`: Remote Config JSON payload
- `etag`: response `ETag` header, needed by future publish operations
- `version`: convenience property for `template["version"]`

Error handling distinguishes common Remote Config cases:

- `401`: ADC token rejected or expired; run the ADC login command
- `403`: account lacks permission on the Firebase project
- `404`: project/template not found
