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

- `stable`: pin a plugin version in the project config using a git tag or commit
- `dev_local`: use a local checkout of a plugin repository during development

The shared stable pin lives in `.titan/config.toml`:

```toml
[plugins.custom]
enabled = true

[plugins.custom.source]
channel = "stable"
repo_url = "https://github.com/user/titan-plugin-custom"
requested_ref = "v1.2.0"
resolved_commit = "0123456789abcdef0123456789abcdef01234567"
```

`requested_ref` stores the exact tag or ref used by that repository. Some repos use
tags like `v1.2.0`; others use `1.2.0`.

For local plugin development, the active override lives in `~/.titan/config.toml`:

```toml
[plugins.custom.source]
channel = "dev_local"
path = "/absolute/path/to/local/plugin/repo"
```

In `dev_local`, Titan loads the plugin directly from the local repository. In `stable`,
Titan prepares an isolated local runtime for the pinned commit.
