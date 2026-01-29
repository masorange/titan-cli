# Release Notes Workflows - Setup Guide

This guide explains how to set up the release notes generation workflow for Ragnarok iOS and Android projects.

## 📋 Prerequisites

**IMPORTANT**: Titan CLI uses a **project-based configuration system**. You **must** run Titan from within the project directory:

```bash
# ✅ CORRECT - Run from project directory
cd /path/to/ragnarok-ios
titan run release-notes-ios

# ❌ WRONG - Don't run from titan-cli directory
cd /path/to/titan-cli
titan run release-notes-ios  # This won't work!
```

### Key Changes in Titan v0.2.0 (PR #110)

- ❌ **Removed**: Global `project_root` and `active_project` settings from `[core]`
- ✅ **New**: Each project has its own `.titan/config.toml`
- ✅ **New**: Titan uses current working directory (`Path.cwd()`) as project root
- ✅ **Global config** (`~/.titan/config.toml`): Now only stores AI provider settings (shared across projects)
- ✅ **Project config** (`./.titan/config.toml`): Stores project-specific settings and plugin configuration

**Migration Note**: Old configurations with `[core]` settings will still load but those fields are ignored.

## ⚠️ Important Note

The release notes workflows are **project-specific** and designed exclusively for Ragnarok iOS/Android projects. They are **NOT** included in the Titan CLI plugin because they:

- Are tightly coupled to ECAPP JIRA project structure
- Use Ragnarok-specific brand categorization
- Have hardcoded conventions for iOS/Android directories

These workflows exist **only as templates** in `examples/` and must be copied to each project's `.titan/workflows/` directory.

## How It Works (Project-Based Model)

```
titan-cli/                          ragnarok-ios/
├── examples/                       ├── .titan/
│   └── ragnarok-ios-...yaml  ─────>│   ├── config.toml         (Project config)
│       (Template only)             │   └── workflows/
                                    │       └── release-notes-ios.yaml
~/.titan/                           │
└── config.toml                     └── ReleaseNotes/
    (Global AI config only)             └── 26.4.0.md  (Generated)

When you run:
  $ cd ragnarok-ios
  $ titan run release-notes-ios

Titan loads:
  1. Global config: ~/.titan/config.toml (AI providers)
  2. Project config: ./titan/config.toml (plugins, JIRA, GitHub)
  3. Project workflows: ./.titan/workflows/*.yaml
  4. Working directory: $(pwd) = ragnarok-ios
```

## Architecture

### Templates in Examples (Titan CLI)

- `ragnarok-ios-release-notes-workflow.yaml` → Copy to iOS project
- `ragnarok-android-release-notes-workflow.yaml` → Copy to Android project

These templates are **NOT** in the plugin. They only exist as reference/templates.

### Project Workflows (iOS/Android repos)

- iOS: `.titan/workflows/generate-release-notes-ios.yaml`
- Android: `.titan/workflows/generate-release-notes-android.yaml`

When copied to projects, these become the **only** workflow visible when running `titan workflow list`.

## Setup for iOS Project (Ragnarok iOS)

### 1. Copy the workflow template

```bash
cd /path/to/ragnarok-ios
mkdir -p .titan/workflows
cp /path/to/titan-cli/examples/ragnarok-ios-release-notes-workflow.yaml \
   .titan/workflows/generate-release-notes-ios.yaml
```

### 2. Configure Titan CLI

Create `.titan/config.toml`:

```toml
[project]
name = "Ragnarok iOS"
description = "Ragnarok iOS Mobile App"

[ai]
default = "anthropic"
model = "claude-sonnet-4-5"

[jira]
base_url = "https://your-domain.atlassian.net"
email = "your-email@example.com"
project_key = "ECAPP"

[github]
owner = "your-org"
repo = "ragnarok-ios"
default_branch = "develop"

[git]
main_branch = "develop"
```

### 3. Set up secrets

```bash
cd /path/to/ragnarok-ios
titan config secrets set JIRA_API_TOKEN
titan config secrets set GITHUB_TOKEN
titan config secrets set ANTHROPIC_API_KEY
```

### 4. Run the workflow

```bash
cd /path/to/ragnarok-ios
titan workflow list
# Should show ONLY: generate-release-notes-ios

titan workflow run generate-release-notes-ios
```

**Expected directory structure**:
```
ragnarok-ios/
├── ReleaseNotes/
│   └── release-notes-26.4.0.md  # Created by workflow
├── .titan/
│   ├── config.toml
│   └── workflows/
│       └── generate-release-notes-ios.yaml
```

## Setup for Android Project (Ragnarok Android)

### 1. Copy the workflow template

```bash
cd /path/to/ragnarok-android
mkdir -p .titan/workflows
cp /path/to/titan-cli/examples/ragnarok-android-release-notes-workflow.yaml \
   .titan/workflows/generate-release-notes-android.yaml
```

### 2. Configure Titan CLI

Create `.titan/config.toml`:

```toml
[project]
name = "Ragnarok Android"
description = "Ragnarok Android Mobile App"

[ai]
default = "anthropic"
model = "claude-sonnet-4-5"

[jira]
base_url = "https://your-domain.atlassian.net"
email = "your-email@example.com"
project_key = "ECAPP"

[github]
owner = "your-org"
repo = "ragnarok-android"
default_branch = "develop"

[git]
main_branch = "develop"
```

### 3. Set up secrets

```bash
cd /path/to/ragnarok-android
titan config secrets set JIRA_API_TOKEN
titan config secrets set GITHUB_TOKEN
titan config secrets set ANTHROPIC_API_KEY
```

### 4. Run the workflow

```bash
cd /path/to/ragnarok-android
titan workflow list
# Should show ONLY: generate-release-notes-android

titan workflow run generate-release-notes-android
```

**Expected directory structure**:
```
ragnarok-android/
├── docs/
│   └── release-notes/
│       └── release-notes-26.4.0.md  # Created by workflow
├── .titan/
│   ├── config.toml
│   └── workflows/
│       └── generate-release-notes-android.yaml
```

## Differences Between iOS and Android

| Aspect | iOS | Android |
|--------|-----|---------|
| **Workflow name** | `generate-release-notes-ios.yaml` | `generate-release-notes-android.yaml` |
| **Directory** | `ReleaseNotes/` | `docs/release-notes/` |
| **Platform param** | `platform: "iOS"` | `platform: "Android"` |
| **Subdirectories** | No platform subdirs | No platform subdirs |
| **LatestPublishers** | Updates `docs/LatestPublishers.md` | Not applicable |

## Why Not in the Plugin?

These workflows are **NOT** included in the Titan CLI plugin because:

1. **Project-specific**: Tightly coupled to Ragnarok iOS/Android architecture
2. **JIRA-specific**: Hardcoded to ECAPP project with specific customfields
3. **Brand-specific**: Uses Ragnarok brand categorization (Yoigo, Jazztel, etc.)
4. **Not reusable**: Would not work in other projects without heavy modification

By keeping them as **templates in examples/**, we:
- ✅ Make it clear they're project-specific
- ✅ Allow customization per project
- ✅ Avoid polluting `titan workflow list` in other projects
- ✅ Keep Titan CLI plugin generic and reusable

## For Other Projects

If you want to create release notes workflows for **other projects** (not Ragnarok):

1. Copy one of the example workflows as a base
2. Modify the JIRA project key, brand logic, and directory structure
3. Save it in your project's `.titan/workflows/` directory
4. Customize the AI prompts and templates as needed

These workflows serve as **reference implementations** for how to build project-specific workflows using Titan CLI's workflow system.

## Troubleshooting

### "No workflows found"

Check that you copied the workflow file to the correct location:
```bash
ls -la .titan/workflows/
```

### "Directory not found"

The workflows have `notes_directory` hardcoded:
- iOS: `ReleaseNotes/`
- Android: `docs/release-notes/`

If your project uses different directories, edit the workflow file:
```yaml
params:
  notes_directory: "custom/path"
```

### "JIRA authentication failed"

Verify your secrets:
```bash
titan config secrets list
```

Ensure `JIRA_API_TOKEN` is set correctly.

---

**Last Updated**: 2026-01-20
**Titan CLI Version**: 0.1.0
