# GitHub Client API

The GitHub plugin adds GitHub operations to Titan through a high-level client and reusable workflows. It covers pull requests, reviews, issues, releases, teams, and repository metadata.

This page documents the plugin from a functional point of view, while also showing how each capability is called and which parameters it needs.

---

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

---

## Accessing the client

In Titan code, the public entry point is the GitHub plugin client:

```python
github_plugin = config.registry.get_plugin("github")
client = github_plugin.get_client()
```

The client returns `ClientResult[...]` values. In practice, this means each call can succeed with data or return an error result.

---

## Pull request operations

### Create a pull request

Creates a new pull request from a head branch into a base branch.

**Call:**

```python
client.create_pull_request(
    title="Add search filters",
    body="## Summary\n- adds filter controls\n- updates results state",
    base="main",
    head="feature/search-filters",
    draft=False,
    assignees=["alice"],
    reviewers=["bob", "example-org/backend-team"],
    labels=["feature", "ui"],
    excluded_reviewers=["carol"],
)
```

**Parameters:**

- `title`: Required. Pull request title.
- `body`: Required. Pull request description.
- `base`: Required. Target branch.
- `head`: Required. Source branch.
- `draft`: Optional. Whether to create the PR as draft.
- `assignees`: Optional. GitHub usernames to assign.
- `reviewers`: Optional. Usernames or teams.
- `labels`: Optional. Labels to apply.
- `excluded_reviewers`: Optional. Usernames to exclude after team expansion.

### Get a pull request

Fetches a single pull request by number.

**Call:**

```python
client.get_pull_request(123)
```

**Parameters:**

- `pr_number`: Required. Pull request number.

### List pull requests pending review

Returns PRs that still need your review.

**Call:**

```python
client.list_pending_review_prs(max_results=25, include_team_reviews=True)
```

**Parameters:**

- `max_results`: Optional. Maximum number of PRs to return.
- `include_team_reviews`: Optional. Include PRs requested from your teams.

### List your pull requests

Returns pull requests created by the authenticated user.

**Call:**

```python
client.list_my_prs(state="open", max_results=25)
```

**Parameters:**

- `state`: Optional. PR state such as `open`, `closed`, or `merged`.
- `max_results`: Optional. Maximum number of PRs to return.

### List all pull requests

Returns pull requests from the repository without filtering by author.

**Call:**

```python
client.list_all_prs(state="open", max_results=50)
```

**Parameters:**

- `state`: Optional. PR state such as `open`, `closed`, or `merged`.
- `max_results`: Optional. Maximum number of PRs to return.

### Read a pull request diff

Returns the pull request diff as text.

**Call:**

```python
client.get_pr_diff(pr_number=123, context_lines=3)
```

**Parameters:**

- `pr_number`: Required. Pull request number.
- `context_lines`: Optional. Number of diff context lines.

### Read patches for specific files

Returns patch text only for selected files in a PR.

**Call:**

```python
client.get_pr_file_patches(123, ["src/search.py", "tests/test_search.py"])
```

**Parameters:**

- `pr_number`: Required. Pull request number.
- `file_paths`: Required. List of paths to extract patches for.

### List changed files

Returns the file paths changed in a pull request.

**Call:**

```python
client.get_pr_files(123)
```

**Parameters:**

- `pr_number`: Required. Pull request number.

### List changed files with stats

Returns each changed file together with additions, deletions, and status.

**Call:**

```python
client.get_pr_files_with_stats(123)
```

**Parameters:**

- `pr_number`: Required. Pull request number.

### Checkout a pull request locally

Checks out the pull request branch in the local repository.

**Call:**

```python
client.checkout_pr(123)
```

**Parameters:**

- `pr_number`: Required. Pull request number.

### Add a PR comment

Adds a general comment to a pull request.

**Call:**

```python
client.add_comment(123, "Please add test coverage for the empty state.")
```

**Parameters:**

- `pr_number`: Required. Pull request number.
- `body`: Required. Comment body.

### Get the latest PR commit SHA

Returns the latest commit SHA associated with the pull request.

**Call:**

```python
client.get_pr_commit_sha(123)
```

**Parameters:**

- `pr_number`: Required. Pull request number.

### Merge a pull request

Merges a pull request using the selected merge strategy.

**Call:**

```python
client.merge_pr(
    pr_number=123,
    merge_method="squash",
    commit_title="Add search filters",
    commit_message="Adds filtering controls and updates result handling.",
)
```

**Parameters:**

- `pr_number`: Required. Pull request number.
- `merge_method`: Optional. Merge strategy such as `merge`, `squash`, or `rebase`.
- `commit_title`: Optional. Merge commit title.
- `commit_message`: Optional. Merge commit message.

---

## Review operations

### Get review threads

Returns code review threads for a pull request.

**Call:**

```python
client.get_pr_review_threads(pr_number=123, include_resolved=True)
```

**Parameters:**

- `pr_number`: Required. Pull request number.
- `include_resolved`: Optional. Include resolved threads.

### Resolve a review thread

Marks a review thread as resolved.

**Call:**

```python
client.resolve_review_thread("THREAD_NODE_ID")
```

**Parameters:**

- `thread_node_id`: Required. GraphQL node ID of the thread.

### Get reviews for a pull request

Returns submitted reviews such as approvals, change requests, and comments.

**Call:**

```python
client.get_pr_reviews(123)
```

**Parameters:**

- `pr_number`: Required. Pull request number.

### Create a draft review

Creates a draft review before submitting it.

**Call:**

```python
client.create_draft_review(
    pr_number=123,
    payload={
        "body": "I left a few comments.",
        "comments": [],
    },
)
```

**Parameters:**

- `pr_number`: Required. Pull request number.
- `payload`: Required. Review payload to send to GitHub.

### Submit a review

Submits a review event, optionally using an existing draft review.

**Call:**

```python
client.submit_review(
    pr_number=123,
    review_id=456,
    event="APPROVE",
    body="Looks good to me.",
)
```

**Parameters:**

- `pr_number`: Required. Pull request number.
- `review_id`: Optional. Draft review ID, or `None` to submit directly.
- `event`: Required. Review event such as `APPROVE`, `REQUEST_CHANGES`, or `COMMENT`.
- `body`: Optional. Review summary text.

### Delete a draft review

Deletes an existing draft review.

**Call:**

```python
client.delete_review(pr_number=123, review_id=456)
```

**Parameters:**

- `pr_number`: Required. Pull request number.
- `review_id`: Required. Draft review ID.

### Reply to a review comment

Adds a reply to an existing PR review comment.

**Call:**

```python
client.reply_to_comment(
    pr_number=123,
    comment_id=789,
    body="Updated in the latest commit.",
)
```

**Parameters:**

- `pr_number`: Required. Pull request number.
- `comment_id`: Required. Comment ID to reply to.
- `body`: Required. Reply text.

### Get general PR comments

Returns PR comments that are not attached to a code line.

**Call:**

```python
client.get_pr_general_comments(123)
```

**Parameters:**

- `pr_number`: Required. Pull request number.

### Add a general issue-style comment to a PR

Adds a non-inline comment to the pull request conversation.

**Call:**

```python
client.add_issue_comment(123, "This is ready for another pass.")
```

**Parameters:**

- `pr_number`: Required. Pull request number.
- `body`: Required. Comment body.

### Request or re-request review

Requests review from one or more users.

**Call:**

```python
client.request_pr_review(123, reviewers=["alice", "bob"])
```

**Parameters:**

- `pr_number`: Required. Pull request number.
- `reviewers`: Optional. List of GitHub usernames.

---

## Issue operations

### Create an issue

Creates a new GitHub issue.

**Call:**

```python
client.create_issue(
    title="Search results are not paginated",
    body="The results page should support server-side pagination.",
    assignees=["alice"],
    labels=["bug", "backend"],
)
```

**Parameters:**

- `title`: Required. Issue title.
- `body`: Required. Issue body.
- `assignees`: Optional. Assignee usernames.
- `labels`: Optional. Labels to apply.

### List repository labels

Returns the labels available in the repository.

**Call:**

```python
client.list_labels()
```

**Parameters:**

- No parameters.

---

## Release operations

### Create a release

Creates a GitHub release from a tag.

**Call:**

```python
client.create_release(
    tag_name="v1.2.0",
    title="v1.2.0",
    notes="Release notes for version 1.2.0.",
    generate_notes=False,
    verify_tag=True,
    prerelease=False,
)
```

**Parameters:**

- `tag_name`: Required. Git tag to release.
- `title`: Optional. Release title.
- `notes`: Optional. Release notes.
- `generate_notes`: Optional. Let GitHub generate the notes automatically.
- `verify_tag`: Optional. Verify that the tag exists before creating the release.
- `prerelease`: Optional. Mark the release as prerelease.

---

## Team operations

### List team members

Returns the members of a GitHub team.

**Call:**

```python
client.list_team_members("example-org/backend-team")
```

**Parameters:**

- `team_slug`: Required. Team identifier in `org/team` format.

This is also used internally when a pull request is created with team reviewers.

---

## Utility operations

### Read the PR template

Returns the configured PR template content when one is available.

**Call:**

```python
client.get_pr_template()
```

**Parameters:**

- No parameters.

### Get the current GitHub user

Returns the authenticated GitHub username.

**Call:**

```python
client.get_current_user()
```

**Parameters:**

- No parameters.

### Get a user's display name

Returns the display name for a GitHub login, falling back to the login if needed.

**Call:**

```python
client.get_user_display_name("alice")
```

**Parameters:**

- `login`: Required. GitHub username.

### Get the current user's display name

Returns the display name of the authenticated user.

**Call:**

```python
client.get_current_user_display_name()
```

**Parameters:**

- No parameters.

### Get the default branch

Returns the repository default branch from Titan config, GitHub metadata, or local git configuration.

**Call:**

```python
client.get_default_branch()
```

**Parameters:**

- No parameters.

---

## Related workflows

The GitHub plugin ships with workflows that use these capabilities directly:

- `create-pr-ai`: Creates a pull request after committing and pushing changes, with AI-generated PR content.
- `create-issue-ai`: Creates a GitHub issue from an AI-suggested title and description.
- `respond-pr-comments`: Helps review pending comments, reply to them, and request another review.

These workflows can be used as-is or extended from `.titan/workflows/`.
