# AGENTS.md - Titan Slack Plugin

Rules specific to `titan-plugin-slack`. The repo-wide rules and guides are in the root
[`AGENTS.md`](../../AGENTS.md); user-facing docs in [`docs/plugins/slack/`](../../docs/plugins/slack/).

## What it is

Personal Slack integration with a user token: post messages and files to people and
channels, resolve targets, and summarise conversations with AI.

## Layout

Simplified, without the `models/` package: `steps/ → operations/ → clients/slack_client.py
→ clients/services/` over the Slack SDK (`clients/sdk.py`). Domain models in `models.py`,
formatting in `formatting.py`, the OAuth provider description in `config/`, config screen in `screens/`.
Workflows: `post-message`, `post-file`, `summarize-slack-target`.

## Plugin-specific rules

- The connection is BYO Slack App + PKCE through Titan's shared OAuth flow
  (`titan_cli/core/security/oauth.py`); the plugin only declares `SLACK_OAUTH`. Keep the
  configuration UX aligned with it.
- The grant (access + refresh token) lives in one keyring key, `<project>_slack_oauth`. The
  access token reaches the SDK only through `OAuthCredentials.create_client(...)`, and on a
  reactive refresh through `OAuthCredentials.refresh(apply)` (`plugin.py`).
- Keep raw Slack API payloads separate from the models returned to steps.
- Config: `SlackPluginConfig` in `titan_cli/core/plugins/models.py`.
- Tests: `tests/` (`clients/`, `services/`, `operations/`, `ui/` plus per-step files).
