# Titan Firebase Plugin

Firebase integration for Titan CLI workflows.

PR1 provides individual authentication through Google Cloud Application Default
Credentials (ADC) and read-only Firebase Remote Config access for one explicit
Firebase project.

## Requirements

- `gcloud` installed and available in `PATH`
- A personal ADC session:

```bash
gcloud auth application-default login
```

No service account files or shared credentials are stored by this plugin.

## Configuration

Titan configuration uses the standard `[plugins.<name>]` layout:

```toml
[plugins.firebase]
enabled = true

[plugins.firebase.config]
# Optional project used by firebase_remoteconfig_get when no project_id is passed.
default_project = "my-firebase-project"

# Optional overrides.
api_base_url = "https://firebaseremoteconfig.googleapis.com/v1"
request_timeout = 30
```

`brand_projects` is intentionally empty in PR1. The multibrand workflow planned
for PR2 will reuse the existing Crashlytics brand mapping instead of duplicating
project IDs here.

## Public Steps

- `firebase_login`: checks that ADC is available and shows the login command
  when it is not.
- `firebase_status`: reports the current ADC/gcloud status.
- `firebase_remoteconfig_get`: reads the Remote Config template for one
  Firebase project and saves the template, version and ETag in `ctx.data`.

Remote Config access uses the REST API with the ADC bearer token.
