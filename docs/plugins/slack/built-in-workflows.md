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
