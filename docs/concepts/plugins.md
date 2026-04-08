# Plugins

---

## Built-in plugins

Titan ships with three official plugins:

| Plugin | Description |
|--------|-------------|
| **git** | Smart commits, branch management, AI-powered commit messages |
| **github** | Create PRs with AI descriptions, manage issues, code reviews |
| **jira** | Search issues, AI-powered analysis, workflow automation |

Enable them per-project in `.titan/config.toml`:

```toml
[plugins.git]
enabled = true

[plugins.github]
enabled = true
```

## Community plugins

Titan also supports community plugins from external repositories.

There are currently two source channels:

- `stable`: install a plugin from a git repository pinned to a tag or commit
- `dev_local`: use a local checkout of a plugin repository during development

Project source selection is stored in `.titan/config.toml`:

```toml
[plugins.custom]
enabled = true

[plugins.custom.source]
channel = "stable"
```

For local plugin development:

```toml
[plugins.custom]
enabled = true

[plugins.custom.source]
channel = "dev_local"
path = "/absolute/path/to/local/plugin/repo"
```

In `dev_local`, Titan loads the plugin directly from the local repository by reading its `pyproject.toml` and `titan.plugins` entry point.

Community plugin installation metadata is tracked globally in `~/.titan/community_plugins.toml`.
