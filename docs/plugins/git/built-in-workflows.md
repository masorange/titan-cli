# Git Built-in Workflows

The Git plugin currently ships one workflow for commit creation and push automation.

## `commit-ai`

Creates a commit from the current working tree using an AI-generated commit message, then pushes it.

**Source workflow:** `plugins/titan-plugin-git/titan_plugin_git/workflows/commit-ai.yaml`

### Default flow

1. `git.get_status`
2. `before_commit` hook
3. `git.show_uncommitted_diff_summary`
4. `git.ai_generate_commit_message`
5. `git.create_commit`
6. `git.push`

### Hooks

- `before_commit`: inject validation or preparation steps before the commit is created

### Typical extension points

- run lints before committing
- run tests before committing
- collect extra project context before AI commit message generation

### Example extension

```yaml
extends: "plugin:git/commit-ai"

hooks:
  before_commit:
    - id: lint
      name: "Run Ruff"
      command: "poetry run ruff check ."
      on_error: fail
```

### Related public steps

- `get_status`
- `show_uncommitted_diff_summary`
- `ai_generate_commit_message`
- `create_commit`
- `push`
