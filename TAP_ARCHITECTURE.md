# TAP Architecture - Titan Adapter Protocol

**TAP (Titan Adapter Protocol)** is a protocol-driven, framework-agnostic architecture for building AI agent systems with zero coupling.

## 🎯 What is TAP?

TAP is a comprehensive plugin architecture that enables you to:

- ✅ **Connect any AI framework** without hardcoded dependencies
- ✅ **Hot-reload configurations** without restarting applications
- ✅ **Swap frameworks** via configuration files
- ✅ **Extend functionality** through plugins
- ✅ **Validate at compile-time** using Python Protocols
- ✅ **Optimize performance** with lazy loading and caching

## 🏗️ TAP Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                   TAP Manager Layer                      │
│        (Facade - Main API - Lifecycle Management)        │
└──────────────┬──────────────────────────┬────────────────┘
               │                          │
    ┌──────────▼──────────┐    ┌─────────▼──────────┐
    │   TAP Factory       │    │   TAP Loader       │
    │  (DI & Creation)    │    │ (Config Loading)   │
    └──────────┬──────────┘    └─────────┬──────────┘
               │                          │
               └──────────┬───────────────┘
                          │
                ┌─────────▼──────────┐
                │  TAP Registry      │
                │ (Discovery & Mgmt) │
                └─────────┬──────────┘
                          │
                ┌─────────▼──────────┐
                │   TAP Protocol     │
                │   (Interface)      │
                └────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
  ┌─────▼──────┐   ┌─────▼──────┐   ┌─────▼──────┐
  │ Anthropic  │   │   OpenAI   │   │  LangGraph │
  │  Adapter   │   │  Adapter   │   │  Adapter   │
  └────────────┘   └────────────┘   └────────────┘
```

## 🎨 TAP Core Principles

### 1. Protocol-Based Interfaces

TAP uses Python `Protocol` for structural typing instead of inheritance:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class TAPAdapter(Protocol):
    """TAP Protocol for framework adapters."""
    
    @staticmethod
    def convert_tool(titan_tool: TitanTool) -> Any: ...
    
    @staticmethod
    def convert_tools(titan_tools: list[TitanTool]) -> Any: ...
```

**Benefits:**
- ✅ Duck typing with type safety
- ✅ No inheritance required
- ✅ Static type checking (mypy, pyright)
- ✅ Runtime validation

### 2. Configuration-Driven

Everything is configured via YAML/JSON:

```yaml
# config/tap.yml
adapters:
  - name: anthropic
    module: titan.adapters.anthropic.AnthropicAdapter
    metadata:
      provider: Anthropic
      version: 1.0.0
    config:
      model: claude-sonnet-4
```

**Benefits:**
- ✅ Zero code changes to add/remove adapters
- ✅ Environment-specific configs (dev/prod/test)
- ✅ Easy to version control
- ✅ Runtime configuration updates

### 3. Lazy Loading

Components are loaded only when needed:

```python
# Registration (immediate)
registry.register_lazy("anthropic", "titan.adapters.AnthropicAdapter")

# Loading (deferred until first use)
adapter = registry.get("anthropic")  # ← Loaded here
```

**Benefits:**
- ✅ Faster startup time
- ✅ Lower memory footprint
- ✅ Only load what you use

### 4. Dependency Injection

Factory pattern with DI for testability:

```python
factory = TAPFactory()
adapter = factory.create(
    "anthropic",
    model="claude-3",
    temperature=0.7
)
```

**Benefits:**
- ✅ Easy to test (mock dependencies)
- ✅ Flexible configuration
- ✅ Instance caching

### 5. Hot-Reload

Reload configurations without restart:

```python
manager = TAPManager.from_config("config/tap.yml")

# During development...
manager.reload()  # ← Reloads config, clears cache
```

**Benefits:**
- ✅ Fast development cycle
- ✅ No restart needed
- ✅ Safe for production (optional)

## 📊 TAP Components

### 1. TAPProtocol (`protocol.py`)
Defines the interface contract that all adapters must implement.

### 2. TAPRegistry (`registry.py`)
Thread-safe singleton registry for adapter discovery and management.

### 3. TAPLoader (`loader.py`)
Loads configurations from YAML, JSON, environment variables, or Python dicts.

### 4. TAPFactory (`factory.py`)
Creates adapter instances with dependency injection and caching.

### 5. TAPManager (`manager.py`)
Main API facade that orchestrates all components.

## 🚀 Quick Start with TAP

```python
from titan.tap import TAPManager
from titan.core.plugin import PluginManager

# 1. Load tools
pm = PluginManager()
pm.discover_plugins("./plugins")
tools = pm.get_all_tools()

# 2. Create TAP manager
tap = TAPManager.from_config("config/tap.yml")

# 3. Get adapter
adapter = tap.get("anthropic")

# 4. Convert tools
converted_tools = adapter.convert_tools(tools)

# 5. Use with your framework
# ... (framework-specific code)
```

## 🎯 TAP Features

| Feature | Description | Benefit |
|---------|-------------|---------|
| **Protocol Validation** | Runtime & static type checking | Type safety without inheritance |
| **Lazy Loading** | Import only when needed | Fast startup, low memory |
| **Hot-Reload** | Reload config without restart | Fast development |
| **Fallback Strategies** | Automatic failover | High availability |
| **Multi-Source Config** | YAML, JSON, ENV, Dict | Flexible deployment |
| **Thread-Safe** | Lock-based synchronization | Production-ready |
| **Caching** | Instance & config caching | High performance |
| **DI Support** | Constructor injection | Easy testing |

## 📈 TAP Benefits

### For Developers
- 🎨 Clean, intuitive API
- 🔧 Hot-reload for fast iteration
- 📝 Comprehensive documentation
- 🧪 Easy to test with mocks
- 🐛 Clear error messages

### For Operations
- 🔄 Configuration-driven (no code changes)
- 🌍 Environment-aware (dev/prod/test)
- 📊 Observable (comprehensive logging)
- 🔐 Secure (no hardcoded credentials)
- 🚀 Scalable (plugin architecture)

### For Architecture
- 🏗️ Zero coupling between components
- 🔌 Easy to extend with new adapters
- 📦 Clear separation of concerns
- 🎯 Type-safe with Protocols
- 🐍 Pythonic (follows best practices)

## 🎓 Design Patterns in TAP

TAP implements industry-standard design patterns:

- **Protocol Pattern** - Interface definition
- **Singleton Pattern** - Registry (thread-safe)
- **Factory Pattern** - Adapter instantiation
- **Facade Pattern** - Manager simplifies complexity
- **Strategy Pattern** - Fallback strategies
- **Dependency Injection** - Flexible configuration

## 🔍 TAP vs Other Approaches

| Approach | Coupling | Flexibility | Type Safety | Performance |
|----------|----------|-------------|-------------|-------------|
| **Hardcoded** | ❌ High | ❌ Low | ✅ High | ✅ High |
| **ABC Classes** | ⚠️ Medium | ⚠️ Medium | ✅ High | ✅ High |
| **TAP** | ✅ None | ✅ Maximum | ✅ High | ✅ High |

## 📚 Further Reading

- [TitanAgents README](README.md) - Project overview
- [Adapter Documentation](titan/adapters/README_EN.md) - Detailed adapter docs
- [Plugin Architecture](PLUGIN_ARCHITECTURE.md) - Plugin system details
- [Examples](examples/) - Working code examples

## ✅ Status

**TAP Architecture**: ✅ Production-Ready  
**Tests**: ✅ 6/6 Passing  
**Documentation**: ✅ Complete  
**Best Practices**: ✅ Applied

---

**TAP into any framework. Zero coupling. Maximum flexibility.** 🚀
