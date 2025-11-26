"""
Example: Using the complete Adapter Manager system.

This demonstrates the new plugin architecture with:
- Configuration-based loading
- Lazy instantiation
- Fallback strategies
- Hot-reload capabilities
"""

from titan.core import PluginManager
from titan.adapters import AdapterManager
from plugins.filesystem import FileSystemPlugin


def main():
    print("=" * 70)
    print("TitanAgents - Complete Adapter Manager Example")
    print("=" * 70)
    print()
    
    # ========================================================================
    # 1. Initialize Plugin Manager (for tools)
    # ========================================================================
    print("📦 Step 1: Setting up tool plugins...")
    pm = PluginManager()
    pm.register_plugin(FileSystemPlugin())
    tools = pm.get_all_tools()
    print(f"✓ Loaded {len(tools)} tools")
    print()
    
    # ========================================================================
    # 2. Load Adapters from Configuration
    # ========================================================================
    print("🔧 Step 2: Loading adapters from configuration...")
    
    # Option A: Load with environment selection
    manager = AdapterManager.from_config("config/adapters.yml", env="dev")
    
    # Option B: Manual loading
    # manager = AdapterManager()
    # manager.load_config("config/adapters.yml")
    
    print(f"✓ Available adapters: {manager.list_adapters()}")
    print()
    
    # ========================================================================
    # 3. Get and Use an Adapter
    # ========================================================================
    print("🎯 Step 3: Using a specific adapter...")
    
    # Get adapter (loaded lazily on first access)
    anthropic = manager.get("anthropic")
    print(f"✓ Got adapter: {anthropic.__class__.__name__}")
    
    # Convert tools
    adapted_tools = anthropic.convert_tools(tools)
    print(f"✓ Converted {len(adapted_tools)} tools to Anthropic format")
    print()
    
    # ========================================================================
    # 4. Use Fallback Strategy
    # ========================================================================
    print("🔄 Step 4: Using fallback strategy...")
    
    # Try multiple adapters in order
    try:
        adapter_name, adapter = manager.get_with_fallback([
            "anthropic",
            "openai",
            "langraph"
        ])
        print(f"✓ Using adapter: {adapter_name}")
    except RuntimeError as e:
        print(f"✗ All adapters failed: {e}")
    print()
    
    # ========================================================================
    # 5. Register and Use Custom Strategy
    # ========================================================================
    print("📋 Step 5: Using named strategies...")
    
    # Register strategies for different scenarios
    manager.register_strategy("production", ["anthropic", "openai"])
    manager.register_strategy("development", ["langraph", "anthropic"])
    manager.register_strategy("testing", ["openai"])
    
    # Use a strategy
    strategy_name, adapter = manager.use_strategy("production")
    print(f"✓ Production strategy selected: {strategy_name}")
    print()
    
    # ========================================================================
    # 6. View Adapter Metadata
    # ========================================================================
    print("ℹ️  Step 6: Viewing adapter metadata...")
    
    for adapter_name in manager.list_adapters():
        metadata = manager.get_metadata(adapter_name)
        provider = metadata.get("provider", "Unknown")
        version = metadata.get("version", "N/A")
        print(f"  • {adapter_name}: {provider} v{version}")
    print()
    
    # ========================================================================
    # 7. Hot Reload (Development Feature)
    # ========================================================================
    print("🔥 Step 7: Hot-reload capability...")
    print("  (Useful for development when you modify adapter code)")
    
    # Reload a specific adapter
    manager.reload("anthropic")
    print("  ✓ Reloaded anthropic adapter")
    
    # Or reload all
    # manager.reload_all()
    print()
    
    # ========================================================================
    # 8. Execute a Tool Through an Adapter
    # ========================================================================
    print("⚡ Step 8: Executing tool through adapter...")
    
    result = anthropic.execute_tool(
        tool_name="write_file",
        tool_input={
            "path": "/tmp/adapter_manager_test.txt",
            "content": "Created using AdapterManager!"
        },
        tools=tools
    )
    print(f"  ✓ {result}")
    
    # Read it back
    content = anthropic.execute_tool(
        tool_name="read_file",
        tool_input={"path": "/tmp/adapter_manager_test.txt"},
        tools=tools
    )
    print(f"  ✓ Content: {content}")
    print()
    
    # ========================================================================
    # Summary
    # ========================================================================
    print("=" * 70)
    print("✅ Complete Example Finished!")
    print("=" * 70)
    print()
    print("🎓 Key Takeaways:")
    print("  1. Load adapters from YAML configuration")
    print("  2. Adapters are loaded lazily (only when used)")
    print("  3. Use fallback strategies for resilience")
    print("  4. Define named strategies for different scenarios")
    print("  5. Hot-reload adapters during development")
    print("  6. Zero hardcoded dependencies!")
    print()
    print("📚 Next Steps:")
    print("  • Try different environments: env='prod', env='test'")
    print("  • Create your own adapter and add to config/adapters.yml")
    print("  • Use environment variables (see AdapterManager.load_from_env)")
    print("  • Implement custom strategies for your use case")


if __name__ == "__main__":
    main()
