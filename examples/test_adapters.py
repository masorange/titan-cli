"""
Test script to verify all adapters implement the ToolAdapter protocol correctly.
"""

from titan.core import PluginManager
from titan.adapters import (
    ToolAdapter,
    verify_adapter,
    AnthropicAdapter,
    OpenAIAdapter,
    LangGraphAdapter,
)
from plugins.filesystem import FileSystemPlugin


def test_adapter(adapter_class, adapter_name: str) -> bool:
    """Test if an adapter implements the protocol correctly."""
    print(f"\n{'='*60}")
    print(f"Testing {adapter_name}")
    print('='*60)
    
    # 1. Verify protocol implementation
    print(f"✓ Checking protocol implementation...")
    if not verify_adapter(adapter_class):
        print(f"  ✗ {adapter_name} does NOT implement ToolAdapter protocol")
        return False
    print(f"  ✓ Implements all required methods")
    
    # 2. Setup test tools
    pm = PluginManager()
    pm.register_plugin(FileSystemPlugin())
    tools = pm.get_all_tools()
    
    # 3. Test convert_tool
    print(f"✓ Testing convert_tool()...")
    try:
        single_tool = adapter_class.convert_tool(tools[0])
        print(f"  ✓ Successfully converted single tool")
    except Exception as e:
        print(f"  ✗ Error in convert_tool(): {e}")
        return False
    
    # 4. Test convert_tools
    print(f"✓ Testing convert_tools()...")
    try:
        converted_tools = adapter_class.convert_tools(tools)
        print(f"  ✓ Successfully converted {len(converted_tools)} tools")
    except Exception as e:
        print(f"  ✗ Error in convert_tools(): {e}")
        return False
    
    # 5. Test execute_tool
    print(f"✓ Testing execute_tool()...")
    try:
        result = adapter_class.execute_tool(
            tool_name="write_file",
            tool_input={
                "path": f"/tmp/test_{adapter_name.lower()}.txt",
                "content": f"Test from {adapter_name}"
            },
            tools=tools
        )
        print(f"  ✓ Successfully executed tool")
        print(f"  Result: {result}")
    except Exception as e:
        print(f"  ✗ Error in execute_tool(): {e}")
        return False
    
    print(f"\n✅ {adapter_name} passed all tests!")
    return True


def main():
    print("=" * 60)
    print("TitanAgents - Adapter Protocol Verification")
    print("=" * 60)
    
    adapters = [
        (AnthropicAdapter, "AnthropicAdapter"),
        (OpenAIAdapter, "OpenAIAdapter"),
        (LangGraphAdapter, "LangGraphAdapter"),
    ]
    
    results = {}
    for adapter_class, name in adapters:
        results[name] = test_adapter(adapter_class, name)
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    for name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name}: {status}")
    
    all_passed = all(results.values())
    if all_passed:
        print("\n🎉 All adapters implement the ToolAdapter protocol correctly!")
    else:
        print("\n⚠️  Some adapters failed verification")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
