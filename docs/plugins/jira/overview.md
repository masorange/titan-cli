# Jira Plugin

The Jira plugin provides Titan's Jira integration for issue lookup, JQL search, transitions, versions, and AI-assisted issue workflows. It exposes:

- a high-level `JiraClient` for direct use from Titan code
- reusable workflow `steps` for issue search, issue analysis, transitions, and issue creation
- built-in workflows such as `analyze-jira-issues`, `create-generic-issue`, and `plan-jira-issue`

## Requirements

To use the Jira plugin in a project:

- Enable the `jira` plugin in `.titan/config.toml`
- Configure Jira connection settings such as `base_url` and `email`
- Store the Jira API token in Titan secrets
- Optionally configure a `default_project` so project-specific operations can work without passing a project key every time

Example project configuration:

```toml
[plugins.jira]
enabled = true

[plugins.jira.config]
base_url = "https://your-company.atlassian.net"
email = "developer@example.com"
default_project = "APP"
```

The API token is stored in secrets, not in the config file.

## Public surfaces

- [Client API](./client-api.md): direct Python methods exposed by `JiraClient`
- [Workflow Steps](./workflow-steps.md): public reusable workflow steps grouped by functionality
- [Built-in Workflows](./built-in-workflows.md): workflows shipped by the plugin

## Workspace and mod

The plugin ships the `jira` [workspace](../../concepts/workspaces.md): a full screen opened from the **Jira** dock tile (`Esc` goes back). Issues from one or several projects (a Projects dropdown), narrowed by statuses, components and starred filters read from Jira, or by a free-text search (an issue key or number, or words matched in summary, description and comments; it ignores Status and Filters) sit on the left; the open issue sits on the right (the two stack when the window is narrow). The card shows the summary, assignee, status, fix version (or that it has none), parent issue, folded description, comments and an AI summary (AI routing task `workspace.jira`), with Plan, Take, Move, Fix version and Open buttons. Move reads the statuses Jira allows from the issue's current one and transitions it to the one you pick. Fix version lists the versions of the issue's project, unreleased ones or, with the Released switch on, released ones; the current one is ticked, and picking another replaces it (Clear empties it). The list shows `shown` issues; when Jira has more, "＋ Show all" loads them (up to 100, one Jira search). The list is read again when a workflow ends. Options (`[workspaces.jira.options]`): `project`, `shown`, `refresh_seconds`, `refresh_key`, `plan_workflow` (`plan-jira-issue`), `take_status` (`In Progress`); an empty `plan_workflow` or `take_status` hides its button. The picks (projects, statuses, filters, search) are kept between runs.

The `jira_ready` [mod](../../concepts/mods.md) is the summary in the side panel: the unfinished issues assigned to you, latest touched first. Pressing one, or **Open Jira workspace**, opens the workspace on it (searching for it when the filters hide it). Options (`[mods.jira_ready.options]`): `project`, `shown`, `refresh_seconds`.

Both read through `titan_plugin_jira/readers/` (snapshots in `models.py`, readers in `issues.py`), neither imports the other, and either can be switched off alone.

## Accessing the client

In Titan code, the public entry point is the Jira plugin client:

```python
jira_plugin = config.registry.get_plugin("jira")
client = jira_plugin.get_client()
```

The client returns `ClientResult[...]` values. In practice, this means each call can succeed with data or return an error result.

## Public workflow steps

The Jira plugin exposes public reusable steps for:

- search and interactive selection
- issue retrieval and AI analysis
- transitions and fix version automation
- guided issue creation

The complete grouped reference lives in [Workflow Steps](./workflow-steps.md).
