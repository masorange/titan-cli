# Firebase Plugin

The Firebase plugin provides read-only Firebase Remote Config access from Titan
workflows.

It validates Firebase authentication, reads Remote Config templates, and can
build a normalized key inventory across several brand/environment projects.

## Requirements

Use one of these authentication sources:

1. Browser-based Google OAuth through Titan, using a configured Google OAuth
   desktop client ID. This stores an access token, refresh token, expiry, and
   scopes in Titan's OAuth token store.
2. A short-lived OAuth access token in `FIREBASE_ACCESS_TOKEN`.
3. A short-lived OAuth access token saved manually. The `firebase_login` prompt
   stores manual tokens in Titan's OAuth token store as a temporary fallback.
   Legacy keys `firebase_access_token` and `<project>_firebase_access_token`
   may still exist from older versions; those keys are still read by the OAuth
   manager.
4. A personal Google Cloud Application Default Credentials login:

```bash
gcloud auth application-default login
```

One token can read several Firebase projects when the authenticated identity has
Remote Config permissions on each project.

Titan resolves Firebase credentials through the shared OAuth manager. That layer
is asynchronous-ready, emits provider-neutral events, stores one token-set blob
per credential, and uses credential-scoped locks before refresh/login
operations. Browser-based Google OAuth tokens include `expires_at` and a
`refresh_token`, so Titan refreshes them before requests when they are near
expiry. Manually pasted access tokens do not include expiry metadata, so replace
them when Firebase rejects them as expired.

The plugin does not use service account files, shared keys, `firebase-admin`, or
the Firebase CLI.

## Configuration

Enable the plugin in `.titan/config.toml`:

```toml
[plugins.firebase]
enabled = true

[plugins.firebase.config]
default_project = "my-firebase-project"
default_environment = "prod"
api_base_url = "https://firebaseremoteconfig.googleapis.com/v1"
request_timeout = 30
oauth_client_id = "your-google-oauth-desktop-client-id"
# Prefer storing oauth_client_secret in Titan keyring through the wizard.
oauth_redirect_port = 0
oauth_timeout = 180
oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
```

`oauth_client_id` should be a Google OAuth client configured with application
type `Desktop app`. This client ID identifies Titan CLI as the installed tool
running the login flow; it is not the Firebase iOS, Android, or web app client.
Titan uses Authorization Code with PKCE and can store the Desktop app
`oauth_client_secret` in Titan's keyring when Google requires it during token
exchange. `oauth_redirect_port = 0` lets Titan choose a free `127.0.0.1`
loopback port for the callback.

Titan resolves OAuth client credentials as an atomic pair: project-specific
keyring values, explicit plugin config values, then generic Firebase keyring
values. When the generic wizard stores the client ID in config and the client
secret in the project keyring, Titan treats those as one configured pair. It
does not combine a project-specific saved client ID with a different config
secret, because Google's token endpoint rejects mismatched Desktop app
credentials.

The browser OAuth default uses `https://www.googleapis.com/auth/cloud-platform`
because Google accepts it in the user consent flow and the Firebase Remote
Config REST API lists it as an accepted authorization scope. The narrower
`https://www.googleapis.com/auth/firebase.remoteconfig` scope is still valid for
Remote Config API calls, but Google may reject it during interactive user
consent with `invalid_scope`.

Do not store `access_token` manually in `.titan/config.toml`. Prefer configuring
`oauth_client_id` and running `firebase_login` so Titan opens Google login and
stores a refreshable credential. Use manual access tokens only as a temporary
fallback, or set `FIREBASE_ACCESS_TOKEN` only for the current shell session.

When `firebase_login` runs interactively and no token is available, it opens the
browser for Google login if `oauth_client_id` is configured. If browser OAuth is
not configured yet, it asks for the Google OAuth Desktop app client ID and
client secret, saves them in the user keyring, opens Google login, and stores a
refreshable credential. If a saved refresh token fails, Titan deletes that stale
token and reauthorizes interactively instead of keeping the workflow stuck on
the old credential. Manual access tokens are only the final fallback.

`default_project` is optional. If it is not configured, workflows must pass a
`project_id` parameter to `firebase_remoteconfig_get`.

For multibrand inventories, prefer explicit project targets:

```toml
[[plugins.firebase.config.projects]]
brand = "yoigo"
environment = "prod"
project_id = "yoigo-prod-project"

[[plugins.firebase.config.projects]]
brand = "masmovil"
environment = "prod"
project_id = "masmovil-prod-project"
```

The compact `brand_projects` mapping is also supported. By default it is read as
`environment -> brand -> project_id`:

```toml
[plugins.firebase.config.brand_projects.prod]
yoigo = "yoigo-prod-project"
masmovil = "masmovil-prod-project"
```

If your source data is `brand -> environment -> project_id`, set:

```toml
[plugins.firebase.config]
brand_projects_layout = "brand_environment"
```

## Entry Point

```toml
[tool.poetry.plugins."titan.plugins"]
firebase = "titan_plugin_firebase.plugin:FirebasePlugin"
```
