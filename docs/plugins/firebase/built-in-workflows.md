# Firebase Built-In Workflows

## `list-remoteconfig-keys`

Reads Remote Config templates across configured Firebase brand/environment
projects and stores a normalized key inventory in workflow context.

```yaml
name: "List Firebase Remote Config Keys"
steps:
  - plugin: firebase
    step: firebase_login

  - plugin: firebase
    step: firebase_remoteconfig_inventory
```

Configure targets with `plugins.firebase.config.projects` or
`plugins.firebase.config.brand_projects`. The workflow is read-only and keeps
reading later projects by default when one project returns an error.

If `plugins.firebase.config.oauth_client_id` is configured and no Firebase token
is available, `firebase_login` opens Google OAuth in the browser and stores a
refreshable credential before listing Remote Config keys. If the client ID is
not configured yet, the workflow asks for it first and saves it in the user
keyring.
