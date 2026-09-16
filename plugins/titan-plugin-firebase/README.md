# titan-plugin-firebase

Firebase Remote Config for Titan CLI: read a project's template and publish
parameter changes, in one project or across several.

## Authentication

Application Default Credentials. Run once:

```bash
gcloud auth application-default login
```

Titan stores no credential of its own — `google.auth` reads the ADC session and
refreshes the token. That also means Firebase attributes every publish to your
own Google account, which is what the Remote Config version history shows.

## Configuration

Five fields, none of them a credential:

```toml
[plugins.firebase]
enabled = true

[plugins.firebase.config]
default_project = "my-firebase-project"
```

`default_project` is the only field the configuration wizard asks for.
`quota_project_id`, `api_base_url`, `request_timeout` and `oauth_scopes` all have working
defaults; set them by hand in `.titan/config.toml` if you need to.

## Several projects

The plugin is generic: it speaks about Firebase projects and knows nothing about
brands, naming patterns or environment maps. The multi-project steps read the
project list from workflow data, so a repository that runs one Firebase project
per brand (or per team, or per environment) keeps that mapping in its own plugin
and publishes the resolved IDs:

```python
return Success(
    "Projects resolved",
    metadata={
        "firebase_project_ids": ["mm-firebase-yoigo", "mm-guuk-firebase-prod"],
        # optional: show your own names instead of the raw IDs
        "firebase_project_labels": {"mm-guuk-firebase-prod": "guuk"},
    },
)
```

Then chain that step with this plugin's generic ones — workflows can use steps
from any installed plugin:

```yaml
steps:
  - id: resolve_projects
    plugin: my-plugin
    step: select_firebase_projects

  - id: firebase_remoteconfig_fanout_plan
    plugin: firebase
    step: firebase_remoteconfig_fanout_plan

  - id: firebase_remoteconfig_fanout_publish
    plugin: firebase
    step: firebase_remoteconfig_fanout_publish
```

The built-in multi-project workflow also accepts `project_ids` directly, as a
comma-separated param, so it is usable without any other plugin.

## Documentation

See `docs/plugins/firebase/` for the client API, the step contracts, and the
built-in workflows.
