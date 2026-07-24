# Firebase Client API

The public client is `titan_plugin_firebase.client.FirebaseClient`.

## Authentication

### `is_available(*, sink=None) -> bool`

Returns `True` when an OAuth access token can be resolved from
`FIREBASE_ACCESS_TOKEN`, Titan's OAuth token store, legacy Firebase keyring
keys, plugin configuration, or Google Cloud ADC.

The optional `sink` receives provider-neutral OAuth events. UI and headless
callers can observe resolution/refresh/login events without coupling the OAuth
manager to a specific presentation layer.

ADC tokens are obtained with:

```bash
gcloud auth application-default print-access-token
```

### `get_active_account() -> str | None`

Returns the active account reported by `gcloud auth list`, or `None` when no
active account can be resolved.

### `get_adc_access_token() -> str | None`

Returns the current ADC access token. Tokens are read from the local gcloud ADC
session and are never persisted by Titan.

### `build_oauth_request(interactive=False) -> OAuthRequest`

Builds the provider-neutral request used by Titan's OAuth manager. Firebase uses
provider `google`, connection ID `firebase:<project>`, the configured
`oauth_scopes`, the `access_token_env_var`, and legacy secret keys for
backwards compatibility.

### `get_oauth_credential(*, sink=None, interactive=False) -> OAuthCredential | None`

Returns the credential resolved by Titan's OAuth manager, if one is available.
This method can read environment tokens, stored OAuth token-set blobs, and
legacy Firebase keyring tokens. When `interactive=True` and `oauth_client_id` is
configured, the Google OAuth provider opens the browser, receives the localhost
callback, exchanges the authorization code with PKCE, and stores a refreshable
token set.

### `get_access_token(*, sink=None, interactive=False) -> str | None`

Returns the token Titan will use for Firebase REST calls. It checks the
configured `access_token_env_var` first, which defaults to
`FIREBASE_ACCESS_TOKEN`, through the OAuth manager. It then checks plugin
configuration and finally falls back to ADC.

With provider-backed Google OAuth, the OAuth manager refreshes stored tokens
before returning them when they are expired or inside the refresh margin. When
refresh fails during an interactive resolution, the stale token-set blob is
deleted and Titan runs a fresh authorization flow.

### `save_access_token(token: str, scope="user") -> None`

Stores a token as a single OAuth token-set blob through Titan's shared OAuth
manager. The default `user` scope writes to the system keyring. Tokens stored
this way are still short-lived OAuth access tokens; manually pasted tokens do
not include `expires_at`, so refresh or replace them when Firebase rejects them
as expired.

Browser-based Google OAuth stores `access_token`, `refresh_token`, `expires_at`,
token type, and granted scopes automatically; callers should prefer that flow
over manual access tokens.

### `save_oauth_client_id(client_id: str, client_secret=None, scope="user") -> None`

Stores a Google OAuth desktop client ID and optional Desktop app client secret
in the user keyring, then configures the current Firebase client session for
browser login. Titan saves both generic Firebase keys and project-specific keys
when a project name is available, so the same Google OAuth client can be reused
across Firebase projects. If no client secret is provided, stale saved client
secret keys are deleted so Titan does not send a mismatched OAuth pair later.

### `delete_oauth_client_id(scope="user") -> bool`

Deletes saved Google OAuth client IDs and client secrets for the current
project/generic Firebase scope, clears the runtime OAuth client configuration,
and unregisters the Google provider from the current client session.

### `configure_google_oauth(client_id: str, client_secret=None) -> None`

Configures browser-based Google OAuth for the current client session without
persisting the client ID or secret. This registers the Google provider used by
the shared OAuth manager for login and refresh. If the client ID changes and no
new client secret is provided, the previous runtime client secret is cleared.

### `invalidate_access_token_source(source: str | None, scope="user") -> bool`

Marks a rejected token source as unusable for the current client session.
Legacy keyring tokens are deleted from the selected secret scope; OAuth
token-store credentials are deleted from Titan's OAuth store. Environment,
plugin config, and ADC sources are ignored for the remainder of the current
client session.

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

The request uses an OAuth bearer token and sends `x-goog-user-project` with the
same project ID as quota project. It returns a `RemoteConfigTemplate` with:

- `project_id`: Firebase project ID used for the request
- `template`: Remote Config JSON payload
- `etag`: response `ETag` header, needed by future publish operations
- `version`: convenience property for `template["version"]`

Error handling distinguishes common Remote Config cases:

- `401`: OAuth token rejected or expired. The error keeps the resolved
  `auth_source`, so workflow steps can invalidate that source, prompt for
  fresh auth, and retry once.
- `403`: account lacks permission on the Firebase project
- `404`: project/template not found

### `get_remote_config_inventory(targets, continue_on_error=True) -> RemoteConfigInventory`

Reads several Firebase project targets and returns:

- `targets`: configured brand/environment targets
- `projects`: one normalized project inventory per successful template read
- `keys`: unique key inventory across projects, including observed value types
  and missing projects
- `failures`: per-project read failures when `continue_on_error` is `True`

Remote Config values are normalized into the supported value types:

- `BOOLEAN`
- `JSON`
- `NUMBER`
- `STRING`
- `UNKNOWN`
