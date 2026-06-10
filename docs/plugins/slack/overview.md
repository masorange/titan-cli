# Slack Plugin

The Slack plugin provides Titan's Slack integration for personal user authentication, workspace validation, and read-only discovery. It exposes:

- a high-level `SlackClient` for direct use from Titan code
- reusable workflow `steps` for connection validation and discovery
- one built-in workflow for validating and inspecting the current Slack workspace surface

## Requirements

To use the Slack plugin in a project:

- Enable the `slack` plugin in `.titan/config.toml`
- Configure Slack through Titan's Slack-specific configuration screen
- Complete the BYO Slack App + PKCE connection flow
- Store the resulting personal Slack token in Titan secrets

Example project configuration:

```toml
[plugins.slack]
enabled = true
```

Slack stores the personal token in Titan secrets/keyring, not in the config file.

## Public surfaces

- [Client API](./client-api.md): direct Python methods exposed by `SlackClient`
- [Workflow Steps](./workflow-steps.md): public reusable workflow steps grouped by functionality
- [Built-in Workflows](./built-in-workflows.md): workflows shipped by the plugin

## Accessing the client

In Titan code, the public entry point is the Slack plugin client:

```python
slack_plugin = config.registry.get_plugin("slack")
client = slack_plugin.get_client()
```

The client returns direct values and raises plugin-level exceptions when Slack operations fail.

## Public workflow steps

The Slack plugin currently exposes public reusable steps for:

- validating the current Slack connection
- listing public channels visible to the current token
- listing users visible to the current token
- selecting a reusable Slack target from users or channels for later workflows
- opening a direct message and posting a Slack message through reusable messaging steps

The grouped reference lives in [Workflow Steps](./workflow-steps.md).
