# Firebase Plugin

The Firebase plugin reads and writes Firebase Remote Config: it lists a project's
parameters and conditions, changes one parameter's value, and applies the same change
across several projects.

It exposes:

- a public `FirebaseClient`
- reusable workflow steps for reading, writing, and multi-project fan-out
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

The plugin has no credential fields, and no notion of a brand, a project naming pattern, or
an environment map. It is generic: it speaks about Firebase projects, and a project ID is
either configured as the default or passed in.

```toml
[plugins.firebase]
enabled = true

[plugins.firebase.config]
default_project = "my-firebase-project"
```

That is also the only field the configuration wizard asks for. The rest have working
defaults and are set by hand in `.titan/config.toml` when someone actually needs them:

| Option | Default | What it does |
|--------|---------|--------------|
| `quota_project_id` | the credential's own quota project, else the project being read | Which project is billed for API quota. Override it when your account lacks `serviceusage.services.use` on the Firebase project itself. Titan applies it to the credential, because `google.auth` overwrites the `x-goog-user-project` header with the credential's value on every request. |
| `api_base_url` | `https://firebaseremoteconfig.googleapis.com/v1` | Remote Config REST base URL. |
| `request_timeout` | `30` | HTTP timeout in seconds. |
| `oauth_scopes` | `["https://www.googleapis.com/auth/cloud-platform"]` | Scopes requested from ADC. |

## Working with several projects

One Firebase project per brand, per team, or per environment is a naming scheme that belongs
to the repository that has it — not to Firebase, and not here. So the multi-project steps
take the project list from workflow data rather than from configuration:

- `firebase_project_ids` — the projects to act on, published by an earlier step (or passed
  to the built-in workflow as the `project_ids` param, comma-separated).
- `firebase_project_labels` — optional `project_id -> label`, so tables and prompts can show
  your own vocabulary while this plugin stays unaware of what the names mean.

A plugin that owns such a mapping resolves it and publishes the result:

```python
return Success(
    "Projects resolved",
    metadata={
        "firebase_project_ids": ["mm-firebase-yoigo", "mm-guuk-firebase-prod"],
        "firebase_project_labels": {"mm-guuk-firebase-prod": "guuk"},
    },
)
```

Workflows can use steps from any installed plugin, so that step chains directly with
`firebase_remoteconfig_fanout_plan` and `firebase_remoteconfig_fanout_publish`.

## Environments are conditions

Remote Config has no environment concept of its own. What a project has is
**conditions** — named expressions such as `Android - Production` — and each parameter can
carry a value per condition on top of its default value. The plugin reads the conditions
from the template rather than taking a configured list, so what you can target is always
what the project actually declares.

A write can target **several of them at once** — the default value, a set of conditions, or
both. Because a publish replaces the whole template, all of those targets land in a single
Remote Config version rather than one version each.

Separate environments (dev, pre, pro) are therefore separate Firebase projects, and which
ones exist is the caller's knowledge, not this plugin's — see "Working with several
projects" above.

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
