# Titan CLI Plugin Architecture

## Overview

The Titan CLI plugin system provides a flexible, extensible architecture that allows third-party integrations to be dynamically discovered, loaded, and managed. Plugins extend Titan CLI functionality by providing:

- **Service Clients**: Integration with external services (Git, GitHub, Jira, etc.)
- **Workflow Steps**: Reusable atomic operations that can be composed in workflows
- **Workflow Definitions**: Pre-built workflow templates
- **Configuration Models**: Type-safe configuration schemas

## Architecture

![Plugin Architecture](assets/diagrams/plugin_class_architecture.mmd)

### Core Components

The plugin system consists of four main modules:

#### 1. `plugin_base.py` - Plugin Interface

Defines the `TitanPlugin` abstract base class that all plugins must inherit from. This establishes the contract between the plugin system and plugin implementations.

**Key Responsibilities:**
- Define plugin metadata (name, version, description)
- Declare dependencies on other plugins
- Provide initialization hooks
- Export clients and workflow steps
- Indicate availability status

#### 2. `plugin_registry.py` - Plugin Lifecycle Manager

The `PluginRegistry` class manages the complete lifecycle of plugins, from discovery through initialization.

**Key Responsibilities:**
- Discover plugins via Python entry points
- Load and validate plugin classes
- Resolve and initialize plugins in dependency order
- Track successful and failed plugins
- Provide plugin lookup and enumeration

#### 3. `models.py` - Configuration Schemas

Defines Pydantic models for plugin configuration, ensuring type safety and validation.

**Available Models:**
- `PluginConfig`: Base configuration structure
- `GitPluginConfig`: Git-specific settings
- `GitHubPluginConfig`: GitHub integration settings
- `JiraPluginConfig`: Jira integration settings

#### 4. `available.py` - Plugin Catalog

Maintains a registry of known, installable plugins. This enables the CLI to provide plugin installation capabilities.

**Purpose:**
- List official/known plugins
- Provide package names for installation
- Document plugin dependencies
- Enable discovery of available integrations

## Plugin Discovery and Initialization

![Discovery and Initialization Flow](assets/diagrams/plugin_discovery_initialization.mmd)

### Discovery Phase

The plugin system uses Python's `entry_points` mechanism to discover installed plugins:

1. **Entry Point Group**: Plugins register themselves under the `titan.plugins` group
2. **Dynamic Loading**: The registry loads plugin classes dynamically at runtime
3. **Validation**: Each loaded class is validated to ensure it inherits from `TitanPlugin`
4. **Error Handling**: Failed plugin loads are tracked separately in `_failed_plugins`

```python
# Example plugin registration in setup.py or pyproject.toml
[project.entry-points."titan.plugins"]
git = "titan_plugin_git:GitPlugin"
github = "titan_plugin_github:GitHubPlugin"
```

### Initialization Phase

Plugins are initialized in dependency order to ensure that dependent plugins have access to their dependencies:

![Dependency Resolution](assets/diagrams/plugin_dependency_resolution.mmd)

**Initialization Algorithm:**

1. **Build Plugin Queue**: All discovered plugins start in the "to initialize" queue
2. **Dependency Check**: For each plugin, verify all dependencies are initialized
3. **Initialize**: Call `plugin.initialize(config, secrets)` when dependencies are met
4. **Error Propagation**: If a dependency fails, mark dependent plugins as failed
5. **Circular Detection**: Detect and fail plugins with circular dependencies
6. **Multi-Pass**: Continue processing until all plugins are initialized or failed

**Example Dependency Chain:**
```
Git Plugin (no dependencies)
  ↓
GitHub Plugin (depends on Git)
  ↓
[Both initialized successfully]
```

## Plugin Interface

### TitanPlugin Base Class

```python
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable
from pathlib import Path

class TitanPlugin(ABC):
    """Base class for all Titan plugins."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier (required)"""
        pass
    
    @property
    def version(self) -> str:
        """Plugin version (default: "0.0.0")"""
        return "0.0.0"
    
    @property
    def description(self) -> str:
        """Human-readable description"""
        return ""
    
    @property
    def dependencies(self) -> list[str]:
        """List of required plugin names"""
        return []
    
    def initialize(self, config: Any, secrets: Any) -> None:
        """
        Initialize plugin with configuration and secrets.
        Called once during plugin lifecycle.
        """
        pass
    
    def get_client(self) -> Optional[Any]:
        """
        Return the main client instance.
        Injected into WorkflowContext for use in steps.
        """
        return None
    
    def get_steps(self) -> Dict[str, Callable]:
        """
        Return workflow steps provided by this plugin.
        Maps step names to step functions.
        """
        return {}
    
    def is_available(self) -> bool:
        """
        Check if plugin is properly configured and available.
        """
        return True
    
    @property
    def workflows_path(self) -> Optional[Path]:
        """
        Path to directory containing workflow definitions.
        """
        return None
```

### Creating a Plugin

Here's a minimal plugin implementation:

```python
from titan_cli.core.plugins import TitanPlugin
from typing import Dict, Callable

class MyPlugin(TitanPlugin):
    def __init__(self):
        self._client = None
    
    @property
    def name(self) -> str:
        return "my_plugin"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "My custom plugin"
    
    @property
    def dependencies(self) -> list[str]:
        return ["git"]  # Requires git plugin
    
    def initialize(self, config, secrets):
        """Initialize with config and secrets"""
        api_key = secrets.get("my_plugin.api_key")
        self._client = MyClient(api_key=api_key)
    
    def get_client(self):
        """Return client instance"""
        return self._client
    
    def get_steps(self) -> Dict[str, Callable]:
        """Register workflow steps"""
        return {
            "my_step": self.my_step_function,
        }
    
    def my_step_function(self, context):
        """Custom workflow step"""
        self._client.do_something()
        return {"status": "success"}
```

## Plugin Integration

![Plugin Workflow Integration](assets/diagrams/plugin_workflow_integration.mmd)

### Workflow Context Integration

Plugins integrate with the workflow execution system through several mechanisms:

1. **Client Injection**: Clients from `get_client()` are injected into `WorkflowContext`
2. **Step Registration**: Steps from `get_steps()` are registered in the step registry
3. **Workflow Templates**: Workflows from `workflows_path` are discovered and made available
4. **Configuration**: Plugin-specific config is accessible during initialization

### Usage in Workflows

Once registered, plugin components are available in workflows:

```yaml
# Example workflow using plugin steps
steps:
  - name: "Checkout branch"
    step: "git.checkout"  # Step from git plugin
    params:
      branch: "feature/new-feature"
  
  - name: "Create PR"
    step: "github.create_pr"  # Step from github plugin
    params:
      title: "New Feature"
      base: "main"
```

## Configuration System

### Plugin Configuration Models

The configuration system uses Pydantic models for type safety and validation:

#### GitPluginConfig

```python
class GitPluginConfig(BaseModel):
    main_branch: str = "main"
    default_remote: str = "origin"
    protected_branches: List[str] = ["main"]
```

#### GitHubPluginConfig

```python
class GitHubPluginConfig(BaseModel):
    repo_owner: Optional[str]
    repo_name: Optional[str]
    default_branch: Optional[str] = None
    default_reviewers: List[str] = []
    pr_template_path: Optional[str] = None
    auto_assign_prs: bool = False
```

#### JiraPluginConfig

```python
class JiraPluginConfig(BaseModel):
    base_url: str  # e.g., "https://jira.company.com"
    email: str
    api_token: Optional[str] = None  # Stored in secrets
    default_project: str
    timeout: int = 30
    enable_cache: bool = True
    cache_ttl: int = 300  # seconds
```

### Configuration in Practice

Configuration is typically stored in `config.toml`:

```toml
[plugins.git]
enabled = true
main_branch = "main"
default_remote = "origin"
protected_branches = ["main", "develop"]

[plugins.github]
enabled = true
repo_owner = "myorg"
repo_name = "myrepo"
default_reviewers = ["alice", "bob"]
auto_assign_prs = true

[plugins.jira]
enabled = true
base_url = "https://jira.company.com"
email = "user@company.com"
default_project = "PROJ"
timeout = 30
```

Secrets are stored separately in the secrets manager:

```bash
# Set plugin secrets
titan secret set github.token "ghp_xxxxxxxxxxxx"
titan secret set jira.api_token "xxxxxxxxxxxx"
```

## Plugin Catalog

The `available.py` module maintains a catalog of known plugins for installation:

```python
KNOWN_PLUGINS: List[KnownPlugin] = [
    {
        "name": "git",
        "description": "Provides core Git functionalities for workflows.",
        "package_name": "titan-plugin-git",
        "dependencies": []
    },
    {
        "name": "github",
        "description": "Adds GitHub integration for pull requests and more.",
        "package_name": "titan-plugin-github",
        "dependencies": ["git"]
    },
    {
        "name": "jira",
        "description": "JIRA integration for issue management.",
        "package_name": "titan-plugin-jira",
        "dependencies": []
    },
]
```

This enables commands like:

```bash
# Install a plugin
titan plugin install github

# List available plugins
titan plugin list --available
```

## Error Handling

The plugin system provides robust error handling through custom exceptions:

### PluginLoadError

Raised when a plugin fails to load during discovery:
- Invalid plugin class
- Import errors
- Missing dependencies

### PluginInitializationError

Raised when a plugin fails during initialization:
- Configuration errors
- Authentication failures
- Dependency failures
- Circular dependencies

### Error Tracking

Failed plugins are tracked separately in the registry:

```python
registry = PluginRegistry()
registry.initialize_plugins(config, secrets)

# Check for failures
failed = registry.list_failed()
for name, error in failed.items():
    print(f"Plugin {name} failed: {error}")

# Get successfully loaded plugins
installed = registry.list_installed()
```

## Best Practices

### Plugin Development

1. **Single Responsibility**: Each plugin should focus on one integration or service
2. **Declare Dependencies**: Always declare plugin dependencies explicitly
3. **Graceful Degradation**: Use `is_available()` to indicate when plugin cannot function
4. **Configuration Validation**: Use Pydantic models for type-safe configuration
5. **Error Handling**: Handle errors gracefully and provide helpful messages
6. **Version Semantics**: Follow semantic versioning for compatibility

### Plugin Configuration

1. **Secrets Separation**: Store sensitive data in secrets, not configuration files
2. **Sensible Defaults**: Provide reasonable defaults for optional settings
3. **Documentation**: Document all configuration options with descriptions
4. **Validation**: Validate configuration during initialization

### Plugin Distribution

1. **Entry Points**: Register plugins using the `titan.plugins` entry point group
2. **Dependencies**: Declare Python package dependencies in `setup.py` or `pyproject.toml`
3. **Testing**: Test plugin loading, initialization, and functionality
4. **Documentation**: Provide clear installation and usage documentation

## Advanced Topics

### Conditional Plugin Loading

Plugins can implement complex availability logic:

```python
class MyPlugin(TitanPlugin):
    def is_available(self) -> bool:
        """Check if required tools are installed"""
        try:
            import required_library
            return shutil.which("required_binary") is not None
        except ImportError:
            return False
```

### Dynamic Step Registration

Plugins can dynamically register steps based on configuration:

```python
def get_steps(self) -> Dict[str, Callable]:
    steps = {
        "basic_step": self.basic_step,
    }
    
    if self._config.enable_advanced:
        steps["advanced_step"] = self.advanced_step
    
    return steps
```

### Plugin-Provided Workflows

Plugins can bundle workflow definitions:

```python
from pathlib import Path

@property
def workflows_path(self) -> Optional[Path]:
    """Return path to bundled workflows"""
    return Path(__file__).parent / "workflows"
```

This allows plugins to provide pre-built workflows that users can reference or extend.

## API Reference

### PluginRegistry

```python
class PluginRegistry:
    def __init__(self, discover_on_init: bool = True)
    def discover() -> None
    def initialize_plugins(config: Any, secrets: Any) -> None
    def list_installed() -> List[str]
    def list_discovered() -> List[str]
    def list_failed() -> Dict[str, Exception]
    def get_plugin(name: str) -> Optional[TitanPlugin]
    def reset() -> None
```

### TitanPlugin

See [Plugin Interface](#plugin-interface) section above.

### KnownPlugin

```python
class KnownPlugin(TypedDict):
    name: str
    description: str
    package_name: str
    dependencies: List[str]
```

## Summary

The Titan CLI plugin architecture provides:

- **Extensibility**: Easy to add new integrations and functionality
- **Dependency Management**: Automatic resolution of plugin dependencies
- **Type Safety**: Pydantic models for configuration validation
- **Error Resilience**: Robust error handling and tracking
- **Discovery**: Automatic plugin discovery via entry points
- **Integration**: Seamless workflow system integration

The system is designed to be both developer-friendly (easy to create plugins) and user-friendly (easy to install and configure plugins), making Titan CLI a truly extensible automation framework.
