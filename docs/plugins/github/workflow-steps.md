# GitHub Workflow Steps

The GitHub plugin exposes public reusable workflow steps through `GitHubPlugin.get_steps()`. The reference groups them by user-facing functionality so workflow authors can find related building blocks quickly.

## Functional groups

- [Pull Requests](#pull-requests)
- [Prompt and Selection](#prompt-and-selection)
- [Issue Creation](#issue-creation)
- [Pull Request Review](#pull-request-review)
- [Code Review](#code-review)
- [Worktree Support](#worktree-support)

## Summary

| Step | Group | Used by built-in workflows |
|------|-------|----------------------------|
| `create_pr` | Pull Requests | `create-pr-ai` |
| `get_pull_request` | Pull Requests | - |
| `merge_pull_request` | Pull Requests | - |
| `verify_pull_request_state` | Pull Requests | - |
| `ai_suggest_pr_description` | Pull Requests | `create-pr-ai` |
| `prompt_for_pr_title` | Prompt and Selection | - |
| `prompt_for_pr_body` | Prompt and Selection | - |
| `prompt_for_issue_body_step` | Prompt and Selection | `create-issue-ai` |
| `prompt_for_self_assign` | Prompt and Selection | `create-issue-ai` |
| `prompt_for_labels` | Prompt and Selection | - |
| `select_cli` | Prompt and Selection | - |
| `ai_suggest_issue_title_and_body` | Issue Creation | `create-issue-ai` |
| `preview_and_confirm_issue` | Issue Creation | - |
| `create_issue` | Issue Creation | `create-issue-ai` |
| `select_pr_for_review` | Pull Request Review | `respond-pr-comments` |
| `fetch_pending_comments` | Pull Request Review | `respond-pr-comments` |
| `check_clean_state` | Pull Request Review | `respond-pr-comments` |
| `checkout_pr_branch` | Pull Request Review | `respond-pr-comments` |
| `review_comments` | Pull Request Review | `respond-pr-comments` |
| `push_commits` | Pull Request Review | `respond-pr-comments` |
| `send_comment_replies` | Pull Request Review | `respond-pr-comments` |
| `request_review` | Pull Request Review | `respond-pr-comments` |
| `checkout_original_branch` | Pull Request Review | `respond-pr-comments` |
| `select_pr_for_code_review` | Code Review | - |
| `fetch_pr_review_bundle` | Code Review | - |
| `build_change_manifest` | Code Review | - |
| `build_existing_comments_index` | Code Review | - |
| `build_review_checklist` | Code Review | - |
| `ai_review_plan` | Code Review | - |
| `validate_review_plan` | Code Review | - |
| `resolve_review_context` | Code Review | - |
| `ai_review_findings` | Code Review | - |
| `normalize_findings` | Code Review | - |
| `dedupe_findings` | Code Review | - |
| `build_new_comment_actions` | Code Review | - |
| `validate_review_actions` | Code Review | - |
| `submit_review_actions` | Code Review | - |
| `build_thread_review_candidates` | Code Review | - |
| `build_thread_review_contexts` | Code Review | - |
| `ai_thread_resolution` | Code Review | - |
| `normalize_thread_decisions` | Code Review | - |
| `build_thread_actions` | Code Review | - |
| `create_worktree` | Worktree Support | - |
| `cleanup_worktree` | Worktree Support | - |

## Pull Requests

Use these steps to generate PR content, inspect PR state, and create or merge pull requests.

- `create_pr`
- `get_pull_request`
- `merge_pull_request`
- `verify_pull_request_state`
- `ai_suggest_pr_description`

## Prompt and Selection

Use these steps when a workflow needs interactive user input before creation or review work starts.

- `prompt_for_pr_title`
- `prompt_for_pr_body`
- `prompt_for_issue_body_step`
- `prompt_for_self_assign`
- `prompt_for_labels`
- `select_cli`

## Issue Creation

Use these steps to build and submit GitHub issues.

- `ai_suggest_issue_title_and_body`
- `preview_and_confirm_issue`
- `create_issue`

## Pull Request Review

Use these steps for the contributor flow of responding to PR comments and restoring local branch state afterward.

- `select_pr_for_review`
- `fetch_pending_comments`
- `check_clean_state`
- `checkout_pr_branch`
- `review_comments`
- `push_commits`
- `send_comment_replies`
- `request_review`
- `checkout_original_branch`

## Code Review

These are advanced review-pipeline steps for structured AI-assisted code review. They are public and reusable, but many are intended to be composed together rather than used in isolation.

- `select_pr_for_code_review`
- `fetch_pr_review_bundle`
- `build_change_manifest`
- `build_existing_comments_index`
- `build_review_checklist`
- `ai_review_plan`
- `validate_review_plan`
- `resolve_review_context`
- `ai_review_findings`
- `normalize_findings`
- `dedupe_findings`
- `build_new_comment_actions`
- `validate_review_actions`
- `submit_review_actions`
- `build_thread_review_candidates`
- `build_thread_review_contexts`
- `ai_thread_resolution`
- `normalize_thread_decisions`
- `build_thread_actions`

## Worktree Support

Use these steps when a GitHub workflow should operate in a dedicated worktree.

- `create_worktree`
- `cleanup_worktree`

## Docstring-based reference

The semiautomated step inventory reads public step docstrings from code and validates that each exposed step documents:

- `Requires`
- `Inputs (from ctx.data)` when applicable
- `Outputs (saved to ctx.data)` when applicable
- `Returns`

The generated machine-readable inventory lives under `docs/plugins/_generated/`.

For this project, the inventory is maintained through:

- `.titan/workflows/sync-plugin-docs.yaml`
- `.titan/workflows/validate-plugin-docs.yaml`
- `.titan/steps/sync_plugin_docs.py`
- `.titan/steps/validate_plugin_docs.py`
