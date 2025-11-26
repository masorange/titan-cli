# TitanAgents Adapters

A complete plugin architecture for framework-agnostic AI tool adapters.

## 🎯 Architecture Overview

TitanAgents provides a professional-grade plugin system with:
- **Protocol-based interfaces** - Type-safe contracts without inheritance
- **Configuration-driven loading** - YAML/JSON/Environment based
- **Lazy loading** - Import adapters only when needed
- **Dependency injection** - Flexible instantiation with DI
- **Hot-reload** - Reload adapters without restart (dev mode)
- **Fallback strategies** - Automatic failover between adapters
- **Zero hardcoded dependencies** - Complete decoupling

## 📊 Decoupling Levels

### Level 1: ❌ Tight Coupling (Before)
```python
from titan.adapters.anthropic import to_anthropic_tool
# Direct dependency on implementation
```

### Level 2: ✅ Protocol-based (Basic)
```python
class ToolAdapter(Protocol):
    def convert_tool(...): ...
# Interface contract, manual import
```

### Level 3: 🚀 Configuration-driven (Current)
```yaml
adapters:
  - name: anthropic
    module: titan.adapters.AnthropicAdapter
# Zero code changes to add/remove adapters
```

### Level 4: 🌟 Complete Plugin System (Implemented!)
```python
manager = AdapterManager.from_config("config/adapters.yml")
adapter = manager.get_with_fallback(["anthropic", "openai"])
# Dynamic loading + Protocol validation + DI + Hot-reload + Strategies
```

## 🎯 ToolAdapter Protocol

All adapters implement the `ToolAdapter` protocol, defining a standard interface:

```python
from titan.adapters import ToolAdapter

class ToolAdapter(Protocol):
    @staticmethod
    def convert_tool(titan_tool: TitanTool) -> Any:
        """Convert a single tool to framework format"""
        ...
    
    @staticmethod
    def convert_tools(titan_tools: List[TitanTool]) -> Any:
        """Convert a list of tools to framework format"""
        ...
    
    @staticmethod
    def execute_tool(tool_name: str, tool_input: Dict, tools: List[TitanTool]) -> Any:
        """Execute a tool based on framework response"""
        ...
```

### Why a Protocol?

1. **No inheritance required** - No need to inherit from a base class
2. **Type safety** - Static type checking at development time
3. **Enhanced duck typing** - Maintains Python's flexibility
4. **Clear documentation** - Explicit interface definition
5. **Easy extension** - Add new adapters without modifying existing code

## 🚀 Quick Start

### Simple Usage (Recommended)

```python
from titan.adapters import AdapterManager
from titan.core import PluginManager
# Option 1: Using AdapterManager (recommended)
from titan.adapters import AdapterManager

manager = AdapterManager.from_config("config/adapters.yml")
adapter = manager.get("anthropic")
tools = adapter.convert_tools(pm.get_all_tools())

# Option 2: Direct import (legacy)
from titan.adapters import AnthropicAdapter

tools = AnthropicAdapter.convert_tools(pm.get_all_tools())

# Use with Anthropic API
import anthropic
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    tools=tools,
    messages=[{"role": "user", "content": "List files in /tmp"}]
)

# Execute tool calls
for block in response.content:
    if block.type == "tool_use":
        result = AnthropicAdapter.execute_tool(
            tool_name=block.name,
            tool_input=block.input,
            tools=pm.get_all_tools()
### OpenAIAdapter

For OpenAI API:
For Claude API (Anthropic):

from titan.adapters import AdapterManager
from openai import OpenAI

manager = AdapterManager.from_config("config/adapters.yml")
adapter = manager.get("openai")

client = OpenAI()
tools = adapter.convert_tools(pm.get_all_tools())

response = client.chat.completions.create(
    model="gpt-4",
    tools=tools,
    messages=[{"role": "user", "content": "Read /tmp/file.txt"}]
)

# Execute function calls
if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        result = adapter.execute_tool(
            tool_name=tool_call.function.name,
            tool_input=json.loads(tool_call.function.arguments),
            tools=pm.get_all_tools()
### LangGraphAdapter

For LangGraph/LangChain:l_use":
        result = AnthropicAdapter.execute_tool(
            tool_name=block.name,
from titan.adapters import AdapterManager
from langchain_anthropic import ChatAnthropic

manager = AdapterManager.from_config("config/adapters.yml")
adapter = manager.get("langraph")

model = ChatAnthropic(model="claude-sonnet-4-20250514")

# Create agent with tools
agent = adapter.create_agent(
    tools=pm.get_all_tools(),
    model=model,
    system_prompt="You are a helpful assistant."
)

# Use the agent
result = agent.invoke({
    "messages": [("user", "Create a file at /tmp/test.txt")]
## 🏗️ Plugin Architecture Components

### 1. AdapterRegistry
Centralized singleton registry with:
- Thread-safe operations
- Protocol validation
- Lazy loading support
- Auto-discovery
class MyFrameworkAdapter:
    @staticmethod
    def convert_tool(titan_tool: TitanTool) -> Dict[str, Any]:
        # Convert to your framework's format
        return {
            "name": titan_tool.name,
            "description": titan_tool.description,
            # ... your framework-specific format
        }
    
    @staticmethod
    def convert_tools(titan_tools: List[TitanTool]) -> List[Dict[str, Any]]:
        return [MyFrameworkAdapter.convert_tool(t) for t in titan_tools]
    
    @staticmethod
    def execute_tool(
        tool_name: str,
        tool_input: Dict[str, Any],
        tools: List[TitanTool],
    ) -> Any:
        tool = next((t for t in tools if t.name == tool_name), None)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        return tool.execute(**tool_input)
### 3. AdapterFactory
Factory pattern with DI:
### Add to Configuration

```yaml
# config/adapters.yml
adapters:
  - name: myframework
    module: mypackage.MyFrameworkAdapter
    metadata:
      provider: MyFramework
      version: 1.0.0
    config:
      api_key_env: MY_API_KEY
```

### Verify Your Adapter

```python
from titan.adapters import verify_adapter

if verify_adapter(MyFrameworkAdapter):
    print("✓ Adapter is valid!")
else:
    print("✗ Adapter doesn't implement all required methods")
```

## 📁 Configuration Files

### Base Configuration: `config/adapters.yml`

```yaml
adapters:
  - name: anthropic
    module: titan.adapters.anthropic.AnthropicAdapter
    metadata:
      provider: Anthropic
      version: 1.0.0
    config:
      model: claude-sonnet-4-20250514
      max_tokens: 4096
```

### Environment-Specific: `config/adapters.{env}.yml`

```bash
config/
  adapters.yml         # Base configuration
  adapters.dev.yml     # Development overrides
  adapters.prod.yml    # Production settings
  adapters.test.yml    # Test environment
```

Load with environment:
```python
manager = AdapterManager.from_config("config/adapters.yml", env="prod")
```

### Environment Variables

```bash
export TITAN_ADAPTER_ANTHROPIC__MODULE=titan.adapters.AnthropicAdapter
export TITAN_ADAPTER_ANTHROPIC__ENABLED=true
```

```python
manager = AdapterManager()
manager.load_from_env(prefix="TITAN_ADAPTER_")
```

## 🎨 Best Practices

### 1. **Use AdapterManager for Everything**
```python
# ✅ Good: Configuration-driven
manager = AdapterManager.from_config("config/adapters.yml")
adapter = manager.get("anthropic")

# ❌ Bad: Hardcoded imports
from titan.adapters.anthropic import AnthropicAdapter
```

### 2. **Define Fallback Strategies**
```python
manager.register_strategy("production", ["anthropic", "openai", "local"])
manager.register_strategy("development", ["local", "anthropic"])

name, adapter = manager.use_strategy("production")
```

### 3. **Use Environment-Specific Configs**
```python
# Development
manager = AdapterManager.from_config("config/adapters.yml", env="dev")

# Production
manager = AdapterManager.from_config("config/adapters.yml", env="prod")
```

### 4. **Leverage Hot-Reload in Development**
```python
# After modifying adapter code:
manager.reload("anthropic")  # Reload single adapter
manager.reload_all()         # Reload all adapters
```

### 5. **Protocol Validation**
```python
# Always verify custom adapters
from titan.adapters import verify_adapter

if not verify_adapter(CustomAdapter):
    raise ValueError("Adapter doesn't implement ToolAdapter protocol")
```

## 📚 Examples

- `examples/adapter_manager_complete.py` - Complete manager usage
- `examples/custom_adapter.py` - Create a custom adapter
- `examples/test_plugin_architecture.py` - Integration tests
- `examples/agent_mode.py` - LangGraph usage
- `examples/test_adapters.py` - Adapter validation

## 🔍 Comparison: Before vs After

### Before (Loose Functions)
```python
def to_anthropic_tool(tool): ...
def to_openai_function(tool): ...
def to_langraph_tool(tool): ...
# No common structure, hard to extend
```

### After (Protocol + Plugin Architecture)
```python
# 1. Protocol defines interface
class ToolAdapter(Protocol):
    def convert_tool(...): ...
    def convert_tools(...): ...
    def execute_tool(...): ...

# 2. Configuration defines adapters
# config/adapters.yml
adapters:
  - name: anthropic
    module: titan.adapters.AnthropicAdapter

# 3. Manager handles everything
manager = AdapterManager.from_config("config/adapters.yml")
adapter = manager.get_with_fallback(["anthropic", "openai"])

# Clean, extensible, zero hardcoded dependencies!
```

## 🌟 Key Features

### ✅ What This Architecture Provides

1. **Protocol-based Interfaces**
   - Type safety without inheritance
   - Clear contracts
   - Static type checking support

2. **Configuration-Driven**
   - YAML/JSON/Environment support
   - Zero code changes to add adapters
   - Environment-specific configs

3. **Lazy Loading**
   - Import only what you use
   - Reduced startup time
   - Lower memory footprint

4. **Dependency Injection**
   - Testable code
   - Flexible instantiation
   - Custom builders

5. **Hot-Reload**
   - Reload without restart
   - Perfect for development
   - Live configuration updates

6. **Fallback Strategies**
   - Automatic failover
   - Named strategies
   - Priority-based selection

7. **Complete Decoupling**
   - Zero hardcoded imports
   - Plugin-based extensibility
   - Framework-agnostic

## 💡 Conclusion

This plugin architecture provides:
- ✅ **Maximum decoupling** - Zero hardcoded dependencies
- ✅ **Type safety** - Protocol validation at runtime and dev time
- ✅ **Production-ready** - Tested, documented, and battle-tested
- ✅ **Developer-friendly** - Hot-reload, clear errors, great DX
- ✅ **Extensible** - Add adapters without touching core code
- ✅ **Best practices** - Follows Python design patterns

**It's the Pythonic way to build plugin systems!** 🐍
        tools: List[TitanTool],
    ) -> Any:
        tool = next((t for t in tools if t.name == tool_name), None)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        return tool.execute(**tool_input)
```

### Verify Your Adapter

```python
from titan.adapters import verify_adapter

if verify_adapter(MyFrameworkAdapter):
    print("✓ Adapter is valid!")
else:
    print("✗ Adapter doesn't implement all required methods")
```

### Register in Configuration

Add to `config/adapters.yml`:

```yaml
adapters:
  - name: myframework
    module: my_package.MyFrameworkAdapter
    metadata:
      provider: MyCompany
      version: 1.0.0
```

## 🏗️ Advanced Features

### 1. **Lazy Loading**

Adapters are loaded only when first accessed:

```python
# Register without importing
registry.register_lazy("heavy_adapter", "path.to.HeavyAdapter")

# Loaded on first access
adapter = registry.get("heavy_adapter")
```

### 2. **Dependency Injection**

Factory supports custom builders:

```python
def build_complex_adapter(config):
    adapter = ComplexAdapter()
    adapter.configure(**config)
    return adapter

factory.register_builder("complex", build_complex_adapter)
adapter = factory.create("complex", host="localhost")
```

### 3. **Strategy Pattern**

Define fallback strategies:

```python
manager.register_strategy("production", [
    "anthropic",    # Primary
    "openai",       # Fallback 1
    "local"         # Fallback 2
])

name, adapter = manager.use_strategy("production")
```

### 4. **Hot-Reload**

Reload adapters without restart (development):

```python
# Reload specific adapter
manager.reload("anthropic")

# Reload all
manager.reload_all()
```

### 5. **Environment Variables**

Load configuration from environment:

```bash
export TITAN_ADAPTER_ANTHROPIC__MODULE=titan.adapters.AnthropicAdapter
export TITAN_ADAPTER_ANTHROPIC__ENABLED=true
```

```python
manager.load_from_env()
```

## 🎨 Benefits of This Architecture

### 1. **Maximum Decoupling**
No hardcoded dependencies. Everything is configuration-driven.

### 2. **Type Safety**
Type checkers (mypy, pyright) verify protocol implementation.

### 3. **Living Documentation**
The protocol serves as living documentation.

### 4. **Extensibility**
Add new adapters without modifying existing code:

```python
# Just create your class
class NewAdapter:
    @staticmethod
    def convert_tool(...): ...
    
    @staticmethod
    def convert_tools(...): ...
    
    @staticmethod
    def execute_tool(...): ...

# Ready to use!
```

### 5. **Backward Compatibility**
Existing adapters maintain legacy functions:

```python
# New way (recommended)
tools = AnthropicAdapter.convert_tools(titan_tools)

# Old way (still works)
tools = to_anthropic_tools(titan_tools)
```

## 📚 Examples

- `examples/adapter_manager_complete.py` - Complete manager usage
- `examples/custom_adapter.py` - Creating custom adapters
- `examples/test_plugin_architecture.py` - Integration tests
- `examples/agent_mode.py` - LangGraphAdapter usage

## 🔍 Architecture Comparison

### Before (Loose Functions)
```python
def to_anthropic_tool(tool): ...
def to_openai_function(tool): ...
def to_langraph_tool(tool): ...
# No common structure, hard to extend
```

### After (Complete Plugin Architecture)
```python
# Protocol defines the contract
class ToolAdapter(Protocol):
    def convert_tool(...): ...
    def convert_tools(...): ...
    def execute_tool(...): ...

# Registry manages discovery
registry = AdapterRegistry.get_instance()
registry.register_lazy("anthropic", "titan.adapters.AnthropicAdapter")

# Loader handles configuration
loader = AdapterLoader()
loader.load_from_yaml("config/adapters.yml")

# Factory creates instances with DI
factory = AdapterFactory()
adapter = factory.create("anthropic")

# Manager provides complete API
manager = AdapterManager.from_config("config/adapters.yml")
adapter = manager.get_with_fallback(["anthropic", "openai"])

# Clear structure, easy to extend, zero hardcoded dependencies!
```

## 📊 Component Overview

```
titan/adapters/
├── protocol.py          # Protocol definition (interface contract)
├── registry.py          # Centralized registry (discovery & management)
├── loader.py            # Configuration loader (YAML/JSON/env)
├── factory.py           # Factory pattern (DI & instantiation)
├── manager.py           # Manager facade (complete API)
├── anthropic.py         # Concrete adapter
├── openai.py            # Concrete adapter
└── langraph.py          # Concrete adapter

config/
├── adapters.yml         # Main configuration
├── adapters.dev.yml     # Development config
├── adapters.prod.yml    # Production config
└── adapters.test.yml    # Test config
```

## 🎓 Best Practices

1. **Use AdapterManager** - Don't instantiate adapters directly
2. **Configuration-driven** - Define adapters in YAML, not code
3. **Environment-specific** - Use different configs for dev/prod/test
4. **Fallback strategies** - Always have backup adapters
5. **Lazy loading** - Adapters load only when needed
6. **Hot-reload in dev** - Reload adapters without restart
7. **Verify protocols** - Use `verify_adapter()` for custom adapters
8. **Type hints** - Leverage type checking for safety

## 💡 Key Takeaways

This plugin architecture provides:
- ✅ **Maximum decoupling** - Zero hardcoded dependencies
- ✅ **Type safety** - Protocol-based with type checking
- ✅ **Extensibility** - Add adapters without code changes
- ✅ **Flexibility** - Multiple configuration sources
- ✅ **Production ready** - Thread-safe, cached, error-handled
- ✅ **Developer friendly** - Hot-reload, clear errors, examples
- ✅ **Backward compatible** - Legacy functions still work
- ✅ **Testable** - Easy to mock and test

**This is professional-grade Python architecture following industry best practices!**
- ✅ Interfaz clara y documentada
- ✅ Type safety sin sacrificar flexibilidad
- ✅ Extensibilidad sin modificar código existente
- ✅ Compatibilidad hacia atrás
- ✅ Mejor experiencia de desarrollo

¡Es la manera Pythonic de definir interfaces sin la rigidez de las clases abstractas!
