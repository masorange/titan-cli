# Slack Built-in Workflows

The Slack plugin currently ships one built-in workflow for channel summaries.

## `summarize-slack-target`

Choose one configured default channel or search for another one, read recent Slack messages, and summarize them with AI.

**Source workflow:** `plugins/titan-plugin-slack/titan_plugin_slack/workflows/summarize-slack-target.yaml`

### Default flow

1. `slack.validate_connection`
2. `slack.select_default_or_search_channel_target`
3. `slack.ensure_target_conversation`
4. `slack.read_recent_messages`
5. `slack.ai_summarize_messages`

### Typical usage

- summarize a recent channel without manually browsing the Slack UI
- reuse repository-level default channels for common summary workflows while still allowing manual search when needed

### Scope constraints

- this workflow depends on conversation-history scopes and AI configuration
- it assumes one active Slack workspace binding for the current repository
- it currently follows a channel-oriented path through `select_default_or_search_channel_target`

### Related public steps

- `validate_connection`
- `select_default_or_search_channel_target`
- `ensure_target_conversation`
- `read_recent_messages`
- `ai_summarize_messages`
