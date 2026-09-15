# Firebase Workflow Steps

The Firebase plugin exposes public reusable workflow steps through
`FirebasePlugin.get_steps()`. The surface covers credential checks, project selection,
reading a Remote Config template, and writing one parameter — in a single project or across
several.

For full contract details for every public step, including documented inputs, outputs,
and return behavior, see the [detailed step reference](../generated/firebase-step-reference.md).

## Functional groups

- [Authentication](#authentication)
- [Project Selection](#project-selection)
- [Reading Remote Config](#reading-remote-config)
- [Writing One Project](#writing-one-project)
- [Writing Several Projects](#writing-several-projects)

## Summary

| Step | Group | Used by built-in workflows |
|------|-------|----------------------------|
| `firebase_auth_check` | Authentication | `read-remoteconfig`, `set-remoteconfig-value`, `set-remoteconfig-value-multiproject` |
| `firebase_select_target` | Project Selection | `read-remoteconfig`, `set-remoteconfig-value` |
| `firebase_select_targets` | Project Selection | `set-remoteconfig-value-multiproject` |
| `firebase_remoteconfig_get` | Reading Remote Config | `read-remoteconfig`, `set-remoteconfig-value` |
| `firebase_remoteconfig_conditions` | Reading Remote Config | `read-remoteconfig`, `set-remoteconfig-value` |
| `firebase_remoteconfig_select_key` | Reading Remote Config | `read-remoteconfig`, `set-remoteconfig-value` |
| `firebase_remoteconfig_set_value` | Writing One Project | `set-remoteconfig-value` |
| `firebase_remoteconfig_diff` | Writing One Project | `set-remoteconfig-value` |
| `firebase_remoteconfig_publish` | Writing One Project | `set-remoteconfig-value` |
| `firebase_remoteconfig_fanout_plan` | Writing Several Projects | `set-remoteconfig-value-multiproject` |
| `firebase_remoteconfig_fanout_publish` | Writing Several Projects | `set-remoteconfig-value-multiproject` |

## Authentication

Use this step before anything that touches Firebase, so a missing or expired ADC session
fails at the start rather than mid-write.

- `firebase_auth_check`: resolve Application Default Credentials, report which kind of
  credential is active, and warn when it is a service account — which would attribute
  every publish to itself instead of to the person running the workflow

## Project Selection

These steps do not map names to projects: a project ID is passed in or configured. A
repository whose projects follow a naming scheme of its own resolves that itself and feeds
the result in.

- `firebase_select_target`: resolve one project from `project_id` or `default_project`,
  keeping an optional `project_label` for display
- `firebase_select_targets`: normalize a caller-supplied list — `project_ids` as a workflow
  param, or `firebase_project_ids` published by an earlier step — applying any
  `firebase_project_labels`, preserving order and dropping duplicates

## Reading Remote Config

Use these steps to read a template and navigate it.

- `firebase_remoteconfig_get`: read the active template, publishing its ETag and the
  version metadata (including who last published it)
- `firebase_remoteconfig_conditions`: list the template's conditions and choose the write
  target — the parameter's default value, or one condition
- `firebase_remoteconfig_select_key`: browse the parameters with their current value for
  the chosen target, filtering by text when the project has many

## Writing One Project

Use these steps to change one parameter in one project. The order is the safety property:
the value is validated, then shown, then published only after an explicit confirmation.

- `firebase_remoteconfig_set_value`: ask for the new value in the shape its type calls for
  (buttons for a boolean, a multiline editor for JSON) and validate it against the live
  template
- `firebase_remoteconfig_diff`: show before and after, and require a confirmation that
  defaults to no. Exits the workflow when the change is a no-op or the user declines
- `firebase_remoteconfig_publish`: validate with Firebase (`validate_only`), then publish,
  reporting the new version number and the author Firebase recorded

## Writing Several Projects

Use these steps to apply one change to several projects. Every project has its own
template, so each is validated separately and reported separately.

- `firebase_remoteconfig_fanout_plan`: validate the change against every target, show a
  plan table (ready / no change / error), and confirm project by project through a
  multi-select with nothing preselected
- `firebase_remoteconfig_fanout_publish`: publish one project at a time, capturing failures
  so one project's rejection does not lose the others, and report every outcome

## Notes

- Publishing replaces the whole Remote Config template, so every write here is a
  read-modify-write guarded by the ETag of the read that preceded it. `If-Match` is never
  `*`.
- `firebase_remoteconfig_publish` refuses to publish without the confirmation that
  `firebase_remoteconfig_diff` produces. Pass `dry_run` to validate without publishing.
- The multi-project workflow declares `key`, `value`, `condition` and `project_ids` as
  optional params; an empty value means "ask me", and the prompts are built from the first
  target's template.

<!-- BEGIN GENERATED STEP CONTRACTS -->
## Detailed Step Contracts

The summaries above show what each firebase step is for. The sections below show the documented contract for each public step: what it expects from `ctx.data`, what it saves back, and what result types it may return.

Expand a step to see its workflow usage, required context, inputs, outputs, and result behavior.

How to read these contracts:

- `Inputs (from ctx.data)` = values the step expects before it runs.
- `Outputs (saved to ctx.data)` = metadata keys saved for later steps when the step returns `Success` or `Skip`.
- `Returns` = the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate payload.

### Authentication

??? info "`firebase_auth_check`"
    Check that Google Application Default Credentials are usable.

    **Workflow usage**

    ```yaml
    - plugin: firebase
      step: firebase_auth_check
    ```

    **Used by built-in workflows:** `read-remoteconfig`, `set-remoteconfig-value`, `set-remoteconfig-value-multiproject`

    **Available to later steps:** `firebase_account`, `firebase_credential_kind`, `firebase_credential_is_user`

    **Requires**

    | Name | Type | Description |
    |------|------|-------------|
    | `ctx.firebase` | - | An initialized FirebaseClient. |

    **Inputs (from ctx.data)**

    None documented.

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_account` | Optional[str] | Service account email, when applicable. |
    | `firebase_credential_kind` | str | user, service_account, impersonated, ... |
    | `firebase_credential_is_user` | bool | Whether publishes get a real author. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `firebase_account`, `firebase_credential_kind`, `firebase_credential_is_user` | If credentials resolve and can mint a token. |
    | `Error` | - | If no ADC session exists or it cannot be refreshed. |


### Project Selection

??? info "`firebase_select_target`"
    Resolve the Firebase project to work on.

    **Workflow usage**

    ```yaml
    - plugin: firebase
      step: firebase_select_target
    ```

    **Used by built-in workflows:** `read-remoteconfig`, `set-remoteconfig-value`

    **Available to later steps:** `firebase_project_id`, `firebase_target_label`

    **Inputs (from ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `project_id` | str, optional | Firebase project ID to use. |
    | `project_label` | str, optional | Friendlier name to show for it. |

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_project_id` | str | Resolved project ID. |
    | `firebase_target_label` | str | User-facing reference for the target. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `firebase_project_id`, `firebase_target_label` | If a project could be resolved. |
    | `Error` | - | If the plugin is unavailable or nothing names a project. |


??? info "`firebase_select_targets`"
    Resolve several Firebase projects from a caller-supplied list.

    **Workflow usage**

    ```yaml
    - plugin: firebase
      step: firebase_select_targets
    ```

    **Used by built-in workflows:** `set-remoteconfig-value-multiproject`

    **Available to later steps:** `firebase_targets`, `firebase_project_ids`

    **Inputs (from ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `project_ids` | list or str, optional | Projects to target; a comma- or space-separated string is accepted. |
    | `firebase_project_ids` | list or str, optional | Same, as published by an earlier step. |
    | `firebase_project_labels` | dict, optional | project_id to label, shown instead of the raw ID. |

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_targets` | list[FirebaseProjectTarget] | Resolved targets. |
    | `firebase_project_ids` | list[str] | Normalized, de-duplicated project IDs. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `firebase_targets`, `firebase_project_ids` | If at least one project was named. |
    | `Error` | - | If the plugin is unavailable or the list is empty. |


### Reading Remote Config

??? info "`firebase_remoteconfig_get`"
    Read the active Remote Config template for one project.

    **Workflow usage**

    ```yaml
    - plugin: firebase
      step: firebase_remoteconfig_get
    ```

    **Used by built-in workflows:** `read-remoteconfig`, `set-remoteconfig-value`

    **Available to later steps:** `firebase_project_id`, `firebase_remoteconfig_etag`, `firebase_remoteconfig_version`, `firebase_remoteconfig_template`

    **Requires**

    | Name | Type | Description |
    |------|------|-------------|
    | `ctx.firebase` | - | An initialized FirebaseClient. |

    **Inputs (from ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_project_id` | str | Project to read, from firebase_select_target. |
    | `project_id` | str, optional | Alternative key for the same thing. |

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_project_id` | str | Project that was read. |
    | `firebase_remoteconfig_etag` | Optional[str] | ETag needed to publish over it. |
    | `firebase_remoteconfig_version` | Optional[str] | Active version number. |
    | `firebase_remoteconfig_template` | UIRemoteConfigTemplate | The template. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `firebase_project_id`, `firebase_remoteconfig_etag`, `firebase_remoteconfig_version`, `firebase_remoteconfig_template` | If the template is read. |
    | `Error` | - | If Firebase is unavailable, no project is given, or the read fails. |


??? info "`firebase_remoteconfig_conditions`"
    Show the template's conditions and choose which value a write targets.

    **Workflow usage**

    ```yaml
    - plugin: firebase
      step: firebase_remoteconfig_conditions
    ```

    **Used by built-in workflows:** `read-remoteconfig`, `set-remoteconfig-value`

    **Available to later steps:** `firebase_condition`, `firebase_condition_label`

    **Requires**

    | Name | Type | Description |
    |------|------|-------------|
    | `ctx.firebase` | - | An initialized FirebaseClient. |

    **Inputs (from ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_remoteconfig_template` | UIRemoteConfigTemplate | From firebase_remoteconfig_get. |
    | `condition` | str, optional | Preselected condition name, or "default". |

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_condition` | Optional[str] | Condition name, None for the default. |
    | `firebase_condition_label` | str | User-facing label for the target. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `firebase_condition`, `firebase_condition_label` | If a target is chosen (or only the default exists). |
    | `Error` | - | If the template is missing or the user cancels. |


??? info "`firebase_remoteconfig_select_key`"
    Choose one Remote Config parameter.

    **Workflow usage**

    ```yaml
    - plugin: firebase
      step: firebase_remoteconfig_select_key
    ```

    **Used by built-in workflows:** `read-remoteconfig`, `set-remoteconfig-value`

    **Available to later steps:** `firebase_key`, `firebase_value_type`, `firebase_current_value`

    **Requires**

    | Name | Type | Description |
    |------|------|-------------|
    | `ctx.firebase` | - | An initialized FirebaseClient. |

    **Inputs (from ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_remoteconfig_template` | UIRemoteConfigTemplate | From firebase_remoteconfig_get. |
    | `firebase_condition` | Optional[str] | Write target, from firebase_remoteconfig_conditions. |
    | `key` | str, optional | Preselected parameter key. |

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_key` | str | Selected parameter key. |
    | `firebase_value_type` | str | Effective value type of the parameter. |
    | `firebase_current_value` | Optional[str] | Raw current value, None if unset. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `firebase_key`, `firebase_value_type`, `firebase_current_value` | If a parameter is selected. |
    | `Error` | - | If the template is missing, the key is unknown, or the user cancels. |


### Writing One Project

??? info "`firebase_remoteconfig_set_value`"
    Ask for the new value of the selected parameter and validate it.

    **Workflow usage**

    ```yaml
    - plugin: firebase
      step: firebase_remoteconfig_set_value
    ```

    **Used by built-in workflows:** `set-remoteconfig-value`

    **Available to later steps:** `firebase_change`, `firebase_new_value`

    **Requires**

    | Name | Type | Description |
    |------|------|-------------|
    | `ctx.firebase` | - | An initialized FirebaseClient. |

    **Inputs (from ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_project_id` | str | Target project. |
    | `firebase_key` | str | Parameter to change. |
    | `firebase_condition` | Optional[str] | Condition to write, None for the default. |
    | `firebase_value_type` | Optional[str] | Type reported by the read. |
    | `firebase_current_value` | Optional[str] | Current raw value. |
    | `value` | str, optional | New value, for non-interactive runs. |

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_change` | UIRemoteConfigChange | The validated change. |
    | `firebase_new_value` | str | Exact string that will be stored. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `firebase_change`, `firebase_new_value` | If the value is valid for the parameter type. |
    | `Error` | - | If inputs are missing, the value is invalid, or the user cancels. |


??? info "`firebase_remoteconfig_diff`"
    Render the pending change and ask the user to confirm it.

    **Workflow usage**

    ```yaml
    - plugin: firebase
      step: firebase_remoteconfig_diff
    ```

    **Used by built-in workflows:** `set-remoteconfig-value`

    **Available to later steps:** `firebase_change_confirmed`

    **Requires**

    | Name | Type | Description |
    |------|------|-------------|
    | `ctx.firebase` | - | An initialized FirebaseClient. |

    **Inputs (from ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_change` | UIRemoteConfigChange | From firebase_remoteconfig_set_value. |
    | `firebase_project_id` | str | Target project. |
    | `firebase_target_label` | Optional[str] | Display label for the project. |

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_change_confirmed` | bool | Always True when the step succeeds. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `firebase_change_confirmed` | If the user confirms the change. |
    | `Exit` | - | If the change is a no-op, or the user declines. |
    | `Error` | - | If there is no pending change to show. |


??? info "`firebase_remoteconfig_publish`"
    Publish one confirmed change, validating it with Firebase first.

    **Workflow usage**

    ```yaml
    - plugin: firebase
      step: firebase_remoteconfig_publish
    ```

    **Used by built-in workflows:** `set-remoteconfig-value`

    **Available to later steps:** `firebase_published_version`, `firebase_published_author`, `firebase_publish_result`

    **Requires**

    | Name | Type | Description |
    |------|------|-------------|
    | `ctx.firebase` | - | An initialized FirebaseClient. |

    **Inputs (from ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_project_id` | str | Target project. |
    | `firebase_change` | UIRemoteConfigChange | The change to publish. |
    | `firebase_change_confirmed` | bool | Set by `firebase_remoteconfig_diff`. |
    | `dry_run` | bool, optional | Validate only, publish nothing. |

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_published_version` | Optional[str] | New version number. |
    | `firebase_published_author` | Optional[str] | Author Firebase recorded. |
    | `firebase_publish_result` | UIRemoteConfigPublishResult | Full outcome. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `firebase_published_version`, `firebase_published_author`, `firebase_publish_result` | If Firebase validated (dry run) or published the template. |
    | `Error` | - | If inputs are missing, the change is unconfirmed, or the write fails. |


### Writing Several Projects

??? info "`firebase_remoteconfig_fanout_plan`"
    Build the per-project plan for one parameter change.

    **Workflow usage**

    ```yaml
    - plugin: firebase
      step: firebase_remoteconfig_fanout_plan
    ```

    **Used by built-in workflows:** `set-remoteconfig-value-multiproject`

    **Available to later steps:** `firebase_fanout_plan`, `firebase_fanout_rejected`

    **Requires**

    | Name | Type | Description |
    |------|------|-------------|
    | `ctx.firebase` | - | An initialized FirebaseClient. |

    **Inputs (from ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_targets` | list[FirebaseProjectTarget] | From firebase_select_targets. |
    | `key` | str | Parameter to change. |
    | `value` | str | New value. |
    | `condition` | str, optional | Condition to write instead of the default. |

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_fanout_plan` | list[UIFanoutEntry] | Entries chosen to publish. |
    | `firebase_fanout_rejected` | list[UIFanoutEntry] | Entries left out. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `firebase_fanout_plan`, `firebase_fanout_rejected` | If at least one project is selected for publishing. |
    | `Exit` | - | If no project can take the change, or the user selects none. |
    | `Error` | - | If inputs are missing. |


??? info "`firebase_remoteconfig_fanout_publish`"
    Publish the planned change to each selected project.

    **Workflow usage**

    ```yaml
    - plugin: firebase
      step: firebase_remoteconfig_fanout_publish
    ```

    **Used by built-in workflows:** `set-remoteconfig-value-multiproject`

    **Available to later steps:** `firebase_fanout_outcomes`, `firebase_fanout_published`, `firebase_fanout_failed`

    **Requires**

    | Name | Type | Description |
    |------|------|-------------|
    | `ctx.firebase` | - | An initialized FirebaseClient. |

    **Inputs (from ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_fanout_plan` | list[UIFanoutEntry] | From firebase_remoteconfig_fanout_plan. |
    | `dry_run` | bool, optional | Validate everywhere, publish nothing. |

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `firebase_fanout_outcomes` | list[UIFanoutOutcome] | Per-project results. |
    | `firebase_fanout_published` | int | Projects published. |
    | `firebase_fanout_failed` | int | Projects that failed. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `firebase_fanout_outcomes`, `firebase_fanout_published`, `firebase_fanout_failed` | If at least one project published (or validated in a dry run). |
    | `Error` | - | If the plan is missing or every project failed. |
<!-- END GENERATED STEP CONTRACTS -->
