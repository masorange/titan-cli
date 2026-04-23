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

- `create_pr`: create a pull request from workflow context data
- `get_pull_request`: fetch a pull request and expose it to later steps
- `merge_pull_request`: merge a pull request with workflow-selected merge options
- `verify_pull_request_state`: validate that a pull request is in the expected state
- `ai_suggest_pr_description`: generate PR title and body from branch changes using AI

## Prompt and Selection

Use these steps when a workflow needs interactive user input before creation or review work starts.

- `prompt_for_pr_title`: capture a PR title interactively when one is not already available
- `prompt_for_pr_body`: capture a PR body interactively when one is not already available
- `prompt_for_issue_body_step`: capture the raw issue request before AI expansion
- `prompt_for_self_assign`: ask whether the current user should be assigned to the issue
- `prompt_for_labels`: prompt for labels to attach to an issue or PR
- `select_cli`: choose which external CLI a workflow should use

## Issue Creation

Use these steps to build and submit GitHub issues.

- `ai_suggest_issue_title_and_body`: generate issue content and suggested labels from user input
- `preview_and_confirm_issue`: show generated issue content and ask for explicit confirmation
- `create_issue`: create the final GitHub issue from workflow context data

## Pull Request Review

Use these steps for the contributor flow of responding to PR comments and restoring local branch state afterward.

- `select_pr_for_review`: select a pull request that needs comment response work
- `fetch_pending_comments`: load unresolved PR comments into workflow context
- `check_clean_state`: ensure the current branch is safe to leave before checkout
- `checkout_pr_branch`: switch to the PR branch while preserving original branch context
- `review_comments`: guide the user through resolving comments and making local changes
- `push_commits`: push local follow-up commits back to the PR branch
- `send_comment_replies`: submit replies for the reviewed comments
- `request_review`: request another review after follow-up work is pushed
- `checkout_original_branch`: restore the original branch after review work completes

## Code Review

These are advanced review-pipeline steps for structured AI-assisted code review. They are public and reusable, but many are intended to be composed together rather than used in isolation.

- `select_pr_for_code_review`: choose a PR for the advanced code-review pipeline
- `fetch_pr_review_bundle`: collect PR, diff, file, and discussion context for review
- `build_change_manifest`: build a structured manifest of changed files and targets
- `build_existing_comments_index`: index existing review comments to avoid duplicate findings
- `build_review_checklist`: prepare a review checklist from PR context
- `ai_review_plan`: ask AI to propose the review strategy
- `validate_review_plan`: verify that the AI review plan is structurally usable
- `resolve_review_context`: expand the exact contexts needed for targeted analysis
- `ai_review_findings`: run targeted AI analysis and produce candidate findings
- `normalize_findings`: normalize raw findings into workflow-friendly structures
- `dedupe_findings`: remove duplicate or overlapping findings before submission
- `build_new_comment_actions`: translate findings into GitHub review actions
- `validate_review_actions`: validate those review actions before posting
- `submit_review_actions`: submit review comments or review actions to GitHub
- `build_thread_review_candidates`: collect review threads that may need follow-up decisions
- `build_thread_review_contexts`: expand context needed to evaluate thread resolution
- `ai_thread_resolution`: ask AI whether open threads should be resolved or reopened
- `normalize_thread_decisions`: normalize thread resolution decisions for execution
- `build_thread_actions`: build GitHub actions from normalized thread decisions

## Worktree Support

Use these steps when a GitHub workflow should operate in a dedicated worktree.

- `create_worktree`: create an isolated worktree for GitHub-focused workflow tasks
- `cleanup_worktree`: remove a worktree created during workflow execution

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
