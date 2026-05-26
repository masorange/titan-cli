# GitHub Plugin

The GitHub plugin provides Titan's GitHub integration for pull requests, issue creation, reviews, and review automation. It exposes:

- a high-level `GitHubClient` for direct use from Titan code
- reusable workflow `steps` for pull requests, issue creation, review handling, and code review pipelines
- built-in workflows such as `create-pr-ai`, `create-issue-ai`, and `respond-pr-comments`

## Requirements

To use the GitHub plugin in a project:

- Enable the `github` plugin in `.titan/config.toml`
- Enable the `git` plugin, because the GitHub plugin depends on it
- Use a GitHub repository that is either configured explicitly or detectable from the git remote
- Install and authenticate the `gh` CLI

Example project configuration:

```toml
[plugins.git]
enabled = true

[plugins.github]
enabled = true

[plugins.github.config]
repo_owner = "example-org"
repo_name = "example-repo"
default_branch = "main"
pr_template_path = ".github/pull_request_template.md"
auto_assign_prs = true
```

## Public surfaces

- [Client API](./client-api.md): direct Python methods exposed by `GitHubClient`
- [Workflow Steps](./workflow-steps.md): public reusable workflow steps grouped by functionality
- [Built-in Workflows](./built-in-workflows.md): workflows shipped by the plugin

## Accessing the client

In Titan code, the public entry point is the GitHub plugin client:

```python
github_plugin = config.registry.get_plugin("github")
client = github_plugin.get_client()
```

The client returns `ClientResult[...]` values. In practice, this means each call can succeed with data or return an error result.

## Public workflow steps

The GitHub plugin exposes public reusable steps for:

- pull request creation and validation
- issue creation
- pull request review response flows
- advanced code review pipelines
- worktree support
- workflow prompts and CLI selection

The complete grouped reference lives in [Workflow Steps](./workflow-steps.md).
