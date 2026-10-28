# AGENTS.md - Titan Slack Plugin

Rules specific to `titan-plugin-slack`. The repo-wide rules and guides are in the root
[`AGENTS.md`](../../AGENTS.md); user-facing docs in [`docs/plugins/slack/`](../../docs/plugins/slack/).

## What it is

Personal Slack integration with a user token: post messages and files to people and
channels, resolve targets, and summarise conversations with AI.

## Layout

Simplified, without the `models/` package: `steps/ → operations/ → clients/slack_client.py
→ clients/services/` over the Slack SDK (`clients/sdk.py`). Domain models in `models.py`,
formatting in `formatting.py`, OAuth in `oauth.py`, config screen in `screens/`.
Workflows: `post-message`, `post-file`, `summarize-slack-target`.

## Plugin-specific rules

- The connection is BYO Slack App + PKCE (`oauth.py`); keep the configuration UX aligned
  with it.
- The user token lives in the keyring and reaches the SDK only through
  `broker.create_client(...)`, including on token refresh (`plugin.py`).
- Keep raw Slack API payloads separate from the models returned to steps.
- Config: `SlackPluginConfig` in `titan_cli/core/plugins/models.py`.
- Tests: `tests/` (`clients/`, `services/`, `operations/`, `ui/` plus per-step files).
