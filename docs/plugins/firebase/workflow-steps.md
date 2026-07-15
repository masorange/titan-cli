# Firebase Workflow Steps

Firebase exposes authentication and read-only Remote Config steps through
`FirebasePlugin.get_steps()`.

For full contract details for every public step, including documented inputs,
outputs, and return behavior, see the [detailed step reference](../generated/firebase-step-reference.md).

## Authentication

- `firebase_login`: validate that the current user has a Google Cloud ADC
  session and show the ADC login command when it is missing.
- `firebase_status`: report the current Firebase ADC authentication status.

## Remote Config

- `firebase_remoteconfig_get`: read one project's Remote Config template,
  storing the template JSON, version payload, and ETag for later steps.

<!-- BEGIN GENERATED STEP CONTRACTS -->
## Detailed Step Contracts

The summaries above show what each firebase step is for. The sections below show the documented contract for each public step: what it expects from `ctx.data`, what it saves back, and what result types it may return.

Expand a step to see its workflow usage, required context, inputs, outputs, and result behavior.

How to read these contracts:

- `Inputs (from ctx.data)` = values the step expects before it runs.
- `Outputs (saved to ctx.data)` = metadata keys saved for later steps when the step returns `Success` or `Skip`.
- `Returns` = the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate payload.

### Authentication

??? info "`firebase_login`"
    Validate that the current user has a Firebase ADC session.

    **Workflow usage**

    ```yaml
    - plugin: firebase
      step: firebase_login
    ```

    **Available to later steps:** `firebase_account`, `firebase_login_command`

    **Requires**

    | Name | Type | Description |
    |------|------|-------------|
    | `ctx.firebase` | - | An initialized FirebaseClient. |

    **Inputs (from ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `fail_on_missing_auth` | bool, optional | Return Error when ADC is missing. Defaults to True. |

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_account` | Optional[str] | Active gcloud account reported by `gcloud auth list`. |
    | `firebase_login_command` | str | Command the user can run to create an ADC session. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `firebase_account`, `firebase_login_command` | If gcloud ADC is available. |
    | `Error` | - | If Firebase client or ADC auth is missing and fail_on_missing_auth is True. |
    | `Skip` | `firebase_account`, `firebase_login_command` | If ADC auth is missing and fail_on_missing_auth is False. |


??? info "`firebase_status`"
    Report the current Firebase ADC authentication status.

    **Workflow usage**

    ```yaml
    - plugin: firebase
      step: firebase_status
    ```

    **Available to later steps:** `firebase_account`, `firebase_login_command`

    **Requires**

    | Name | Type | Description |
    |------|------|-------------|
    | `ctx.firebase` | - | An initialized FirebaseClient. |

    **Inputs (from ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `fail_on_missing_auth` | bool, optional | Return Error when ADC is missing. Defaults to True. |

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_account` | Optional[str] | Active gcloud account reported by `gcloud auth list`. |
    | `firebase_login_command` | str | Command the user can run to create an ADC session. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `firebase_account`, `firebase_login_command` | If gcloud ADC is available. |
    | `Error` | - | If Firebase client or ADC auth is missing and fail_on_missing_auth is True. |
    | `Skip` | `firebase_account`, `firebase_login_command` | If ADC auth is missing and fail_on_missing_auth is False. |


### Remote Config

??? info "`firebase_remoteconfig_get`"
    Read a Firebase Remote Config template for one project.

    **Workflow usage**

    ```yaml
    - plugin: firebase
      step: firebase_remoteconfig_get
    ```

    **Available to later steps:** `firebase_project_id`, `firebase_remoteconfig_template`, `firebase_remoteconfig_etag`, `firebase_remoteconfig_version`

    **Requires**

    | Name | Type | Description |
    |------|------|-------------|
    | `ctx.firebase` | - | An initialized FirebaseClient. |

    **Inputs (from ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `project_id` | str, optional | Firebase project ID to read. |
    | `firebase_project_id` | str, optional | Alternate project ID key from a previous step. |

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_project_id` | str | Firebase project ID used for the request. |
    | `firebase_remoteconfig_template` | dict | Remote Config template JSON payload. |
    | `firebase_remoteconfig_etag` | Optional[str] | ETag returned by Firebase for later publishing. |
    | `firebase_remoteconfig_version` | Optional[dict] | Remote Config template version payload. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `firebase_project_id`, `firebase_remoteconfig_template`, `firebase_remoteconfig_etag`, `firebase_remoteconfig_version` | If the Remote Config template is read successfully. |
    | `Error` | - | If Firebase is unavailable, no project ID is provided, or the API request fails. |
<!-- END GENERATED STEP CONTRACTS -->
