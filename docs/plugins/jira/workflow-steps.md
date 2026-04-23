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

- `search_saved_query`
- `search_jql`
- `prompt_select_issue`

## Issue Retrieval and Analysis

Use these steps to retrieve full issue details and produce AI-assisted requirement analysis.

- `get_issue`
- `ai_analyze_issue_requirements`

## Transitions and Fix Versions

Use these steps to inspect transitions, move issues, and manage fix-version data.

- `get_transitions`
- `transition_issue`
- `verify_issue_state`
- `list_versions`
- `create_version`
- `ensure_version_exists`
- `assign_fix_version`
- `verify_issue_has_fix_version`

## Issue Creation

Use these steps to guide a user from a rough request to a created Jira issue.

- `prompt_issue_description`
- `select_issue_type`
- `select_issue_priority`
- `ai_enhance_issue_description`
- `review_issue_description`
- `confirm_auto_assign`
- `create_generic_issue`

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
