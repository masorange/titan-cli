# Plugin Registration Guide

This guide explains how the App Store Connect plugin is registered with Titan CLI.

## Registration Status: ✅ COMPLETE

The plugin is now properly registered and discoverable by Titan CLI.

## Configuration

### 1. Titan Config (`.titan/config.toml`)

The plugin is registered in the Titan configuration file:

```toml
[plugins.appstore]
enabled = true
path = "plugins/titan-plugin-appstore"

[plugins.appstore.config]
# Credentials are stored in .appstore_connect/credentials.json
# To configure: edit .appstore_connect/credentials.json with your API credentials
# Run workflow: titan run plugins/titan-plugin-appstore/workflows/create-app-version.yaml
```

### 2. Plugin Entry Point (`titan_plugin.py`)

The plugin provides these functions for Titan discovery:

- `get_plugin_info()` - Returns plugin metadata (name, version, description, status)
- `get_steps()` - Returns dictionary of available steps
- `get_workflows_dir()` - Returns path to workflows directory

### 3. Available Steps

The plugin exports these workflow steps:

1. **select_app_step** - Interactive app selection from App Store Connect
2. **prompt_version_step** - Version string input with validation
3. **create_version_step** - Create new version in App Store Connect

## Verification

### Test Plugin Discovery

```bash
python -c "
import sys
sys.path.insert(0, 'plugins/titan-plugin-appstore')
import titan_plugin

info = titan_plugin.get_plugin_info()
steps = titan_plugin.get_steps()

print('Plugin:', info['name'], info['version'])
print('Steps:', list(steps.keys()))
"
```

Expected output:
```
Plugin: appstore 1.0.0
Steps: ['select_app_step', 'prompt_version_step', 'create_version_step']
```

### Test with Titan CLI

```bash
# List available plugins
titan plugins list

# Get plugin status
titan plugins status appstore

# Run workflow
titan run plugins/titan-plugin-appstore/workflows/create-app-version.yaml
```

## How It Works

### 1. Discovery

Titan CLI reads `.titan/config.toml` and discovers the plugin at the configured path.

### 2. Loading

Titan imports the plugin via:
```python
import sys
sys.path.insert(0, plugin_path)
import titan_plugin
```

### 3. Registration

Titan calls:
- `get_plugin_info()` to get metadata
- `get_steps()` to register workflow steps
- `get_workflows_dir()` to find workflows

### 4. Usage

Steps become available in workflows:
```yaml
steps:
  - id: select_app
    plugin: appstore
    step: select_app_step
```

## File Structure

```
plugins/titan-plugin-appstore/
├── __init__.py              # Root package (exports discovery functions)
├── titan_plugin.py          # Plugin entry point for Titan
├── titan_plugin_appstore/   # Main package
│   ├── __init__.py
│   ├── plugin.py            # Plugin metadata
│   └── steps/               # Workflow steps
│       ├── select_app_step.py
│       ├── prompt_version_step.py
│       └── create_version_step.py
└── workflows/
    └── create-app-version.yaml
```

## Troubleshooting

### Plugin not appearing in `titan plugins list`

**Check configuration:**
```bash
grep -A 5 "plugins.appstore" .titan/config.toml
```

Should show:
```toml
[plugins.appstore]
enabled = true
path = "plugins/titan-plugin-appstore"
```

**Verify path:**
```bash
ls -la plugins/titan-plugin-appstore/titan_plugin.py
```

Should exist and be importable.

### Steps not available in workflows

**Test step import:**
```python
import sys
sys.path.insert(0, 'plugins/titan-plugin-appstore')
import titan_plugin
steps = titan_plugin.get_steps()
print(steps.keys())
```

Should print: `dict_keys(['select_app_step', 'prompt_version_step', 'create_version_step'])`

### Workflows not found

**Check workflows directory:**
```bash
ls -la plugins/titan-plugin-appstore/workflows/
```

Should contain:
```
create-app-version.yaml
```

## Updating the Plugin

### Adding a New Step

1. Create step file in `titan_plugin_appstore/steps/`:
   ```python
   # my_new_step.py
   def my_new_step(ctx):
       # step implementation
       pass
   ```

2. Export from `titan_plugin_appstore/steps/__init__.py`:
   ```python
   from .my_new_step import my_new_step
   __all__ = [..., "my_new_step"]
   ```

3. Register in `titan_plugin.py`:
   ```python
   from titan_plugin_appstore.steps import (
       select_app_step,
       prompt_version_step,
       create_version_step,
       my_new_step,  # Add this
   )

   def get_steps():
       return {
           "select_app_step": select_app_step,
           "prompt_version_step": prompt_version_step,
           "create_version_step": create_version_step,
           "my_new_step": my_new_step,  # Add this
       }
   ```

4. Use in workflows:
   ```yaml
   steps:
     - id: my_step
       plugin: appstore
       step: my_new_step
   ```

### Adding a New Workflow

1. Create YAML file in `workflows/`:
   ```yaml
   # workflows/my-workflow.yaml
   name: "My Workflow"
   plugin: appstore
   steps:
     - id: step1
       step: select_app_step
   ```

2. Run with Titan:
   ```bash
   titan run plugins/titan-plugin-appstore/workflows/my-workflow.yaml
   ```

## Migration Notes

This plugin replaces the old `.titan/steps/appstore_connect/` implementation.

**Old usage:**
```yaml
# ❌ OLD
steps:
  - plugin: project
    step: select_app_step
```

**New usage:**
```yaml
# ✅ NEW
steps:
  - plugin: appstore
    step: select_app_step
```

The old implementation has been removed and all references should use the new plugin.

## Support

- **Configuration issues**: Check `.titan/config.toml`
- **Import errors**: Verify `titan_plugin.py` exists
- **Step errors**: Check step implementation in `titan_plugin_appstore/steps/`
- **Workflow errors**: Verify YAML syntax and step references

---

**Status**: ✅ Plugin registered and ready to use

**Last Updated**: March 9, 2026
