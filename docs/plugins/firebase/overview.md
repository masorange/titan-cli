# Firebase Plugin

The Firebase plugin reads and writes Firebase Remote Config: it lists a project's
parameters and conditions, compares keys and values across projects, creates new keys
where they are needed, and applies value changes across one or several projects.

It exposes:

- a public `FirebaseClient`
- reusable workflow steps for reading, creating keys, writing values, and
  multi-project fan-out
- three product-level workflows in the picker, plus reusable lower-level
  workflow definitions for one-project and diagnostic flows

## Authentication

Authentication is **Application Default Credentials (ADC)**. Run once:

```bash
gcloud auth application-default login
```

Titan stores no Firebase credential of its own. `google.auth` reads the ADC session and
refreshes the access token, and the authorized HTTP session sets the `Authorization`
header itself — the plugin never handles the token, and never asks the secret broker for
anything.

That has a consequence worth understanding before you write anything: **Firebase
attributes every published version to the identity behind the token.** With user
credentials that is you, so the Remote Config version history in the Firebase console
shows your email with origin `REST_API`. If `GOOGLE_APPLICATION_CREDENTIALS` points at a
service account, every publish is attributed to that service account instead, and the
`firebase_auth_check` step warns about it.

The default ADC scope (`cloud-platform`) covers Remote Config. The narrow scope is
`https://www.googleapis.com/auth/firebase.remoteconfig`.

Titan reports which *kind* of credential is active but not the signed-in email: an ADC
session minted for `cloud-platform` need not carry the `userinfo.email` scope. The account
that matters appears on the published version, which the publish step reports back.

## Requirements

- Enable the `firebase` plugin in `.titan/config.toml`
- An ADC session (`gcloud auth application-default login`)
- Read access to Remote Config in the target projects; publishing additionally needs
  update permission, which is often restricted in production projects

## Configuration

The plugin has no credential fields and no hardcoded business naming scheme. It is
generic: it speaks about Firebase projects, named project sets, display labels, optional
brands, optional environments, and group tags. A repository can assign whatever meaning it
wants to those fields in its own `.titan/config.toml`.

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

`default_project` is used by lower-level one-project workflow definitions.
`default_project_set` is used by product-level multi-project workflows when `project_ids`
is not passed. The rest have working defaults:

| Option | Default | What it does |
|--------|---------|--------------|
| `default_project` | `None` | Firebase project ID for one-project workflows. |
| `default_project_set` | `None` | Project set name used by multi-project workflows when no project list is passed. |
| `default_environment` | `None` | Environment metadata inherited by projects that omit it, and preselected by TUI project-set workflows when several environments are available. |
| `default_condition_group` | `None` | Remote Config condition/value group used by inventory views when no workflow param names one. |
| `condition_groups` | `{}` | Named Remote Config value views, each selecting `default` plus exact, prefix, or contains matches over condition names. |
| `project_sets` | `{}` | Project-local Firebase target sets, each with projects, optional labels, brands, environments, and group tags. |
| `quota_project_id` | the credential's own quota project, else the project being read | Which project is billed for API quota. Override it when your account lacks `serviceusage.services.use` on the Firebase project itself. Titan applies it to the credential, because `google.auth` overwrites the `x-goog-user-project` header with the credential's value on every request. |
| `api_base_url` | `https://firebaseremoteconfig.googleapis.com/v1` | Remote Config REST base URL. |
| `request_timeout` | `30` | HTTP timeout in seconds. |
| `oauth_scopes` | `["https://www.googleapis.com/auth/cloud-platform"]` | Scopes requested from ADC. |

The workflow picker intentionally shows only the product-level Firebase Remote Config
entries: `create-remoteconfig-key`, `list-remoteconfig-keys-multiproject`, and
`set-remoteconfig-value-multiproject`. The single-project and diagnostic YAML definitions
still ship for compatibility and composition, but they are not shown as default menu
choices.

When a workflow runs in the TUI without a configured or passed project, Titan first asks
Firebase Management for the projects available to the active ADC session and lets the user
choose from that list. If the project list cannot be loaded, the workflow falls back to a
manual project ID prompt.

Firebase Management does not expose Titan's brand, group, or environment metadata. When
Titan recovers the project catalogue, it enriches matching projects from
`plugins.firebase.config.project_sets`, including inherited `default_environment` values.

For large Firebase accounts, pass `project_filter` to narrow that catalogue before the
selector is shown. The filter is a set of case-insensitive words matched against project
IDs, display names, configured labels, brands, environments, group tags, resource names,
and project numbers, so `Prepago, National` keeps projects whose visible metadata contains
either family.

## Working with several projects

One Firebase project per brand, per team, or per environment is a naming scheme that belongs
to the repository that has it — not to Firebase. Multi-project steps therefore accept
generic ways to know their targets:

- `firebase_project_ids` — the projects to act on, published by an earlier step (or passed
  to the built-in workflow as the `project_ids` param, comma-separated).
- `firebase_project_labels` — optional `project_id -> label`, so tables and prompts can show
  your own vocabulary while this plugin stays unaware of what the names mean.
- `firebase_project_brands` — optional `project_id -> brand`, used as display metadata.
- `firebase_project_environments` — optional `project_id -> environment`, used to recover
  and guard environment context.
- `project_set` / `firebase_project_set` — a configured set under
  `plugins.firebase.config.project_sets`, falling back to `default_project_set`.
- `project_groups` / `firebase_project_groups` — optional group tags used to keep only part
  of a configured project set.
- `environment` / `firebase_environment` — optional environment filter such as `dev` or
  `pro`; when omitted in the TUI and several environments are present, Titan asks which
  environments to include.
- `firebase_project_filter` — optional catalogue filter published by an earlier step, useful
  when the generic TUI selector should only show families such as `Prepago` and `National`.

A plugin that owns such a mapping resolves it and publishes the result:

```python
return Success(
    "Projects resolved",
    metadata={
        "firebase_project_ids": ["mm-firebase-yoigo", "mm-guuk-firebase-prod"],
        "firebase_project_labels": {"mm-guuk-firebase-prod": "Guuk PRO"},
        "firebase_project_brands": {"mm-guuk-firebase-prod": "Guuk"},
        "firebase_project_environments": {"mm-guuk-firebase-prod": "pro"},
    },
)
```

Workflows can use steps from any installed plugin, so that step chains directly with
`firebase_remoteconfig_fanout_plan` and `firebase_remoteconfig_fanout_publish`.

Write workflows validate and confirm each selected project separately. When the selected
project set contains several known environments, Titan asks which ones to include first,
so a single run can intentionally target `dev`, `pro`, or both.

For a read-only inventory, chain the same project-selection step with
`firebase_remoteconfig_fanout_list_keys`. It reads each project in series and reports the
union of keys, keys present in every readable project, keys missing per project,
deterministic value-type profiles, bulk-safe keys, and type conflicts between projects.
It also displays each key's default value and condition-specific values per project, so
multi-brand drift can be reviewed before planning a write. One expandable comparison
per key combines its coverage, type status, and every selected project's value per
Remote Config environment/condition (`default`, `android_prod`, `ios_prod`, or whatever
the template declares). The configured project environment (`DEV`, `PRO`, or the
repository's own vocabulary) appears in a separate column, including for projects where
the key is missing. Structured JSON values open as nested trees. Pass
`condition_group=android` or configure `default_condition_group` to focus the comparison
on one named value view.

For creating new keys, use `create-remoteconfig-key`. It selects the configured project
set or explicit project IDs, audits which projects already have the key, asks for the
new key's type, default value and optional condition values, validates the payload in
each target project, and then validates/publishes each selected project with its own
ETag. Existing target keys are never overwritten.

## Environments and conditions

Remote Config has no environment concept of its own. What a project has is
**conditions** — named expressions such as `android_prod` — and each parameter can carry
a value per condition on top of its default value. The plugin reads the conditions from
the template rather than taking a configured list, so what you can target is always what
the project actually declares.

Separate deployment environments such as dev, pre and pro are usually represented as
separate Firebase projects. Titan models that project-level environment as optional
metadata in `project_sets`, lets workflows filter with `environment=dev` or
`environment=pro`, and in the TUI can ask for several environments in one run.
Conditions remain template data; environments remain project-selection data.

## How writes work

Remote Config has no per-parameter write endpoint: publishing replaces the whole
template. Every write here is therefore a read-modify-write:

1. Read the template and its `ETag`.
2. Replace exactly one value, carrying everything else over untouched.
3. `PUT ?validate_only=true` with `If-Match: <etag>` so Firebase checks the payload.
4. `PUT` with the same `If-Match` to publish. The version number increases by one.

`If-Match` is always the ETag from the read, never `*`. If someone published in between,
Firebase answers 409 and the plugin re-reads and reapplies the change once — so a
concurrent edit in the Firebase console fails loudly instead of being silently
overwritten.

Values are validated against the parameter's type before any request. Titan normalizes
Firebase's value type strings into `RemoteConfigValueType`: `BOOLEAN` (shown as `Bool`),
`JSON`, `NUMBER` (shown as `Number`), `STRING` (shown as `String`), and `UNKNOWN`.
Unknown or absent declared types are inferred deterministically from all explicit stored
values when building a multi-project inventory. A key is bulk-safe only when every
readable project has it, all projects agree on one known effective type, and no legacy
untyped project has mixed inferred values or Firebase-managed value sources. Booleans are
edited with a choice control and normalized to Firebase's `true`/`false` literals, JSON
uses a multiline editor and is stored compacted, numbers are checked, and strings preserve
user-entered whitespace. Writing a conditional value for a condition the template does not
declare is refused locally.

The REST API models each stored value as a union. Titan edits literal `value` entries and
can replace `useInAppDefault` with a literal value, but it preserves and refuses to
overwrite `personalizationValue`, `experimentValue`, `rolloutValue`, or future unknown
value-source fields. Inventories expose those values as managed by Firebase so they are
reviewed in the console or by a future dedicated workflow instead of being silently
converted into plain strings.

Creating a key builds the full parameter payload from typed input. Condition-specific
values can only be supplied for condition names that exist in every selected target
project; otherwise the workflow stops before any publish.

Each publish carries a description Titan generates — the key, the target, and the value
before and after — which appears in the version history next to your email.

## Limits to know

Remote Config caps a template at 2000 parameters, keeps at most 300 stored versions, and
retains each for 90 days.

## Related pages

- [Client API](client-api.md)
- [Workflow Steps](workflow-steps.md)
- [Built-in Workflows](built-in-workflows.md)
