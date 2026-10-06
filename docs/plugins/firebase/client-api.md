# Firebase Client API

The Firebase plugin exposes Remote Config through `FirebaseClient`. Every method returns
a `ClientResult` — `ClientSuccess` with a UI model, or `ClientError` with an actionable
message — so callers never handle exceptions.

## Requirements

To use the Firebase client in Titan code:

- enable the `firebase` plugin
- have an Application Default Credentials session (`gcloud auth application-default login`)

There is no credential to configure or store: see [Overview](overview.md#authentication).

---

## Accessing the client

```python
firebase_plugin = config.registry.get_plugin("firebase")
client = firebase_plugin.get_client()
```

Building the client does no I/O. Credentials are resolved on the first network call, so
enabling the plugin never blocks on gcloud.

---

## Authentication

### `check_auth()`

Resolve Application Default Credentials and report the identity that will own any change.

**Call:**

```python
client.check_auth()
```

**Parameters:**

- No parameters.

**Returns:** `ClientResult[UIAdcIdentity]` — `credential_kind` (`user`,
`service_account`, `impersonated`, ...), `is_user_credential`, `quota_project_id`, and
`account`, which holds a service account's own email and is `None` for user credentials.
`ClientError` with code `ADC_UNAVAILABLE` when there is no usable session; its
`details["login_command"]` carries the command that creates one.

Titan does not resolve the signed-in user's email: an ADC session minted for
`cloud-platform` need not carry the `userinfo.email` scope, and the endpoint that would
answer also rejects the credential's quota project. The authoritative author is the one
Firebase records on the published version, which `publish_remote_config_change` reports.
This call makes no network request beyond refreshing the token.

### `uses_service_account_env_var()`

Whether `GOOGLE_APPLICATION_CREDENTIALS` is set, which would make a service account —
not the person running the workflow — the author of every publish.

**Parameters:**

- No parameters.

**Returns:** `bool`.

---

## Reading

### `list_projects()`

List Firebase projects available to the active Google credentials.

**Call:**

```python
client.list_projects()
```

**Parameters:**

- No parameters.

**Returns:** `ClientResult[list[UIFirebaseProject]]` — each project includes
`project_id`, `display_name`, `name`, and `project_number`. The list comes from Firebase
Management, so it contains Firebase projects rather than generic Google Cloud projects.

**Error codes:** `AUTH_REJECTED` (401), `PERMISSION_DENIED` (403), `API_ERROR`,
`ADC_UNAVAILABLE`.

### `get_remote_config(project_id)`

Read the active Remote Config template for one project.

**Call:**

```python
client.get_remote_config("my-firebase-project")
```

**Parameters:**

- `project_id`: Required Firebase project ID.

**Returns:** `ClientResult[UIRemoteConfigTemplate]` — parameters sorted by key (each with
its effective `RemoteConfigValueType`, default value and conditional values), the
template's conditions, its parameter group names, the active version metadata, and the
`etag` a publish needs.

**Error codes:** `AUTH_REJECTED` (401), `PERMISSION_DENIED` (403), `NOT_FOUND` (404),
`ETAG_CONFLICT` (409), `BAD_REQUEST` (400), `API_ERROR`, `ADC_UNAVAILABLE`.

---

## Writing

### `validate_remote_config_change(project_id, key, new_value, condition=None)`

Check one parameter edit against the live template without publishing anything.

**Call:**

```python
client.validate_remote_config_change(
    "my-firebase-project",
    "feature_enabled",
    "true",
    "android_prod",
)
```

**Parameters:**

- `project_id`: Required Firebase project ID.
- `key`: Required parameter key. Must already exist in the template.
- `new_value`: Required new value, as text. It is validated against the parameter's
  effective type and normalized (booleans to `true`/`false`, JSON compacted).
- `condition`: Optional condition name to write instead of the default value. It must
  already exist in the template.

**Returns:** `ClientResult[UIRemoteConfigChange]` — the value it would replace, the value
it would store, whether the condition was inheriting the default, and `is_noop`.

**Error codes:** `TEMPLATE_EDIT_ERROR` (unknown parameter or condition, or the target
value is managed by Firebase personalization, experiments, rollouts, or an unknown future
value-source field), `INVALID_VALUE` (value does not match the type), plus the read error
codes above.

### `publish_remote_config_change(project_id, change, validate_only=False)`

Apply one change to the template and publish it.

**Call:**

```python
client.publish_remote_config_change(
    "my-firebase-project",
    change,
    validate_only=True,
)
```

**Parameters:**

- `project_id`: Required Firebase project ID.
- `change`: Required `UIRemoteConfigChange`, normally from
  `validate_remote_config_change`.
- `validate_only`: Optional. When true, Firebase checks the payload and nothing is
  published.

**Behavior:** reads the template immediately before writing, so the ETag is fresh; sends
it as `If-Match`; and on a 409 re-reads and reapplies the change once. A second conflict
is reported rather than retried. The published version carries a description naming the
key, the target, and the value before and after.

**Returns:** `ClientResult[UIRemoteConfigPublishResult]` — the new `etag`, the version
Firebase created (number, author email, origin, type), whether a conflict forced a retry,
and the change that was applied.

**Error codes:** `MISSING_ETAG` (the read returned none, so publishing would risk
overwriting another edit), `TEMPLATE_EDIT_ERROR` (the parameter or condition disappeared
between read and write, or the live value is no longer a literal/editable value), plus the
read error codes above.

### `create_remote_config_key(project_id, request, validate_only=False)`

Create one missing Remote Config parameter in a project from typed input.

**Call:**

```python
client.create_remote_config_key(
    "my-firebase-project",
    UIRemoteConfigKeyCreateRequest(
        key="new_checkout_enabled",
        value_type=RemoteConfigValueType.BOOLEAN,
        default_raw_value="true",
        conditional_raw_values={"android_prod": "false"},
        description="Controls the new checkout",
    ),
    validate_only=True,
)
```

**Parameters:**

- `project_id`: Required Firebase project ID.
- `request`: Required `UIRemoteConfigKeyCreateRequest`, including the new key, declared
  `RemoteConfigValueType`, default value, optional condition values and optional
  description.
- `validate_only`: Optional. When true, Firebase checks the target payload and nothing is
  published.

**Behavior:** reads the target template and its ETag, builds a new parameter payload,
adds it only if the key does not already exist, then validates or publishes the whole
template with `If-Match`. On an ETag conflict it re-reads and retries once. Condition
values must reference conditions that already exist in the target template.

**Returns:** `ClientResult[UIRemoteConfigKeyCreateResult]` — target project, key, declared
type, new `etag`, version metadata, whether the request was validate-only, and whether a
conflict forced a retry.

**Error codes:** `MISSING_ETAG`, `TEMPLATE_EDIT_ERROR` (existing key, malformed template,
or missing target conditions), `INVALID_VALUE`, plus the read and publish error codes
above.

### `copy_remote_config_key(source_project_id, target_project_id, key, validate_only=False)`

Copy one missing Remote Config parameter from a source project to a target project.

**Call:**

```python
client.copy_remote_config_key(
    "my-source-firebase-project",
    "my-target-firebase-project",
    "new_checkout_enabled",
    validate_only=True,
)
```

**Parameters:**

- `source_project_id`: Required Firebase project ID that already contains the key.
- `target_project_id`: Required Firebase project ID where the key should be created.
- `key`: Required parameter key. It must exist in the source template and must not already
  exist in the target template.
- `validate_only`: Optional. When true, Firebase checks the target payload and nothing is
  published.

**Behavior:** reads the source template, reads the target template and its ETag, adds the
source parameter payload to the target without overwriting existing keys, then validates or
publishes the whole target template with `If-Match`. On a target ETag conflict it re-reads
and retries once. If the copied parameter references conditional values, every referenced
condition must already exist in the target template. Parameters containing Firebase-managed
`personalizationValue`, `experimentValue`, `rolloutValue`, or unknown future value-source
fields are not copied by this generic operation.

**Returns:** `ClientResult[UIRemoteConfigKeyCopyResult]` — source project, target project,
key, effective `RemoteConfigValueType`, its Titan display label, new `etag`, version
metadata, and whether a conflict forced a retry.

**Error codes:** `MISSING_ETAG`, `TEMPLATE_EDIT_ERROR` (missing source key, existing target
key, malformed payload, or missing target conditions), plus the read and publish error codes
above.
