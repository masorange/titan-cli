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

## Selection and Target Resolution

### `select_user_target`

Filter visible Slack users by query and select one canonical user target.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: slack
  step: select_user_target
```

**Available to later steps:** `slack_target`, `slack_target_type`, `slack_target_id`, `slack_target_name`, `slack_target_query`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.slack` | - | An initialized SlackClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `slack_users` | list[UISlackUser] | Users visible to the current Slack token. |
| `slack_target_query` | str, optional | Pre-filled query used to filter Slack users. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `slack_target` | UISlackTarget | Canonical selected Slack target. |
| `slack_target_type` | str | Selected target type (`user`). |
| `slack_target_id` | str | Slack user ID. |
| `slack_target_name` | str | User-facing target name. |
| `slack_target_query` | str | Query used to resolve the selection. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `slack_target`, `slack_target_type`, `slack_target_id`, `slack_target_name`, `slack_target_query` | If the user target is selected successfully. |
| `Error` | - | If Slack is unavailable, no users are available, the query is invalid, or no match is selected. |

### `select_channel_target`

Filter visible Slack channels by query and select one canonical channel target.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: slack
  step: select_channel_target
```

**Available to later steps:** `slack_target`, `slack_target_type`, `slack_target_id`, `slack_target_name`, `slack_target_query`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.slack` | - | An initialized SlackClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `slack_channels` | list[UISlackChannel] | Public channels visible to the current Slack token. |
| `slack_target_query` | str, optional | Pre-filled query used to filter Slack channels. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `slack_target` | UISlackTarget | Canonical selected Slack target. |
| `slack_target_type` | str | Selected target type (`channel`). |
| `slack_target_id` | str | Slack channel ID. |
| `slack_target_name` | str | User-facing target name. |
| `slack_target_query` | str | Query used to resolve the selection. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `slack_target`, `slack_target_type`, `slack_target_id`, `slack_target_name`, `slack_target_query` | If the channel target is selected successfully. |
| `Error` | - | If Slack is unavailable, no channels are available, the query is invalid, or no match is selected. |

## Messaging

### `open_direct_message`

Open or reuse a direct message conversation for the selected user target.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: slack
  step: open_direct_message
```

**Used by built-in workflows:** `send-slack-direct-message`

**Available to later steps:** `slack_conversation`, `slack_conversation_id`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.slack` | - | An initialized SlackClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `slack_target` | UISlackTarget | Selected Slack target. Must be a `user` target. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `slack_conversation` | UISlackConversation | Opened or reused Slack conversation. |
| `slack_conversation_id` | str | Conversation ID used for later message operations. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `slack_conversation`, `slack_conversation_id` | If the direct message conversation is ready. |
| `Error` | - | If Slack is unavailable, the target is missing or invalid, or the Slack request fails. |

### `prompt_message_body`

Capture a multiline Slack message body for later posting.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: slack
  step: prompt_message_body
```

**Used by built-in workflows:** `send-slack-direct-message`

**Available to later steps:** `slack_message_text`

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `slack_message_text` | str, optional | Pre-filled message text. If already present, the prompt is skipped. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `slack_message_text` | str | Message text to post later. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `slack_message_text` | If the message body is captured successfully. |
| `Skip` | `slack_message_text` | If the message body already exists in context. |
| `Error` | - | If the user cancels or the message body is empty. |

### `post_message`

Post the prepared message to the selected Slack conversation.

**How to read this contract**

- `Inputs (from ctx.data)` shows what the step expects before it runs.
- `Outputs (saved to ctx.data)` shows the metadata keys later steps can read after `Success` or `Skip`.
- `Returns` describes the workflow result type (`Success`, `Skip`, `Error`, `Exit`), not a separate function return payload.

**Workflow usage**

```yaml
- plugin: slack
  step: post_message
```

**Used by built-in workflows:** `send-slack-direct-message`

**Available to later steps:** `slack_message`, `slack_message_ts`, `slack_message_channel`

**Requires**

| Name | Type | Description |
|------|------|-------------|
| `ctx.slack` | - | An initialized SlackClient. |

**Inputs (from ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `slack_conversation_id` | str | Slack conversation ID to post into. |
| `slack_message_text` | str | Message body to post. |
| `slack_thread_ts` | str, optional | Thread timestamp for replies. |

**Outputs (saved to ctx.data)**

| Name | Type | Description |
|------|------|-------------|
| `slack_message` | UISlackPostedMessage | Posted Slack message metadata. |
| `slack_message_ts` | str | Timestamp of the posted message. |
| `slack_message_channel` | str | Channel or conversation ID where the message was posted. |

**Returns**

| Result | Saved for later steps | Description |
|--------|-----------------------|-------------|
| `Success` | `slack_message`, `slack_message_ts`, `slack_message_channel` | If the Slack message is posted successfully. |
| `Error` | - | If Slack is unavailable, required context is missing, or the Slack request fails. |
