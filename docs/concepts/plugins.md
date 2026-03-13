# Plugins

!!! note "Coming soon"
    This page is under construction. For now, see the [README](https://github.com/masorange/titan-cli#readme) for a list of built-in plugins.

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
