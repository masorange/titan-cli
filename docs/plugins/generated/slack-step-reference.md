# Slack Step Reference

This page is generated from the public step inventory and shows the documented workflow contract for each public step.

## Validation and Discovery

### `validate_connection`

Validate the configured Slack connection and expose identity metadata.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

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

### `list_public_channels`

List public Slack channels visible to the current token.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

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

### `list_users`

List Slack users visible to the current token.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

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
