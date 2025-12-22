# Titan Plugin - GitHub

GitHub integration plugin for Titan CLI with AI-powered PR creation and management.

## Features

- Pull Request creation and management
- AI-powered PR title and description generation
- PR review workflows
- Auto-assignment of PRs to creator
- Integration with gh CLI for seamless authentication

## Installation

This plugin is installed automatically with Titan CLI when gh CLI is configured.

## Prerequisites

### gh CLI Installation

The GitHub plugin uses `gh CLI` for all GitHub operations. Install it:

```bash
# macOS
brew install gh

# Linux
# See https://github.com/cli/cli#installation

# Windows
# See https://github.com/cli/cli#installation
```

### Authentication

Authenticate with GitHub using gh CLI:

```bash
gh auth login
```

This will:
1. Open a browser for OAuth authentication
2. Store credentials securely in your system keychain
3. Configure git to use gh CLI for GitHub operations

**Important**: Do NOT set `GITHUB_TOKEN` environment variable as it will conflict with gh CLI authentication.

## Configuration

### Project Configuration

Configure in `.titan/config.toml` (project-level):

```toml
[plugins.github]
enabled = true

[plugins.github.config]
repo_owner = "your-org"
repo_name = "your-repo"
default_branch = "master"  # or "main", "develop"
default_reviewers = ["reviewer1", "reviewer2"]
pr_template_path = ".github/pull_request_template.md"
auto_assign_prs = true  # Auto-assign PRs to creator
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `repo_owner` | string | **required** | GitHub repository owner (user or organization) |
| `repo_name` | string | **required** | GitHub repository name |
| `default_branch` | string | `null` | Default branch for PRs (falls back to repo default) |
| `default_reviewers` | list | `[]` | Default reviewers to add to PRs |
| `pr_template_path` | string | `null` | Path to PR template file |
| `auto_assign_prs` | boolean | `false` | Automatically assign PRs to the creator |

## Usage

### Available Workflows

#### Create PR with AI
AI-powered PR creation with automatic commit message and PR description generation:

```bash
titan
# Select: Run Workflow → Create Pull Request with AI
```

This workflow:
1. Runs pre-commit hooks (linting, tests)
2. Generates AI commit message from changes
3. Creates commit
4. Generates AI PR title and description
5. Pushes to remote
6. Creates pull request
7. **Auto-assigns PR to you** (if `auto_assign_prs = true`)

### Available Steps

The GitHub plugin provides reusable workflow steps:

#### `create_pr`
Creates a pull request with AI-generated or manual title/description.

**Inputs:**
- `pr_title` (string): PR title
- `pr_body` (string, optional): PR description
- `pr_head_branch` (string): Feature branch
- `pr_is_draft` (boolean, optional): Create as draft PR

**Outputs:**
- `pr_number` (int): Created PR number
- `pr_url` (string): PR URL

#### `assign_pr`
Assigns users to a pull request (reusable step).

**Inputs:**
- `pr_number` (int): PR number to assign
- `assignees` (list[string], optional): GitHub usernames. Defaults to current user if not provided.

**Example workflow:**
```yaml
steps:
  - id: create_pr
    name: "Create PR"
    plugin: github
    step: create_pr

  - id: assign_reviewers
    name: "Assign Reviewers"
    plugin: github
    step: assign_pr
    params:
      assignees: ["reviewer1", "reviewer2"]
```

#### `ai_suggest_pr_description`
Generates AI-powered PR title and description from commits.

#### `prompt_for_pr_title`
Prompts user for PR title (fallback when AI is rejected).

#### `prompt_for_pr_body`
Prompts user for PR body/description (fallback when AI is rejected).

### Auto-Assignment Feature

When `auto_assign_prs` is enabled in configuration:

- **Automatic**: PRs are automatically assigned to the creator
- **Seamless**: No manual action required
- **Non-blocking**: If assignment fails, the PR is still created successfully
- **User-friendly**: Shows confirmation message when assigned

**Example output:**
```
✅ Pull request #123 created: https://github.com/org/repo/pull/123
ℹ️  Assigned PR to your-username
```

**If assignment fails:**
```
✅ Pull request #123 created: https://github.com/org/repo/pull/123
⚠️  Could not auto-assign PR: permission denied
```

### Manual PR Assignment

You can also assign PRs manually using gh CLI:

```bash
gh pr edit <pr-number> --add-assignee @me
```

## Troubleshooting

### gh CLI not authenticated

**Error:**
```
❌ Plugin 'github' failed to initialize:
GitHub CLI is not authenticated. Run: gh auth login
```

**Solution:**
```bash
gh auth login
```

### GITHUB_TOKEN conflicts

**Error:**
```
❌ GITHUB_TOKEN environment variable has invalid token
```

**Solution:**
Remove GITHUB_TOKEN from your shell configuration:

```bash
# Remove from ~/.zshrc or ~/.bashrc
# Then reload:
source ~/.zshrc
```

Or unset in current session:
```bash
unset GITHUB_TOKEN
```

### Multiple gh accounts

**Error:**
```
⚠️ gh CLI has authenticated account but it's not active
```

**Solution:**
```bash
gh auth switch
# Select the account you want to use
```

### Permission denied for assignment

**Error:**
```
⚠️ Could not auto-assign PR: permission denied
```

**Cause:** Your GitHub token doesn't have `repo` scope.

**Solution:**
```bash
gh auth refresh -h github.com -s repo
```

## Development

Run tests:
```bash
cd plugins/titan-plugin-github
poetry run pytest
```

## Architecture

### gh CLI Wrapper

This plugin uses `gh CLI` as a wrapper for all GitHub operations:

**Advantages:**
- ✅ No Python dependencies for GitHub API
- ✅ OAuth authentication handled by gh CLI
- ✅ Secure token storage in system keychain
- ✅ Independent updates from Titan
- ✅ Complete GitHub API coverage

**See:** [Issue #71](https://github.com/masmovil/titan-cli/issues/71) for detailed discussion on this architectural decision.

## Related Documentation

- [gh CLI Documentation](https://cli.github.com/manual/)
- [GitHub API Documentation](https://docs.github.com/en/rest)
- [Titan CLI Documentation](../../README.md)
