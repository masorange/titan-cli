# Slack Workflow Steps

The Slack plugin exposes public reusable workflow steps through `SlackPlugin.get_steps()`. The first Slack step surface is intentionally small and focused on connection validation plus read-only discovery.

For full contract details for every public step, including documented inputs, outputs, and return behavior, see the [detailed step reference](../generated/slack-step-reference.md).

## Functional groups

- [Validation and Discovery](#validation-and-discovery)
- [Selection and Target Resolution](#selection-and-target-resolution)
- [Messaging](#messaging)

## Summary

| Step | Group | Used by built-in workflows |
|------|-------|----------------------------|
| `validate_connection` | Validation and Discovery | `discover-slack-workspace` |
| `list_public_channels` | Validation and Discovery | `discover-slack-workspace` |
| `list_users` | Validation and Discovery | `discover-slack-workspace` |
| `select_user_target` | Selection and Target Resolution | - |
| `select_channel_target` | Selection and Target Resolution | - |
| `open_direct_message` | Messaging | `send-slack-direct-message` |
| `prompt_message_body` | Messaging | `send-slack-direct-message` |
| `post_message` | Messaging | `send-slack-direct-message` |

## Validation and Discovery

Use these steps to validate the current Slack connection and inspect the accessible workspace surface.

- `validate_connection`: validate the configured Slack token and expose identity metadata
- `list_public_channels`: list public channels visible to the current token
- `list_users`: list users visible to the current token

## Selection and Target Resolution

Use these steps to resolve a reusable Slack target object for later workflows.

- `select_user_target`: filter visible Slack users by query and select one canonical user target
- `select_channel_target`: filter visible Slack channels by query and select one canonical channel target

## Messaging

Use these steps to open a direct message conversation and post a plain-text Slack message.

- `open_direct_message`: open or reuse a direct message conversation for the selected user target
- `prompt_message_body`: capture a multiline Slack message body for later posting
- `post_message`: post the prepared message to the selected conversation
