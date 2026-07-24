# Firebase Plugin

The Firebase plugin provides ADC-backed access to Firebase Remote Config from
Titan workflows.

PR1 is intentionally read-only and single-project: it validates a personal
Google Cloud Application Default Credentials session and reads a Remote Config
template for an explicit Firebase project ID.

## Requirements

- `gcloud` installed in `PATH`
- A personal ADC login:

```bash
gcloud auth application-default login
```

The plugin does not use service account files, shared keys, `firebase-admin`, or
the Firebase CLI.

## Configuration

Enable the plugin in `.titan/config.toml`:

```toml
[plugins.firebase]
enabled = true

[plugins.firebase.config]
default_project = "my-firebase-project"
api_base_url = "https://firebaseremoteconfig.googleapis.com/v1"
request_timeout = 30
```

`default_project` is optional. If it is not configured, workflows must pass a
`project_id` parameter to `firebase_remoteconfig_get`.

`brand_projects` exists in the schema as a placeholder for PR2. Multibrand
project resolution should reuse the existing Crashlytics brand mapping rather
than duplicate project IDs in this plugin config.

## Entry Point

```toml
[tool.poetry.plugins."titan.plugins"]
firebase = "titan_plugin_firebase.plugin:FirebasePlugin"
```
