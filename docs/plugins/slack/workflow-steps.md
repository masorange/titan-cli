# Slack Workflow Steps

The Slack plugin exposes public reusable workflow steps through `SlackPlugin.get_steps()`. The current step surface stays intentionally small, but now covers connection validation, target selection, messaging, and conversation summaries.

For full contract details for every public step, including documented inputs, outputs, and return behavior, see the [detailed step reference](../generated/slack-step-reference.md).

## Functional groups

- [Validation and Discovery](#validation-and-discovery)
- [Selection and Target Resolution](#selection-and-target-resolution)
- [Messaging](#messaging)
- [Conversation Summaries](#conversation-summaries)

## Summary

| Step | Group | Used by built-in workflows |
|------|-------|----------------------------|
| `validate_connection` | Validation and Discovery | `discover-slack-workspace` |
| `list_public_channels` | Validation and Discovery | `discover-slack-workspace` |
| `list_users` | Validation and Discovery | `discover-slack-workspace` |
| `select_user_target` | Selection and Target Resolution | `send-slack-direct-message` |
| `select_channel_target` | Selection and Target Resolution | `send-slack-channel-message` |
| `select_default_or_search_channel_target` | Selection and Target Resolution | `summarize-slack-target` |
| `prepare_message_destination` | Messaging | `send-slack-direct-message`, `send-slack-channel-message` |
| `open_direct_message` | Messaging | - |
| `prompt_message_body` | Messaging | `send-slack-direct-message`, `send-slack-channel-message` |
| `post_message` | Messaging | `send-slack-direct-message`, `send-slack-channel-message` |
| `select_target` | Conversation Summaries | `summarize-slack-target` |
| `ensure_target_conversation` | Conversation Summaries | `summarize-slack-target` |
| `read_recent_messages` | Conversation Summaries | `summarize-slack-target` |
| `ai_summarize_messages` | Conversation Summaries | `summarize-slack-target` |

## Validation and Discovery

Use these steps to validate the current Slack connection and inspect the accessible workspace surface.

- `validate_connection`: validate the configured Slack token and expose identity metadata
- `list_public_channels`: list public channels visible to the current token
- `list_users`: list users visible to the current token

## Selection and Target Resolution

Use these steps to resolve a reusable Slack target object for later workflows.

- `select_user_target`: filter visible Slack users by query and select one canonical user target
- `select_channel_target`: filter visible Slack channels by query and select one canonical channel target
- `select_default_or_search_channel_target`: choose one configured default channel or fall back to manual Slack channel search

## Messaging

Use these steps to resolve a message destination and post a plain-text Slack message.

- `prepare_message_destination`: resolve the selected user or channel target into the destination conversation used for posting
- `open_direct_message`: open or reuse a direct message conversation for the selected user target
- `prompt_message_body`: capture a multiline Slack message body for later posting
- `post_message`: post the prepared message to the selected conversation

## Conversation Summaries

Use these steps to resolve a target conversation, read its recent messages, and summarize them with AI.

- `select_target`: search both users and channels and select one unified Slack target
- `ensure_target_conversation`: resolve a Slack conversation from the selected target
- `read_recent_messages`: read the latest messages from the resolved conversation
- `ai_summarize_messages`: summarize the retrieved messages with AI
