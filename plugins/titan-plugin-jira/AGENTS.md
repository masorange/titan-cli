# AGENTS.md - Titan Jira Plugin

Rules specific to `titan-plugin-jira`. The repo-wide rules and guides are in the root
[`AGENTS.md`](../../AGENTS.md); user-facing docs in [`docs/plugins/jira/`](../../docs/plugins/jira/).

## What it is

Jira integration: search (JQL and saved queries), issue read/create/edit/transition,
versions, comments, and AI analysis and planning of issues.

## Layout

5-layer: `steps/ → operations/ → clients/jira_client.py → clients/services/ →
clients/network/`, with `models/{network,view,mappers}`. Also: `agents/` (`JiraAgent`,
prompts and contracts, configured by `config/jira_agent.toml`), `formatters/` (markdown
output), `utils/` (`IssueSorter`, `SavedQueries`), `constants/`, `readers/` (snapshots and readers shared by the mod and the workspace), the
`jira_ready` mod (`mods/jira_ready/`, the summary pane), the `jira` workspace (`workspaces/jira/`,
the full screen), `messages.py`.

## Plugin-specific rules

- Auth is Basic (`email:api_token`). The token is resolved by key existence and passed to
  `JiraClient` only inside `broker.create_client(...)` (`plugin.py`); never read it elsewhere.
- Config: `JiraPluginConfig` in `titan_cli/core/plugins/models.py`. `base_url` and `email`
  are global (`~/.titan/config.toml`); `default_project` can be overridden per project.
- New saved queries go in `utils/saved_queries.py`; workflows reference them by `query_name`.
- Custom fields and transition payloads differ per instance: never hardcode a field id
  or a project key.
- Tests: `tests/{services,operations,unit,utils,integration}`.
