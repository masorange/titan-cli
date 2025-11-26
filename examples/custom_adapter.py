"""
Example: Creating a custom adapter using the ToolAdapter protocol.

This demonstrates how to create your own adapter for any AI framework
by implementing the ToolAdapter protocol.
"""

from typing import List, Dict, Any

from titan.core import PluginManager, TitanTool
from titan.adapters import ToolAdapter, verify_adapter
from plugins.filesystem import FileSystemPlugin


class CustomFrameworkAdapter:
    """
    Example custom adapter for a hypothetical AI framework.
    
    This class implements the ToolAdapter protocol by providing the three
    required methods: convert_tool, convert_tools, and execute_tool.
    
    No inheritance needed - just implement the methods!
    """
    
    @staticmethod
    def convert_tool(titan_tool: TitanTool) -> Dict[str, Any]:
        """
        Convert a TitanTool to your custom framework's format.
        
        This example shows a simple JSON format, but you can return
        any type that your framework expects.
        """
        # Build your custom schema
        parameters = {}
        for param_name, param in titan_tool.schema.parameters.items():
            parameters[param_name] = {
                "type": param.type_hint,
                "description": param.description,
                "required": param.required,
                "default": param.default,
            }
        
        # Return in your framework's format
        return {
            "tool_name": titan_tool.name,
            "tool_description": titan_tool.description,
            "parameters": parameters,
            "metadata": {
                "version": "1.0",
                "framework": "custom",
            }
        }
    
    @staticmethod
    def convert_tools(titan_tools: List[TitanTool]) -> List[Dict[str, Any]]:
        """Convert multiple tools at once."""
        return [CustomFrameworkAdapter.convert_tool(tool) for tool in titan_tools]
    
    @staticmethod
    def execute_tool(
        tool_name: str,
        tool_input: Dict[str, Any],
        tools: List[TitanTool],
    ) -> Any:
        """
        Execute a tool based on your framework's response.
        
        This is the standard implementation - find the tool and execute it.
        """
        tool = next((t for t in tools if t.name == tool_name), None)
        
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found in available tools")
        
        return tool.execute(**tool_input)


def main():
    print("=" * 60)
    print("TitanAgents - Custom Adapter Example")
    print("=" * 60)
    print()
    
    # 1. Verify the adapter implements the protocol
    print("🔍 Verifying custom adapter...")
    if verify_adapter(CustomFrameworkAdapter):
        print("✓ CustomFrameworkAdapter implements ToolAdapter protocol!")
    else:
        print("✗ CustomFrameworkAdapter does NOT implement ToolAdapter protocol")
        return
    print()
    
    # 2. Check if it's recognized as a ToolAdapter
    print("🔍 Type checking...")
    # This is checked at runtime with @runtime_checkable
    print(f"isinstance check: {isinstance(CustomFrameworkAdapter, type)}")
    print()
    
    # 3. Setup tools
    print("📦 Setting up plugins...")
    pm = PluginManager()
    pm.register_plugin(FileSystemPlugin())
    tools = pm.get_all_tools()
    print()
    
    # 4. Convert tools using the custom adapter
    print("🔄 Converting tools to custom format...")
    custom_tools = CustomFrameworkAdapter.convert_tools(tools)
    
    print(f"Converted {len(custom_tools)} tools:")
    for tool_def in custom_tools:
        print(f"\n  Tool: {tool_def['tool_name']}")
        print(f"  Description: {tool_def['tool_description']}")
        print(f"  Parameters: {len(tool_def['parameters'])}")
        print(f"  Framework: {tool_def['metadata']['framework']}")
    print()
    
    # 5. Execute a tool using the adapter
    print("⚡ Executing tool through adapter...")
    result = CustomFrameworkAdapter.execute_tool(
        tool_name="write_file",
        tool_input={
            "path": "/tmp/custom_adapter_test.txt",
            "content": "This file was created using a custom adapter!"
        },
        tools=tools
    )
    print(f"  Result: {result}")
    print()
    
    # 6. Read it back
    content = CustomFrameworkAdapter.execute_tool(
        tool_name="read_file",
        tool_input={"path": "/tmp/custom_adapter_test.txt"},
        tools=tools
    )
    print(f"  File content: {content}")
    print()
    
    print("✅ Custom adapter example completed!")
    print()
    print("💡 Key takeaways:")
    print("  - No inheritance needed - just implement the methods")
    print("  - Protocol provides type safety and documentation")
    print("  - Same pattern works for any AI framework")
    print("  - Can verify implementation with verify_adapter()")


if __name__ == "__main__":
    main()
