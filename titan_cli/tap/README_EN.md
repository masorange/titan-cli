# TitanAgents Adapters - Complete Plugin Architecture

A production-ready plugin architecture for AI framework adapters with configuration-based loading, dependency injection, hot-reload, and enterprise features.

## 🚀 Quick Start

```python
from titan.adapters import AdapterManager

# Load from configuration
manager = AdapterManager.from_config("config/adapters.yml")

# Get adapter
adapter = manager.get("anthropic")

# Convert tools
tools = adapter.convert_tools(titan_tools)
```

## 📐 Architecture Overview

The system follows best practices with multiple decoupled layers:

```
┌─────────────────────────────────────────────────────────┐
│                   AdapterManager                         │
│        (Facade - Main API - Lifecycle Management)        │
└──────────────┬──────────────────────────┬────────────────┘
               │                          │
    ┌──────────▼──────────┐    ┌─────────▼──────────┐
    │   AdapterFactory    │    │   AdapterLoader    │
    │  (DI & Creation)    │    │ (Config Loading)   │
    └──────────┬──────────┘    └─────────┬──────────┘
               │                          │
               └──────────┬───────────────┘
                          │
                ┌─────────▼──────────┐
                │  AdapterRegistry   │
                │ (Discovery & Mgmt) │
                └─────────┬──────────┘
                          │
                ┌─────────▼──────────┐
                │   ToolAdapter      │
                │   (Protocol)       │
                └────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
  ┌─────▼──────┐   ┌─────▼──────┐   ┌─────▼──────┐
  │ Anthropic  │   │   OpenAI   │   │  LangGraph │
  │  Adapter   │   │  Adapter   │   │  Adapter   │
  └────────────┘   └────────────┘   └────────────┘
```

## 🎯 Core Components

### 1. ToolAdapter Protocol

Defines the contract that all adapters must implement:

```python
from __future__ import annotations
from typing import Protocol, Any

class ToolAdapter(Protocol):
    @staticmethod
    def convert_tool(titan_tool: TitanTool) -> Any:
        """Convert a single tool"""
        ...

    @staticmethod
    def convert_tools(titan_tools: list[TitanTool]) -> Any:
        """Convert multiple tools"""
        ...

    @staticmethod
    def execute_tool(
        tool_name: str,
        tool_input: dict[str, Any],
        tools: list[TitanTool]
    ) -> Any:
        """Execute a tool"""
        ...
```

**New! Enhanced Protocol Validation:**

```python
from titan.adapters.protocol import (
    verify_adapter,
    is_valid_adapter,
    get_adapter_info
)

# Basic validation
if verify_adapter(MyAdapter):
    print("✓ Adapter has all required methods")

# Strict validation (checks method signatures)
if verify_adapter(MyAdapter, strict=True):
    print("✓ Adapter fully complies with protocol")

# Universal validation (works with classes and instances)
if is_valid_adapter(MyAdapter):
    print("✓ Valid adapter class")

adapter = MyAdapter()
if is_valid_adapter(adapter):
    print("✓ Valid adapter instance")

# Detailed introspection
info = get_adapter_info(MyAdapter)
print(f"Valid: {info['is_valid']}")
print(f"Strict Valid: {info['is_strict_valid']}")
print(f"Methods: {info['methods']}")
```

**Why Protocol?**
- ✅ No mandatory inheritance
- ✅ Type safety at development time
- ✅ Duck typing with type checking
- ✅ Clear interface documentation
- ✅ Easy extension without code modification

### 2. AdapterRegistry

Centralized registry for adapter discovery and management:

```python
from titan.adapters import get_registry

registry = get_registry()

# Manual registration
registry.register("myadapter", MyAdapter)

# Lazy registration (loaded on first access)
registry.register_lazy("heavy", "path.to.HeavyAdapter")

# Auto-discovery
registry.auto_discover("titan.adapters")

# Get adapter
adapter = registry.get("myadapter")
```

**Features:**
- Thread-safe singleton
- Lazy loading support
- Protocol validation
- Auto-discovery
- Metadata management

### 3. AdapterLoader

Loads adapters from multiple configuration sources:

```python
from titan.adapters import AdapterLoader

loader = AdapterLoader()

# From YAML
loader.load_from_yaml("config/adapters.yml")

# From JSON
loader.load_from_json("config/adapters.json")

# From environment variables
loader.load_from_env()

# From dictionary
config = {"adapters": [...]}
loader.load_from_dict(config)
```

**Features:**
- YAML/JSON support
- Environment variables
- Environment-specific configs
- Schema validation
- Clear error messages

### 4. AdapterFactory

Creates adapter instances with dependency injection:

```python
from titan.adapters import AdapterFactory

factory = AdapterFactory()

# Create adapter
adapter = factory.create("anthropic")

# With configuration
adapter = factory.create("anthropic", model="claude-3")

# With fallback
name, adapter = factory.create_with_fallback(["anthropic", "openai"])

# Custom builder
def build_complex(config):
    adapter = ComplexAdapter()
    adapter.configure(**config)
    return adapter

factory.register_builder("complex", build_complex)
```

**Features:**
- Dependency injection
- Instance caching
- Custom builders
- Fallback support
- Stateless/stateful detection

### 5. AdapterManager (Main Interface)

Complete lifecycle management - **This is what you should use!**

```python
from titan.adapters import AdapterManager

# Load from config with environment
manager = AdapterManager.from_config("config/adapters.yml", env="prod")

# Get adapter
adapter = manager.get("anthropic")

# With fallback
name, adapter = manager.get_with_fallback(["anthropic", "openai"])

# Named strategies
manager.register_strategy("production", ["anthropic", "openai"])
name, adapter = manager.use_strategy("production")

# Hot-reload (development)
manager.reload("anthropic")
manager.reload_all()

# List and check
adapters = manager.list_adapters()
available = manager.is_available("anthropic")
metadata = manager.get_metadata("anthropic")
```

**Features:**
- Configuration-based loading
- Lazy instantiation
- Fallback strategies
- Named strategies
- Hot-reload
- Environment-specific configs
- Metadata management

## 📝 Configuration Files

### Main Configuration (`config/adapters.yml`)

```yaml
adapters:
  - name: anthropic
    module: titan.adapters.anthropic.AnthropicAdapter
    metadata:
      provider: Anthropic
      version: 1.0.0
      description: Adapter for Anthropic's Claude API
    config:
      model: claude-sonnet-4-20250514
      max_tokens: 4096
      temperature: 0.7
  
  - name: openai
    module: titan.adapters.openai.OpenAIAdapter
    metadata:
      provider: OpenAI
      version: 1.0.0
    config:
      model: gpt-4
      temperature: 0.7
```

### Environment-Specific Configs

- **`config/adapters.dev.yml`** - Development (verbose, debugging)
- **`config/adapters.prod.yml`** - Production (optimized, reliable)
- **`config/adapters.test.yml`** - Testing (fast, deterministic)

## 📦 Built-in Adapters

### AnthropicAdapter

```python
from titan.adapters import AnthropicAdapter

tools = AnthropicAdapter.convert_tools(titan_tools)

# Use with Anthropic API
import anthropic
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    tools=tools,
    messages=[{"role": "user", "content": "Task"}]
)

# Execute tool calls
for block in response.content:
    if block.type == "tool_use":
        result = AnthropicAdapter.execute_tool(
            tool_name=block.name,
            tool_input=block.input,
            tools=titan_tools
        )
```

### OpenAIAdapter

```python
from titan.adapters import OpenAIAdapter
from openai import OpenAI

client = OpenAI()
tools = OpenAIAdapter.convert_tools(titan_tools)

response = client.chat.completions.create(
    model="gpt-4",
    tools=tools,
    messages=[{"role": "user", "content": "Task"}]
)
```

### LangGraphAdapter

```python
from titan.adapters import LangGraphAdapter
from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(model="claude-sonnet-4-20250514")
agent = LangGraphAdapter.create_agent(
    tools=titan_tools,
    model=model,
    system_prompt="You are a helpful assistant."
)

result = agent.invoke({"messages": [("user", "Task")]})
```

## 🔧 Creating Custom Adapters

### 1. Implement the Protocol (Modern Python 3.10+)

```python
from __future__ import annotations

from typing import Any
from titan.core import TitanTool

class MyFrameworkAdapter:
    """
    Custom adapter for MyFramework.

    Uses modern Python 3.10+ type hints (dict, list instead of Dict, List).
    """

    @staticmethod
    def convert_tool(titan_tool: TitanTool) -> dict[str, Any]:
        """Convert a single TitanTool to MyFramework format."""
        return {
            "name": titan_tool.name,
            "description": titan_tool.description,
            # Your framework-specific format
        }

    @staticmethod
    def convert_tools(titan_tools: list[TitanTool]) -> list[dict[str, Any]]:
        """Convert multiple TitanTools to MyFramework format."""
        return [MyFrameworkAdapter.convert_tool(t) for t in titan_tools]

    @staticmethod
    def execute_tool(
        tool_name: str,
        tool_input: dict[str, Any],
        tools: list[TitanTool],
    ) -> Any:
        """Execute a tool from MyFramework's response."""
        tool = next((t for t in tools if t.name == tool_name), None)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        return tool.execute(**tool_input)
```

### 2. Verify Protocol Implementation (With Strict Mode)

```python
from titan.adapters.protocol import (
    verify_adapter,
    is_valid_adapter,
    get_adapter_info
)

# Basic validation
if verify_adapter(MyFrameworkAdapter):
    print("✓ Adapter has all required methods")

# Strict validation (checks parameter names and signatures)
if verify_adapter(MyFrameworkAdapter, strict=True):
    print("✓ Adapter fully complies with protocol")
else:
    print("✗ Adapter has wrong method signatures")

# Get detailed information
info = get_adapter_info(MyFrameworkAdapter)
if not info['is_strict_valid']:
    print("Issues found:")
    for method_name, method_info in info['methods'].items():
        if not method_info.get('exists'):
            print(f"  - Missing method: {method_name}")
        elif 'error' in method_info:
            print(f"  - Error in {method_name}: {method_info['error']}")
```

### 3. Register in Configuration

Add to `config/adapters.yml`:

```yaml
adapters:
  - name: myframework
    module: my_package.MyFrameworkAdapter
    metadata:
      provider: MyCompany
      version: 1.0.0
```

## 🎨 Advanced Features

### Fallback Strategies

```python
# Try multiple adapters in order
name, adapter = manager.get_with_fallback([
    "anthropic",  # Try first
    "openai",     # Then this
    "local"       # Finally this
])
```

### Named Strategies

```python
# Define strategies
manager.register_strategy("production", ["anthropic", "openai"])
manager.register_strategy("development", ["local", "anthropic"])
manager.register_strategy("testing", ["mock"])

# Use strategy
name, adapter = manager.use_strategy("production")
```

### Hot-Reload (Development)

```python
# Reload specific adapter
manager.reload("anthropic")

# Reload all adapters
manager.reload_all()
```

### Environment Variables

```bash
export TITAN_ADAPTER_ANTHROPIC__MODULE=titan.adapters.AnthropicAdapter
export TITAN_ADAPTER_ANTHROPIC__ENABLED=true
export TITAN_ADAPTER_OPENAI__MODULE=titan.adapters.OpenAIAdapter
```

```python
manager.load_from_env()
```

### Custom Builders

```python
def build_stateful_adapter(config):
    adapter = StatefulAdapter()
    adapter.connect(host=config.get("host"))
    adapter.authenticate(api_key=config.get("api_key"))
    return adapter

factory.register_builder("stateful", build_stateful_adapter)
adapter = factory.create("stateful", host="api.example.com")
```

## 📚 Examples

| Example | Description |
|---------|-------------|
| `examples/adapter_manager_complete.py` | Complete manager usage with all features |
| `examples/custom_adapter.py` | Creating and using custom adapters |
| `examples/test_plugin_architecture.py` | Integration tests for the system |
| `examples/test_adapters.py` | Protocol verification tests |
| `examples/agent_mode.py` | LangGraph adapter usage |

## 🎓 Best Practices

1. **Use AdapterManager** - Don't instantiate adapters directly
   ```python
   # ✅ Good
   manager = AdapterManager.from_config("config/adapters.yml")
   adapter = manager.get("anthropic")
   
   # ❌ Avoid
   from titan.adapters.anthropic import AnthropicAdapter
   adapter = AnthropicAdapter()
   ```

2. **Configuration-Driven** - Define adapters in YAML, not code
   ```yaml
   # config/adapters.yml
   adapters:
     - name: my_adapter
       module: path.to.MyAdapter
   ```

3. **Environment-Specific** - Use different configs per environment
   ```python
   # Development
   manager = AdapterManager.from_config("config/adapters.yml", env="dev")
   
   # Production
   manager = AdapterManager.from_config("config/adapters.yml", env="prod")
   ```

4. **Fallback Strategies** - Always have backup options
   ```python
   name, adapter = manager.get_with_fallback(["primary", "secondary", "tertiary"])
   ```

5. **Lazy Loading** - Adapters load only when needed (automatic)

6. **Hot-Reload in Dev** - Reload without restart
   ```python
   if os.getenv("ENV") == "development":
       manager.reload("adapter_name")
   ```

7. **Verify Custom Adapters** - Use protocol verification
   ```python
   assert verify_adapter(MyAdapter), "Invalid adapter implementation"
   ```

## 🔍 Architecture Benefits

### Before (Functions)

```python
# Hardcoded imports
from titan.adapters.anthropic import to_anthropic_tool

# No structure
tools = [to_anthropic_tool(t) for t in titan_tools]

# Hard to extend, coupled, no config
```

### After (Plugin Architecture)

```python
# Configuration-driven
manager = AdapterManager.from_config("config/adapters.yml")

# Clean API
adapter = manager.get("anthropic")
tools = adapter.convert_tools(titan_tools)

# With fallback
name, adapter = manager.get_with_fallback(["anthropic", "openai"])

# Zero hardcoded dependencies!
```

## 💡 Key Achievements

✅ **Maximum Decoupling** - Zero hardcoded dependencies  
✅ **Type Safety** - Protocol-based with type checking  
✅ **Extensibility** - Add adapters without code changes  
✅ **Flexibility** - Multiple configuration sources  
✅ **Production Ready** - Thread-safe, cached, error-handled  
✅ **Developer Friendly** - Hot-reload, clear errors, examples  
✅ **Backward Compatible** - Legacy functions still work  
✅ **Testable** - Easy to mock and test  
✅ **Enterprise Grade** - Follows industry best practices  

## 🧪 Testing

### Run Unit Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/adapters/test_protocol.py -v
pytest tests/adapters/test_factory.py -v

# Run with coverage
pytest tests/ --cov=titan.adapters --cov-report=html
```

### Test Suite Coverage

**Protocol Tests** (`tests/adapters/test_protocol.py`):
- ✅ `verify_adapter()` - basic and strict modes
- ✅ `is_valid_adapter()` - classes and instances
- ✅ `get_adapter_info()` - detailed introspection
- ✅ `_verify_method_signatures()` - signature validation
- ✅ Protocol runtime checking
- ✅ Invalid adapter detection

**Factory Tests** (`tests/adapters/test_factory.py`):
- ✅ Stateless adapter creation
- ✅ Stateful adapter instantiation
- ✅ Cache key generation (with MD5 hash)
- ✅ Custom builder registration
- ✅ Fallback strategies
- ✅ Cache management
- ✅ Error handling

### Integration Tests

Run the complete integration test suite:

```bash
python examples/test_plugin_architecture.py
```

All integration tests pass:
- ✅ Registry operations
- ✅ Loader (YAML/JSON/env/dict)
- ✅ Factory (creation, caching, fallback)
- ✅ Manager (complete workflow)
- ✅ End-to-end with real tools
- ✅ Environment configurations

### Example Test

```python
from titan.adapters.protocol import verify_adapter, get_adapter_info
from titan.adapters import AdapterManager

def test_custom_adapter():
    """Test a custom adapter implementation."""
    # Verify protocol compliance
    assert verify_adapter(MyAdapter, strict=True)

    # Check adapter info
    info = get_adapter_info(MyAdapter)
    assert info['is_strict_valid']
    assert all(m['is_static'] for m in info['methods'].values())

    # Test with manager
    manager = AdapterManager()
    manager.registry.register("myAdapter", MyAdapter)

    adapter = manager.get("myAdapter")
    assert adapter is MyAdapter
```

## 📖 API Reference

### Protocol Validation Functions (New!)

```python
from titan.adapters.protocol import (
    verify_adapter,
    is_valid_adapter,
    get_adapter_info,
)

# Verify adapter implementation
verify_adapter(adapter_class: type, strict: bool = False) -> bool

# Check if object is valid adapter (class or instance)
is_valid_adapter(obj: Any) -> bool

# Get detailed adapter information
get_adapter_info(adapter_class: type) -> dict[str, Any]
# Returns:
# {
#     'is_valid': bool,
#     'is_strict_valid': bool,
#     'class_name': str,
#     'module': str,
#     'methods': {
#         'convert_tool': {
#             'exists': bool,
#             'is_static': bool,
#             'signature': str,
#             'parameters': list[str]
#         },
#         ...
#     }
# }
```

### AdapterManager

```python
manager = AdapterManager.from_config(config_path, env=None)
manager.get(name, use_cache=None, **config) -> Any
manager.get_with_fallback(names: list[str], **config) -> tuple[str, Any]
manager.list_adapters() -> list[str]
manager.is_available(name: str) -> bool
manager.get_metadata(name: str) -> dict[str, Any]
manager.reload(name: str) -> None
manager.reload_all() -> None
manager.register_strategy(name: str, adapters: list[str]) -> None
manager.use_strategy(name: str, **config) -> tuple[str, Any]
```

### AdapterRegistry

```python
registry = get_registry()
registry.register(name: str, adapter_class: type, metadata: dict = None) -> None
registry.register_lazy(name: str, module_path: str, metadata: dict = None) -> None
registry.get(name: str) -> type
registry.is_registered(name: str) -> bool
registry.list_adapters() -> list[str]
registry.get_metadata(name: str) -> dict
registry.auto_discover(package: str) -> int
```

### AdapterLoader

```python
loader = AdapterLoader()
loader.load_from_yaml(filepath, env=None) -> int
loader.load_from_json(filepath, env=None) -> int
loader.load_from_dict(config: dict[str, Any]) -> int
loader.load_from_env(prefix="TITAN_ADAPTER_") -> int
```

### AdapterFactory

```python
factory = AdapterFactory()
factory.create(name: str, use_cache: bool = None, **config) -> Any
factory.create_with_fallback(names: list[str], **config) -> tuple[str, Any]
factory.register_builder(name: str, builder_func: Callable) -> None
factory.clear_cache(name: str = None) -> None
```

## 🚀 Getting Started

1. **Install dependencies:**
   ```bash
   pip install pyyaml  # For YAML configuration
   ```

2. **Create configuration:**
   ```bash
   mkdir -p config
   # Use example configs or create your own
   ```

3. **Use in your code:**
   ```python
   from titan.adapters import AdapterManager
   
   manager = AdapterManager.from_config("config/adapters.yml")
   adapter = manager.get("anthropic")
   tools = adapter.convert_tools(your_tools)
   ```

## 🎯 Conclusion

This is a **professional-grade plugin architecture** that provides:
- Complete decoupling through configuration
- Type-safe interfaces with protocols
- Flexible instantiation with DI
- Production-ready lifecycle management
- Developer-friendly features (hot-reload, fallback, etc.)

**Following Python and software engineering best practices!**
