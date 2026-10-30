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

The plugin ships the `github` [mod](../../concepts/mods.md): a side-panel pane that answers "what needs me now?". A line of totals (open PRs, to review, yours, merge queue length, failing runs), then only what asks something of you: **Review requested** (author, age, conflicts), **Your PRs** that have something to act on (checks failing, changes requested, conflicts, ready to merge, or in the merge queue with its position), and **CI failing** (the latest failed runs). Each lists three rows and counts the rest; with nothing pending it says so. Pressing a PR or a run opens the workspace with that row unfolded; **Open GitHub workspace** opens it as is. Its rail icon shows how many reviews wait for you, and a toast tells you when a review is requested or one of your PRs leaves the merge queue. It refreshes on timers and right after any workflow ends. Options (`[mods.github.options]`): `prs_refresh_seconds`, `queue_refresh_seconds`, `runs_refresh_seconds`, `queue_shown`, `refresh_key` (`f5`).

## Workspace

The plugin ships the `github` workspace: a full screen opened from its dock tile (`Esc` goes back) with the PRs waiting for your review (pressing a PR's line unfolds what can be done about it: a link to GitHub, a Review button that opens `review-pr`, Approve and Request changes — both submitted with no body — and Comment, which opens a field with Accept/Cancel and posts a general PR comment), your PRs — each unfolding two lines (the branch it lands on with the PR's age, and what it changes, added lines in green and removed in red, with “↻” and when it was last touched), its labels, a ⚠ Conflicts fold (the files that clash with the base branch, read from git the first time it is opened, with a button that runs `resolve-pr-conflicts`), a Reviewers fold (who approved, asked for changes or has yet to answer, each pressable to ask them again) and an Assignees fold, then, set apart at the bottom, what can be pressed: a merge button when nothing blocks it: not a draft, no conflicts, no change requested, review not still required (a review decision GitHub leaves empty, as repos with branch rulesets do, does not block), no unresolved review conversation (read when the row is opened, and again each refresh while it stays open) and its checks pass (**⇉ Add to queue** when the branch it lands on has a merge queue, **⇉ Squash & merge** otherwise; a first press asks for confirmation, and when the PR cannot merge yet a line says why) a **✉ Notify channel** button while the Slack plugin is active (runs `plugin:slack/post-message` with a message built from the `notify_message` template, so you pick the channel there), and a button that re-requests review from everyone who already reviewed; the buttons sit under an "Actions" heading, all of one width. Above the groups, a **search box** takes GitHub's own search syntax (`author:ana label:bug review:approved status:failure draft:false base:develop`, free text too): Enter searches the whole repo through GitHub (never per keystroke, since search has its own rate limit), the results replace the groups with the same rows and buttons, and **✕ Clear search** brings the groups back. A third group, *Other PRs* (closed by default), lists the open PRs that are neither yours nor waiting on you, with the same review buttons; it is read on its own timer, so it shows "loading…" without holding back the lists above it, and a failure there is shown inside it — the merge queue (what is in it now, and under a **Queue runs** fold the runs it has already run, passed or failed, with the same diagnosis and re-run buttons as below) and an AI diagnosis of failed checks (AI routing task `mods.workspace.github`, "PR check diagnosis") with a **⟳ Re-run failed jobs** button (re-runs the failed and cancelled jobs of the PR's Actions runs, for a cancelled runner or a flaky test) and a **✦ Fix with AI** button that runs `fix-pr-checks` on that PR, diagnosis included, and each diagnosed job of a workflow run offers the same **✦ Fix with AI**, which opens your AI CLI with that diagnosis typed in (no workflow: nothing is checked out or committed). A **Workflow runs** section lists the repo's latest GitHub Actions runs as GitHub's own list does, whoever started them: its state, what started it (the PR for a merge queue run, else the event and branch), when and how long. Pressing a run unfolds its Actions: for a failed one **✦ Diagnose failure** (the AI reads the log of each failed job, like the PR diagnosis; copyable), **⟳ Re-run failed jobs** and **⟳ Re-run all jobs**, plus a link to GitHub; a run still going offers no re-run until it ends. Ten runs show at first and **▾ Show 10 more** adds ten each time. Sections `prs`, `queue` and `runs` can be switched off one by one, also while Titan runs. Options (`[workspaces.github.options]`): `review_workflow` (`review-pr`, empty for no button), `conflicts_workflow` (`resolve-pr-conflicts`), `checks_workflow` (`fix-pr-checks`), `notify_workflow` (`plugin:slack/post-message`, empty for no button), `notify_message` (Markdown with `{number}`, `{title}`, `{url}`, `{author}`, `{branch}`), `prs_refresh_seconds`, `queue_refresh_seconds`, `runs_refresh_seconds` (30), `queue_shown`, `refresh_key` (empty by default: the mod binds `f5`).

It also refreshes right after any workflow ends. Mod and workspace read through the same readers (`titan_plugin_github/readers/`).

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
