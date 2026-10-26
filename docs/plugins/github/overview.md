# GitHub Plugin

The GitHub plugin provides Titan's GitHub integration for pull requests, issue creation, reviews, and review automation. It exposes:

- a high-level `GitHubClient` for direct use from Titan code
- reusable workflow `steps` for pull requests, issue creation, review handling, and code review pipelines
- built-in workflows such as `create-pr-ai`, `create-issue-ai`, `respond-pr-comments`, `resolve-pr-conflicts` and `fix-pr-checks`

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

## Mod

The plugin ships the `github` [mod](../../concepts/mods.md): a side-panel pane with the PRs waiting for your review (pressing a PR's line unfolds what can be done about it: a link to GitHub, a Review button that opens `review-pr`, Approve and Request changes — both submitted with no body — and Comment, which opens a field with Accept/Cancel and posts a general PR comment), your PRs — each unfolding two lines (the branch it lands on with the PR's age, and what it changes, added lines in green and removed in red, with “↻” and when it was last touched), its labels, a ⚠ Conflicts fold (the files that clash with the base branch, read from git the first time it is opened, with a button that runs `resolve-pr-conflicts`), a Reviewers fold (who approved, asked for changes or has yet to answer, each pressable to ask them again) and an Assignees fold, then, set apart at the bottom, what can be pressed: a merge button when the PR is approved, its checks pass and nothing conflicts (**⇉ Add to queue** when the branch it lands on has a merge queue, **⇉ Squash & merge** otherwise; a first press asks for confirmation, and when the PR cannot merge yet a line says why) a **✉ Notify channel** button while the Slack plugin is active (runs `plugin:slack/post-message` with a message built from the `notify_message` template, so you pick the channel there), and a button that re-requests review from everyone who already reviewed; the buttons sit under an "Actions" heading, all of one width. A third group, *Other PRs* (closed by default), lists the open PRs that are neither yours nor waiting on you, with the same review buttons; it is read on its own timer, so it shows "loading…" without holding back the lists above it, and a failure there is shown inside it — the merge queue and an AI diagnosis of failed checks (AI routing task `mods.github`, "PR check diagnosis") with a **⟳ Re-run failed jobs** button (re-runs the failed and cancelled jobs of the PR's Actions runs, for a cancelled runner or a flaky test) and a ⚒ Fix with AI button that runs `fix-pr-checks` on that PR, diagnosis included. Its rail icon shows how many reviews wait for you. Sections `prs` and `queue` can be switched off one by one. Options (`[mods.github.options]`): `review_workflow` (`review-pr`, empty for no button), `conflicts_workflow` (`resolve-pr-conflicts`), `checks_workflow` (`fix-pr-checks`), `notify_workflow` (`plugin:slack/post-message`, empty for no button), `notify_message` (Markdown with `{number}`, `{title}`, `{url}`, `{author}`, `{branch}`), `prs_refresh_seconds`, `queue_refresh_seconds`, `queue_shown`, `refresh_key` (`f5`).

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
