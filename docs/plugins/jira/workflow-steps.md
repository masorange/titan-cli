# Jira Workflow Steps

The Jira plugin exposes public reusable workflow steps through `JiraPlugin.get_steps()`. The reference groups them by workflow intent so teams can discover related Jira building blocks quickly.

## Functional groups

- [Search and Selection](#search-and-selection)
- [Issue Retrieval and Analysis](#issue-retrieval-and-analysis)
- [Transitions and Fix Versions](#transitions-and-fix-versions)
- [Issue Creation](#issue-creation)

## Summary

| Step | Group | Used by built-in workflows |
|------|-------|----------------------------|
| `search_saved_query` | Search and Selection | `analyze-jira-issues` |
| `search_jql` | Search and Selection | - |
| `prompt_select_issue` | Search and Selection | `analyze-jira-issues` |
| `get_issue` | Issue Retrieval and Analysis | - |
| `ai_analyze_issue_requirements` | Issue Retrieval and Analysis | `analyze-jira-issues` |
| `get_transitions` | Transitions and Fix Versions | - |
| `transition_issue` | Transitions and Fix Versions | - |
| `verify_issue_state` | Transitions and Fix Versions | - |
| `list_versions` | Transitions and Fix Versions | - |
| `create_version` | Transitions and Fix Versions | - |
| `ensure_version_exists` | Transitions and Fix Versions | - |
| `assign_fix_version` | Transitions and Fix Versions | - |
| `verify_issue_has_fix_version` | Transitions and Fix Versions | - |
| `prompt_issue_description` | Issue Creation | `create-generic-issue` |
| `select_issue_type` | Issue Creation | `create-generic-issue` |
| `select_issue_priority` | Issue Creation | `create-generic-issue` |
| `ai_enhance_issue_description` | Issue Creation | `create-generic-issue` |
| `review_issue_description` | Issue Creation | `create-generic-issue` |
| `confirm_auto_assign` | Issue Creation | `create-generic-issue` |
| `create_generic_issue` | Issue Creation | `create-generic-issue` |

## Search and Selection

Use these steps to query Jira and let the user choose the issue that the workflow should act on.

- `search_saved_query`: search Jira issues using a named saved query
- `search_jql`: search Jira issues using explicit JQL from workflow context
- `prompt_select_issue`: prompt the user to choose one issue from the search results

## Issue Retrieval and Analysis

Use these steps to retrieve full issue details and produce AI-assisted requirement analysis.

- `get_issue`: fetch full Jira issue details for a selected issue
- `ai_analyze_issue_requirements`: generate an AI-assisted requirements analysis for the selected issue

## Transitions and Fix Versions

Use these steps to inspect transitions, move issues, and manage fix-version data.

- `get_transitions`: load the transitions available for an issue
- `transition_issue`: move an issue to another Jira state
- `verify_issue_state`: check that an issue is already in the expected state
- `list_versions`: list versions available for the current Jira project
- `create_version`: create a Jira version
- `ensure_version_exists`: create a version only when it does not already exist
- `assign_fix_version`: assign a fix version to an issue
- `verify_issue_has_fix_version`: verify that an issue already has the expected fix version

## Issue Creation

Use these steps to guide a user from a rough request to a created Jira issue.

- `prompt_issue_description`: capture a brief user description for the new issue
- `select_issue_type`: choose the Jira issue type for the new issue
- `select_issue_priority`: choose the Jira issue priority
- `ai_enhance_issue_description`: expand the raw request into title and description using AI
- `review_issue_description`: review and optionally edit the generated issue content
- `confirm_auto_assign`: ask whether the new issue should be self-assigned
- `create_generic_issue`: create the Jira issue from the prepared workflow context

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
