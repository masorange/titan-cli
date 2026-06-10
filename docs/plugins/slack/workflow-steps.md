# Slack Workflow Steps

The Slack plugin exposes public reusable workflow steps through `SlackPlugin.get_steps()`. The first Slack step surface is intentionally small and focused on connection validation plus read-only discovery.

For full contract details for every public step, including documented inputs, outputs, and return behavior, see the [detailed step reference](../generated/slack-step-reference.md).

## Functional groups

- [Validation and Discovery](#validation-and-discovery)

## Summary

| Step | Group | Used by built-in workflows |
|------|-------|----------------------------|
| `validate_connection` | Validation and Discovery | `discover-slack-workspace` |
| `list_public_channels` | Validation and Discovery | `discover-slack-workspace` |
| `list_users` | Validation and Discovery | `discover-slack-workspace` |

## Validation and Discovery

Use these steps to validate the current Slack connection and inspect the accessible workspace surface.

- `validate_connection`: validate the configured Slack token and expose identity metadata
- `list_public_channels`: list public channels visible to the current token
- `list_users`: list users visible to the current token

## Detailed Step Contracts

The summaries above show what each slack step is for. The sections below show the documented contract for each public step: what it expects from `ctx.data`, what it saves back, and what result types it may return.

How to read these contracts:

- `Inputs (from ctx.data)` = values the step expects before it runs.
- `Outputs (saved to ctx.data)` = metadata keys saved for later steps when the step returns `Success` or `Skip`.
- `Returns` = the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate payload.

### Validation and Discovery

??? info "`validate_connection`"
    Validate the configured Slack connection and expose identity metadata.

    **Workflow usage**

    ```yaml
    - plugin: slack
      step: validate_connection
    ```

    **Used by built-in workflows:** `discover-slack-workspace`

    **Available to later steps:** `slack_auth`, `slack_team_id`, `slack_team_name`, `slack_user_id`

    **Requires**

    | Name | Type | Description |
    |------|------|-------------|
    | `ctx.slack` | - | An initialized SlackClient. |

    **Inputs (from ctx.data)**

    None documented.

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `slack_auth` | dict | Slack auth identity details from `auth_test()`. |
    | `slack_team_id` | str \| None | Team identifier reported by Slack. |
    | `slack_team_name` | str \| None | Team name reported by Slack. |
    | `slack_user_id` | str \| None | User identifier reported by Slack. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `slack_auth`, `slack_team_id`, `slack_team_name`, `slack_user_id` | If the Slack connection validates successfully. |
    | `Error` | - | If the Slack client is not available or the auth request fails. |

??? info "`list_public_channels`"
    List public Slack channels visible to the current token.

    **Workflow usage**

    ```yaml
    - plugin: slack
      step: list_public_channels
    ```

    **Used by built-in workflows:** `discover-slack-workspace`

    **Available to later steps:** `slack_channels`, `slack_channels_next_cursor`

    **Requires**

    | Name | Type | Description |
    |------|------|-------------|
    | `ctx.slack` | - | An initialized SlackClient. |

    **Inputs (from ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `slack_limit` | int, optional | Maximum number of channels to request. Defaults to 100. |
    | `slack_cursor` | str, optional | Pagination cursor for the next page. |
    | `slack_exclude_archived` | bool, optional | Whether to exclude archived channels. Defaults to True. |

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `slack_channels` | list[NetworkSlackChannel] | Public channels returned by Slack. |
    | `slack_channels_next_cursor` | str \| None | Pagination cursor for a later request. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `slack_channels`, `slack_channels_next_cursor` | If the channel list is retrieved successfully. |
    | `Error` | - | If the Slack client is not available or the Slack request fails. |

??? info "`list_users`"
    List Slack users visible to the current token.

    **Workflow usage**

    ```yaml
    - plugin: slack
      step: list_users
    ```

    **Used by built-in workflows:** `discover-slack-workspace`

    **Available to later steps:** `slack_users`, `slack_users_next_cursor`

    **Requires**

    | Name | Type | Description |
    |------|------|-------------|
    | `ctx.slack` | - | An initialized SlackClient. |

    **Inputs (from ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `slack_limit` | int, optional | Maximum number of users to request. Defaults to 100. |
    | `slack_cursor` | str, optional | Pagination cursor for the next page. |

    **Outputs (saved to ctx.data)**

    | Name | Type | Description |
    |------|------|-------------|
    | `slack_users` | list[NetworkSlackUser] | Users returned by Slack. |
    | `slack_users_next_cursor` | str \| None | Pagination cursor for a later request. |

    **Returns**

    | Result | Saved for later steps | Description |
    |--------|-----------------------|-------------|
    | `Success` | `slack_users`, `slack_users_next_cursor` | If the user list is retrieved successfully. |
    | `Error` | - | If the Slack client is not available or the Slack request fails. |
