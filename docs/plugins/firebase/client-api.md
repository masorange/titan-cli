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

**Returns:** `ClientResult[UIAdcIdentity]` — `account`, `credential_kind`
(`user`, `service_account`, `impersonated`, ...), `quota_project_id`, and
`is_user_credential`. `ClientError` with code `ADC_UNAVAILABLE` when there is no usable
session; its `details["login_command"]` carries the command that creates one.

### `uses_service_account_env_var()`

Whether `GOOGLE_APPLICATION_CREDENTIALS` is set, which would make a service account —
not the person running the workflow — the author of every publish.

**Parameters:**

- No parameters.

**Returns:** `bool`.

---

## Reading

### `get_remote_config(project_id)`

Read the active Remote Config template for one project.

**Call:**

```python
client.get_remote_config("mm-firebase-yoigo")
```

**Parameters:**

- `project_id`: Required Firebase project ID.

**Returns:** `ClientResult[UIRemoteConfigTemplate]` — parameters sorted by key (each with
its effective type, default value and conditional values), the template's conditions, its
parameter group names, the active version metadata, and the `etag` a publish needs.

**Error codes:** `AUTH_REJECTED` (401), `PERMISSION_DENIED` (403), `NOT_FOUND` (404),
`ETAG_CONFLICT` (409), `BAD_REQUEST` (400), `API_ERROR`, `ADC_UNAVAILABLE`.

---

## Writing

### `validate_remote_config_change(project_id, key, new_value, condition=None)`

Check one parameter edit against the live template without publishing anything.

**Call:**

```python
client.validate_remote_config_change(
    "mm-firebase-yoigo",
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

**Error codes:** `TEMPLATE_EDIT_ERROR` (unknown parameter or condition), `INVALID_VALUE`
(value does not match the type), plus the read error codes above.

### `publish_remote_config_change(project_id, change, validate_only=False)`

Apply one change to the template and publish it.

**Call:**

```python
client.publish_remote_config_change(
    "mm-firebase-yoigo",
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
between read and write), plus the read error codes above.
