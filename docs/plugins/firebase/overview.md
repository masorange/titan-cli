# Firebase Plugin

The Firebase plugin reads and writes Firebase Remote Config: it lists a project's
parameters and conditions, changes one parameter's value, and applies the same change
across several brands, each of which is its own Firebase project.

It exposes:

- a public `FirebaseClient`
- reusable workflow steps for reading, writing, and multi-brand fan-out
- three built-in workflows

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

The plugin has no credential fields. Configuration is about which projects a repository
targets.

```toml
[plugins.firebase]
enabled = true

[plugins.firebase.config]
# Single-project setups
default_project = "mm-firebase-dev"

# Multi-brand setups: one Firebase project per brand
brands = ["yoigo", "masmovil", "lebara", "llamaya", "guuk"]
project_id_pattern = "mm-firebase-{brand}"

[plugins.firebase.config.brand_project_overrides]
guuk = "mm-guuk-firebase-prod"
```

Three sources can name a project, in order of specificity:

1. `brand_projects` — an explicit mapping, for project IDs that follow no rule.
2. `project_id_pattern` plus `brand_project_overrides` — a naming convention with
   exceptions.
3. `default_project` — the single-project case.

`brand_projects` is nested by environment and brand, with the shape given by
`brand_projects_layout`:

```toml
[plugins.firebase.config]
brand_projects_layout = "environment_brand"   # or "brand_environment"
default_environment = "pro"

[plugins.firebase.config.brand_projects.pre]
yoigo = "mm-firebase-yoigo-pre"

[plugins.firebase.config.brand_projects.pro]
yoigo = "mm-firebase-yoigo"
```

Other options:

| Option | Default | What it does |
|--------|---------|--------------|
| `quota_project_id` | the credential's own quota project, else the project being read | Which project is billed for API quota. Override it when your account lacks `serviceusage.services.use` on the Firebase project itself. Titan applies it to the credential, because `google.auth` overwrites the `x-goog-user-project` header with the credential's value on every request. |
| `api_base_url` | `https://firebaseremoteconfig.googleapis.com/v1` | Remote Config REST base URL. |
| `request_timeout` | `30` | HTTP timeout in seconds. |
| `oauth_scopes` | `["https://www.googleapis.com/auth/cloud-platform"]` | Scopes requested from ADC. |

## Environments are conditions

Remote Config has no environment concept of its own. What a project has is
**conditions** — named expressions such as `android_prod` — and each parameter can carry
a value per condition on top of its default value. The plugin reads the conditions from
the template rather than taking a configured list, so what you can target is always what
the project actually declares.

Separate environments per brand (dev, pre, pro) are therefore separate Firebase
projects, which is what `brand_projects` and `default_environment` model.

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

Values are validated against the parameter's type before any request. Booleans are
normalized to the literals Firebase accepts (`"True"`, `"1"` and `"0"` are documented as
wrong), JSON is parsed and stored compacted, and numbers are checked. Writing a
conditional value for a condition the template does not declare is refused locally.

Each publish carries a description Titan generates — the key, the target, and the value
before and after — which appears in the version history next to your email.

## Limits to know

Remote Config caps a template at 2000 parameters, keeps at most 300 stored versions, and
retains each for 90 days.

## Related pages

- [Client API](client-api.md)
- [Workflow Steps](workflow-steps.md)
- [Built-in Workflows](built-in-workflows.md)
