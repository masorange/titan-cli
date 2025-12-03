# plugins/titan-plugin-github/titan_plugin_github/messages.py
class Messages:
    class GitHubClient:
        cli_not_found = "GitHub CLI ('gh') not found. Please install it and ensure it's in your PATH."
        not_authenticated = "GitHub CLI is not authenticated. Run: gh auth login"
        config_repo_missing = "GitHub repository owner and name must be configured in [plugins.github.config]."
        pr_not_found = "Pull Request #{pr_number} not found."
        review_not_found = "Review ID #{review_id} for Pull Request #{pr_number} not found."
        api_error = "GitHub API error: {error_msg}"
        permission_error = "Permission denied for GitHub operation: {error_msg}"
        unexpected_error = "An unexpected GitHub error occurred: {error}"
        invalid_merge_method = "Invalid merge method: {method}. Must be one of: {valid_methods}"
        pr_creation_failed = "Failed to create pull request: {error}"
        failed_to_parse_pr_number = "Failed to parse PR number from URL: {url}"

    class GitHubPlugin:
        pass # Placeholder for any plugin-specific messages

msg = Messages()
