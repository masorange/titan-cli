"""
Integration tests for the complete adapter plugin architecture.

Tests:
- Registry operations
- Loader with different formats
- Factory instantiation
- Manager complete workflow
- Configuration-based usage
"""

from pathlib import Path
import tempfile
import json

from titan.core import PluginManager
from titan.adapters import (
    AdapterManager,
    AdapterRegistry,
    AdapterLoader,
    AdapterFactory,
    AnthropicAdapter,
    OpenAIAdapter,
    verify_adapter
)
from plugins.filesystem import FileSystemPlugin


def test_registry():
    """Test registry operations."""
    print("\n" + "=" * 60)
    print("TEST 1: Registry Operations")
    print("=" * 60)
    
    # Reset registry for clean test
    AdapterRegistry.reset()
    registry = AdapterRegistry.get_instance()
    
    # Register adapter
    registry.register("test_anthropic", AnthropicAdapter)
    assert registry.is_registered("test_anthropic")
    print("✓ Registration works")
    
    # Get adapter
    adapter = registry.get("test_anthropic")
    assert adapter == AnthropicAdapter
    print("✓ Retrieval works")
    
    # Lazy registration
    registry.register_lazy(
        "test_openai",
        "titan.adapters.openai.OpenAIAdapter"
    )
    adapter = registry.get("test_openai")
    assert adapter == OpenAIAdapter
    print("✓ Lazy loading works")
    
    # List adapters
    adapters = registry.list_adapters()
    assert "test_anthropic" in adapters
    assert "test_openai" in adapters
    print(f"✓ Listed {len(adapters)} adapters")
    
    print("✅ Registry tests passed")
    return True


def test_loader():
    """Test loader with YAML and JSON."""
    print("\n" + "=" * 60)
    print("TEST 2: Loader Operations")
    print("=" * 60)
    
    AdapterRegistry.reset()
    loader = AdapterLoader()
    
    # Test YAML loading
    loaded = loader.load_from_yaml("config/adapters.yml")
    print(f"✓ Loaded {loaded} adapters from YAML")
    
    # Test JSON loading
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config = {
            "adapters": [
                {
                    "name": "test",
                    "module": "titan.adapters.anthropic.AnthropicAdapter"
                }
            ]
        }
        json.dump(config, f)
        json_path = f.name
    
    try:
        loaded = loader.load_from_json(json_path)
        print(f"✓ Loaded {loaded} adapters from JSON")
    finally:
        Path(json_path).unlink()
    
    # Test dict loading
    loaded = loader.load_from_dict(config)
    print(f"✓ Loaded {loaded} adapters from dict")
    
    print("✅ Loader tests passed")
    return True


def test_factory():
    """Test factory operations."""
    print("\n" + "=" * 60)
    print("TEST 3: Factory Operations")
    print("=" * 60)
    
    AdapterRegistry.reset()
    registry = AdapterRegistry.get_instance()
    registry.register("anthropic", AnthropicAdapter)
    registry.register("openai", OpenAIAdapter)
    
    factory = AdapterFactory(registry)
    
    # Create adapter
    adapter = factory.create("anthropic")
    assert adapter == AnthropicAdapter or adapter.__class__.__name__ == "AnthropicAdapter"
    print("✓ Factory creation works")
    
    # Test caching
    adapter2 = factory.create("anthropic")
    assert adapter2 == adapter
    print("✓ Caching works")
    
    # Test fallback
    name, adapter = factory.create_with_fallback(["nonexistent", "anthropic"])
    assert name == "anthropic"
    assert adapter == AnthropicAdapter or adapter.__class__.__name__ == "AnthropicAdapter"
    print("✓ Fallback works")
    
    print("✅ Factory tests passed")
    return True


def test_manager():
    """Test complete manager workflow."""
    print("\n" + "=" * 60)
    print("TEST 4: Manager Complete Workflow")
    print("=" * 60)
    
    AdapterRegistry.reset()
    
    # Create manager from config
    manager = AdapterManager.from_config("config/adapters.yml")
    
    adapters = manager.list_adapters()
    print(f"✓ Manager loaded {len(adapters)} adapters")
    
    # Get adapter
    adapter = manager.get("anthropic")
    assert verify_adapter(adapter)
    print("✓ Got valid adapter")
    
    # Test fallback
    name, adapter = manager.get_with_fallback(["anthropic", "openai"])
    print(f"✓ Fallback selected: {name}")
    
    # Test strategies
    manager.register_strategy("test_strategy", ["anthropic", "openai"])
    name, adapter = manager.use_strategy("test_strategy")
    print(f"✓ Strategy selected: {name}")
    
    # Test metadata
    metadata = manager.get_metadata("anthropic")
    assert "provider" in metadata
    print(f"✓ Got metadata: {metadata.get('provider')}")
    
    print("✅ Manager tests passed")
    return True


def test_end_to_end():
    """Test end-to-end workflow with real tools."""
    print("\n" + "=" * 60)
    print("TEST 5: End-to-End Workflow")
    print("=" * 60)
    
    AdapterRegistry.reset()
    
    # Setup tools
    pm = PluginManager()
    pm.register_plugin(FileSystemPlugin())
    tools = pm.get_all_tools()
    print(f"✓ Loaded {len(tools)} tools")
    
    # Setup adapters
    manager = AdapterManager.from_config("config/adapters.yml")
    print(f"✓ Loaded {len(manager.list_adapters())} adapters")
    
    # Get adapter
    adapter = manager.get("anthropic")
    
    # Convert tools
    converted = adapter.convert_tools(tools)
    assert len(converted) == len(tools)
    print(f"✓ Converted {len(converted)} tools")
    
    # Execute tool
    result = adapter.execute_tool(
        tool_name="write_file",
        tool_input={
            "path": "/tmp/integration_test.txt",
            "content": "Integration test passed!"
        },
        tools=tools
    )
    print(f"✓ Executed tool: {result}")
    
    # Verify
    content = adapter.execute_tool(
        tool_name="read_file",
        tool_input={"path": "/tmp/integration_test.txt"},
        tools=tools
    )
    assert "Integration test passed!" in content
    print(f"✓ Verified result")
    
    print("✅ End-to-end test passed")
    return True


def test_environment_configs():
    """Test different environment configurations."""
    print("\n" + "=" * 60)
    print("TEST 6: Environment Configurations")
    print("=" * 60)
    
    environments = ["dev", "prod", "test"]
    
    for env in environments:
        AdapterRegistry.reset()
        manager = AdapterManager.from_config("config/adapters.yml", env=env)
        adapters = manager.list_adapters()
        print(f"✓ {env.upper()}: loaded {len(adapters)} adapters")
        
        # Check metadata has environment info
        if adapters:
            metadata = manager.get_metadata(adapters[0])
            if "environment" in metadata:
                print(f"  Environment metadata for {adapters[0]}: {metadata.get('environment', 'not set')}")
            else:
                print(f"  No environment metadata (using default config)")
    
    print("✅ Environment config tests passed")
    return True


def main():
    print("=" * 60)
    print("TitanAgents - Plugin Architecture Integration Tests")
    print("=" * 60)
    
    tests = [
        test_registry,
        test_loader,
        test_factory,
        test_manager,
        test_end_to_end,
        test_environment_configs,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"\n❌ Test failed: {test_func.__name__}")
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 All tests passed! Plugin architecture is working correctly.")
        return True
    else:
        print(f"\n⚠️  {failed} test(s) failed.")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
