# Slack Built-in Workflows

The Slack plugin currently ships one small built-in workflow for connection validation and read-only discovery.

## `discover-slack-workspace`

Validate the current Slack connection, list public channels, and list visible users.

**Source workflow:** `plugins/titan-plugin-slack/titan_plugin_slack/workflows/discover-slack-workspace.yaml`

### Default flow

1. `slack.validate_connection`
2. `slack.list_public_channels`
3. `slack.list_users`

### Typical usage

- verify that Slack OAuth configuration is working end to end
- inspect what the current personal token can read before building richer workflows
- confirm the first public Slack step surface behaves coherently inside Titan

### Scope constraints

- the workflow stays read-only
- it does not read channel history yet
- it assumes one active personal Slack connection per user

## `send-slack-direct-message`

Select a person, open or reuse a direct message conversation, compose a message, and send it.

**Source workflow:** `plugins/titan-plugin-slack/titan_plugin_slack/workflows/send-slack-direct-message.yaml`

### Default flow

1. `slack.validate_connection`
2. `slack.select_user_target`
3. `slack.open_direct_message`
4. `slack.prompt_message_body`
5. `slack.post_message`

### Typical usage

- send a personal message to one selected Slack user from Titan
- validate that DM-specific Slack scopes and the direct-message path are working end to end

### Scope constraints

- this workflow depends on DM-related Slack scopes beyond the original discovery-only baseline
- it still assumes one active personal Slack connection per user

## `summarize-slack-target`

Search for a person or channel, resolve the backing conversation, read recent Slack messages, and summarize them with AI.

**Source workflow:** `plugins/titan-plugin-slack/titan_plugin_slack/workflows/summarize-slack-target.yaml`

### Default flow

1. `slack.validate_connection`
2. `slack.select_target`
3. `slack.ensure_target_conversation`
4. `slack.read_recent_messages`
5. `slack.ai_summarize_messages`

### Typical usage

- summarize a recent conversation without manually browsing the Slack UI
- inspect recent channel or DM context from Titan before taking action

### Scope constraints

- this workflow depends on conversation-history scopes and AI configuration
- it assumes one active personal Slack connection per user
