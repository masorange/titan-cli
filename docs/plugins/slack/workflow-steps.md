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
