# Jira Built-in Workflows

The Jira plugin ships workflows for issue analysis and issue creation.

## `analyze-jira-issues`

Searches Jira issues, lets the user select one, and analyzes the selected issue with AI.

**Source workflow:** `plugins/titan-plugin-jira/titan_plugin_jira/workflows/analyze-jira-issues.yaml`

### Default flow

1. `jira.search_saved_query`
2. `jira.prompt_select_issue`
3. `jira.ai_analyze_issue_requirements`

### Typical usage

- triage open work before implementation
- get an AI-assisted requirements breakdown from an existing Jira issue

## `create-generic-issue`

Guides the user through issue creation, enhances the description with AI, and creates the Jira issue.

**Source workflow:** `plugins/titan-plugin-jira/titan_plugin_jira/workflows/create-generic-issue.yaml`

### Default flow

1. `jira.prompt_issue_description`
2. `jira.select_issue_type`
3. `jira.select_issue_priority`
4. `jira.ai_enhance_issue_description`
5. `jira.review_issue_description`
6. `jira.confirm_auto_assign`
7. `before_create_issue` hook
8. `jira.create_generic_issue`

### Hooks

- `before_create_issue`: inject project-specific validation or field enrichment before issue creation

### Example extension

```yaml
extends: "plugin:jira/create-generic-issue"

hooks:
  before_create_issue:
    - id: set_component
      name: "Enrich Jira Fields"
      plugin: project
      step: prepare_jira_fields
```
