# Titan Firebase Plugin

Firebase integration for Titan CLI workflows.

The plugin provides read-only Firebase Remote Config access for one project or
for several brand/environment projects.

## Requirements

Use one authentication source:

- Browser-based Google OAuth through Titan with a configured Google OAuth
  desktop client ID. Titan stores the refreshable credential in its OAuth token
  store.
- Short-lived OAuth access token in `FIREBASE_ACCESS_TOKEN`
- Short-lived OAuth access token saved manually. The `firebase_login` prompt
  saves manual tokens to the OAuth token store as a temporary fallback.
- A personal Google Cloud ADC session:

```bash
gcloud auth application-default login
```

One token can read several Firebase projects when the authenticated identity has
Remote Config permissions on each project. Manually pasted access tokens expire,
so refresh or replace them when Firebase starts returning `401`.
When a Remote Config request receives `401`, the workflow invalidates the
resolved token source, asks for fresh auth, and retries the request once.

Firebase credentials are resolved through Titan's shared OAuth manager.
Provider-backed Google OAuth stores `access_token`, `refresh_token`,
`expires_at`, and scopes, so Titan refreshes before requests if the token is near
expiry. The manual-token bridge cannot know expiry in advance because pasted
access tokens do not include that metadata.

The plugin configuration wizard presents Google OAuth first. If a workflow runs
without `oauth_client_id`, Titan asks for a Google OAuth client ID, saves it in
the user keyring with the Desktop app client secret, opens Google login, and
reuses the refreshable credential on later runs. If a saved refresh token fails,
Titan deletes that stale token and reauthorizes interactively. Pasting an access
token is the last fallback.

Use an OAuth client with application type `Desktop app` for Titan CLI. That
credential identifies the local tool that opens Google login and receives the
`127.0.0.1` loopback callback; it is separate from the Firebase iOS, Android, or
web app clients. Google may also require the Client Secret generated for that
same Desktop app client during token exchange; Titan stores it in keyring.

Titan resolves OAuth client credentials as an atomic pair: project-specific
keyring values, explicit plugin config values, then generic Firebase keyring
values. When the generic wizard stores the client ID in config and the client
secret in the project keyring, Titan treats those as one configured pair. It
does not combine a project-specific saved client ID with a different config
secret.

No service account files or shared credentials are stored by this plugin.

## Configuration

Titan configuration uses the standard `[plugins.<name>]` layout:

```toml
[plugins.firebase]
enabled = true

[plugins.firebase.config]
# Optional project used by firebase_remoteconfig_get when no project_id is passed.
default_project = "my-firebase-project"
default_environment = "prod"

# Optional overrides.
api_base_url = "https://firebaseremoteconfig.googleapis.com/v1"
request_timeout = 30
oauth_client_id = "your-google-oauth-desktop-client-id"
# Prefer storing oauth_client_secret in Titan keyring through the wizard.
oauth_redirect_port = 0
oauth_timeout = 180
oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]

[[plugins.firebase.config.projects]]
brand = "yoigo"
environment = "prod"
project_id = "yoigo-prod-project"

[[plugins.firebase.config.projects]]
brand = "masmovil"
environment = "prod"
project_id = "masmovil-prod-project"
```

`brand_projects` is also supported for compact project maps. By default it is
read as `environment -> brand -> project_id`.

## Public Steps

- `firebase_login`: checks that Firebase OAuth auth is available, opens Google
  login when `oauth_client_id` is configured, and falls back to a manual token
  prompt when browser OAuth is not configured.
- `firebase_status`: reports the current Firebase auth status.
- `firebase_remoteconfig_get`: reads the Remote Config template for one
  Firebase project and saves the template, version and ETag in `ctx.data`.
- `firebase_remoteconfig_inventory`: reads configured brand/environment
  projects and saves a normalized inventory of all Remote Config keys.

Remote Config access uses the REST API with an OAuth bearer token. If Firebase
rejects the selected token, Remote Config steps invalidate that source, prompt
for fresh auth, and retry once.
