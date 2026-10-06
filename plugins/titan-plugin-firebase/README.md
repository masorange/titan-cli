# titan-plugin-firebase

Firebase Remote Config for Titan CLI: read a project's template, compare keys
and values across several projects, create new keys where they are needed, and
publish parameter changes in one project or across several.

## Authentication

Application Default Credentials. Run once:

```bash
gcloud auth application-default login
```

Titan stores no credential of its own — `google.auth` reads the ADC session and
refreshes the token. That also means Firebase attributes every publish to your
own Google account, which is what the Remote Config version history shows.

## Configuration

No credentials are configured here:

```toml
[plugins.firebase]
enabled = true

[plugins.firebase.config]
default_project = "my-firebase-project"
default_project_set = "mobile_apps"
default_environment = "dev"
default_condition_group = "android"

[plugins.firebase.config.condition_groups.android]
label = "Android"
include_default = true
condition_contains = ["Android"]

[plugins.firebase.config.condition_groups.ios]
label = "iOS"
include_default = true
condition_contains = ["iOS"]

[plugins.firebase.config.project_sets.mobile_apps]
description = "Mobile app Remote Config projects"

[[plugins.firebase.config.project_sets.mobile_apps.projects]]
project_id = "my-firebase-project"
label = "Main app"
brand = "Main"
environment = "dev"
groups = ["production"]
```

`default_project` is kept for lower-level one-project workflow definitions.
`default_project_set` and `project_sets` feed the product-level multi-project
workflows shown in the picker. `quota_project_id`, `api_base_url`,
`request_timeout` and `oauth_scopes` all have working defaults.
`condition_groups` are optional Remote Config value views: use them to show only
the default plus Android conditions, iOS conditions, or any repository-owned
grouping of condition names. A workflow can override the default with
`condition_group=ios`.

If a workflow runs in the TUI without a project ID, the plugin first lists the
Firebase projects available to the active ADC session and lets you choose. The
lower-level `list-projects` workflow can also show that catalogue directly when
run by name. Pass `project_filter`, for example `Prepago, National`, to narrow a
large catalogue by project ID, display name, resource name or project number
before selecting projects.

## Several projects

The plugin is generic: it speaks about Firebase projects, labels, brands,
environments and groups, but does not hardcode what those words mean for any
company. A repository that runs one Firebase project per brand, per team, or per
environment can configure a project set in `.titan/config.toml`, or publish the
resolved IDs and metadata from its own project/plugin step:

```python
return Success(
    "Projects resolved",
    metadata={
        "firebase_project_ids": ["mm-firebase-yoigo", "mm-guuk-firebase-prod"],
        # optional metadata used for display and safe filtering
        "firebase_project_labels": {"mm-guuk-firebase-prod": "Guuk PRO"},
        "firebase_project_brands": {"mm-guuk-firebase-prod": "Guuk"},
        "firebase_project_environments": {"mm-guuk-firebase-prod": "pro"},
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
comma-separated param, so it is usable without any other plugin. Use
`project_set`, `project_groups` and `environment` to pick configured subsets, or
`project_filter` to choose interactively from a filtered Firebase catalogue. If a
configured set spans several known environments and no `environment` param is
passed, the TUI asks which environments to include before any write plan is
built.

Firebase Management does not expose Titan's brand/environment metadata. When
Titan lists Firebase projects, it enriches the recovered catalogue by matching
each `project_id` against configured `project_sets`, including inherited
`default_environment` values.

The workflow picker intentionally shows only the product-level entries:
`create-remoteconfig-key`, `list-remoteconfig-keys-multiproject`, and
`set-remoteconfig-value-multiproject`. The single-project and diagnostic YAML
definitions still ship for compatibility and composition, but they do not crowd
the default menu.

For inventory work, use `list-remoteconfig-keys-multiproject`: it reads the
selected projects one by one, shows key presence, deterministic type profiles,
bulk-safe keys, type conflicts, and one expandable comparison per key. Each
comparison contains the value that every project has for each Remote Config
environment/condition (`default`, `android_prod`, `ios_prod`, or whatever the
template declares). The configured project environment (`DEV`, `PRO`, or the
repository's own vocabulary) is shown separately from that Remote Config
condition, including when the key is missing. Structured JSON values open as
nested trees. Pass `condition_group=android` or configure
`default_condition_group` to focus the comparison on one configured view.

Titan normalizes Firebase value types into `RemoteConfigValueType`: `Bool`,
`JSON`, `Number`, `String` and `Unknown` for display. The underlying workflow
metadata still uses Firebase-compatible names such as `BOOLEAN` and `STRING`.
Each type drives a different input shape: booleans use choices, JSON uses a
multiline editor, numbers are validated as numeric text, and strings preserve
user-entered whitespace.

Firebase parameter values are union payloads, not always editable literals:
besides `value` and `useInAppDefault`, the REST API can return
`personalizationValue`, `experimentValue` and `rolloutValue`. Titan preserves
those fields when it round-trips the template, shows them as managed values in
inventories, and refuses to edit or copy them until a workflow explicitly
supports that Firebase-managed source.

Use `create-remoteconfig-key` to add a new key to selected projects where it is
missing. Titan reads the configured project set, asks for the key shape
(`Bool`, `JSON`, `Number` or `String`), default value and optional condition
values, validates the payload in every selected project, then publishes one
project at a time with that project's ETag. The selected projects may include
DEV, PRO or both when those environments are configured. Existing target keys
are never overwritten.

Use `set-remoteconfig-value-multiproject` to modify values for an existing key
across selected brands and environments. The workflow can target the default
value or one Remote Config condition, validates every project separately, and
asks which projects should receive the change before publishing.

## Documentation

See `docs/plugins/firebase/` for the client API, the step contracts, and the
built-in workflows.
