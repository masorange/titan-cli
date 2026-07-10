# Slack Built-in Workflows

The Slack plugin currently ships one built-in workflow for target summaries.

## `summarize-slack-target`

Search for a person or channel, read recent Slack messages, and summarize them with AI.

**Source workflow:** `plugins/titan-plugin-slack/titan_plugin_slack/workflows/summarize-slack-target.yaml`

### Default flow

1. `slack.validate_connection`
2. `slack.select_target`
3. `slack.ensure_target_conversation`
4. `slack.read_recent_messages`
5. `slack.ai_summarize_messages`

### Typical usage

- summarize a recent DM or channel without manually browsing the Slack UI
- search Slack once and pick either a person or a channel from the same result list

### Scope constraints

- this workflow depends on conversation-history scopes and AI configuration
- it assumes one active Slack workspace binding for the current repository
- it searches both users and channels through `select_target` and does not offer a quick-pick shortcut for repository-configured `default_channels` (use `select_default_or_search_channel_target` directly in a custom workflow if that shortcut is needed)

### Related public steps

- `validate_connection`
- `select_target`
- `ensure_target_conversation`
- `read_recent_messages`
- `ai_summarize_messages`
