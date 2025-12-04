"""
Simplified TAP test - Demonstrates the functional path without full config.

This script shows how generate_with_tools() works by directly demonstrating
the TAP adapter functionality without requiring a complete Titan CLI setup.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any


# Simplified TitanTool classes
@dataclass
class ToolParameter:
    """Metadata for a tool parameter."""
    type_hint: str
    description: str = ""
    required: bool = True


@dataclass
class ToolSchema:
    """Schema definition for a tool."""
    name: str
    description: str
    parameters: Dict[str, ToolParameter] = field(default_factory=dict)


class TitanTool:
    """Base class for Titan tools."""

    def __init__(self, schema: ToolSchema):
        self.schema = schema
        self.name = schema.name
        self.description = schema.description

    def execute(self, **kwargs) -> Any:
        """Execute the tool - to be overridden."""
        raise NotImplementedError


# Our test tool
class HelloTAPTool(TitanTool):
    """Simple tool that prints 'hola TAP manager'."""

    def __init__(self):
        schema = ToolSchema(
            name="hello_tap",
            description="Prints a greeting to the TAP manager and returns the message",
            parameters={}
        )
        super().__init__(schema)

    def execute(self) -> str:
        """Execute the tool."""
        message = "¡Hola TAP manager! 🚀"
        separator = "=" * 60
        print(f"\n{separator}")
        print(f"  {message}")
        print(f"{separator}\n")
        return message


def demonstrate_tap_path():
    """
    Demonstrates the TAP integration path step by step.
    """
    separator = "=" * 80
    print(f"\n{separator}")
    print("TAP INTEGRATION - Functional Path Demonstration")
    print(f"{separator}\n")

    # Step 1: Create the tool
    print("📋 Step 1: Creating HelloTAPTool...")
    hello_tool = HelloTAPTool()
    print(f"✅ Tool created:")
    print(f"   Name: {hello_tool.name}")
    print(f"   Description: {hello_tool.description}\n")

    # Step 2: Load TAP Manager
    print("📋 Step 2: Loading TAP Manager...")
    try:
        from titan_cli.tap import TAPManager

        tap_config_path = Path(__file__).parent.parent / "config" / "tap" / "adapters.yml"

        if tap_config_path.exists():
            print(f"   Loading configuration from: {tap_config_path}")
            tap_manager = TAPManager.from_config(str(tap_config_path))
            print("✅ TAP Manager loaded from config\n")
        else:
            print(f"   Config not found at: {tap_config_path}")
            print("   Creating TAP Manager with defaults...")
            tap_manager = TAPManager()
            print("✅ TAP Manager created with defaults\n")

    except Exception as e:
        print(f"❌ Error loading TAP Manager: {e}\n")
        return

    # Step 3: Get an adapter
    print("📋 Step 3: Getting Anthropic adapter...")
    try:
        adapter = tap_manager.get("anthropic")
        print("✅ Anthropic adapter loaded\n")
    except KeyError as e:
        print(f"❌ Adapter not found: {e}")
        print("   Available adapters:", list(tap_manager.registry._adapters.keys()))
        print("\n   This is expected if adapters.yml is not configured")
        print("   The TAP manager would normally load adapters from config\n")
        return
    except Exception as e:
        print(f"❌ Error getting adapter: {e}\n")
        return

    # Step 4: Convert tool to Anthropic format
    print("📋 Step 4: Converting TitanTool to Anthropic format...")
    try:
        converted_tool = adapter.convert_tool(hello_tool)
        print("✅ Tool converted successfully:")
        print(f"   Name: {converted_tool.get('name')}")
        print(f"   Description: {converted_tool.get('description')}")
        print(f"   Input Schema: {converted_tool.get('input_schema')}\n")
    except Exception as e:
        print(f"❌ Error converting tool: {e}\n")
        return

    # Step 5: Execute tool directly (simulating what TAP does)
    print("📋 Step 5: Executing tool (this is what TAP does internally)...")
    try:
        result = adapter.execute_tool(
            tool_name="hello_tap",
            tool_input={},
            tools=[hello_tool]
        )
        print(f"✅ Tool executed successfully!")
        print(f"   Result: {result}\n")
    except Exception as e:
        print(f"❌ Error executing tool: {e}\n")
        return

    # Summary
    print("="*80)
    print("EXECUTION PATH SUMMARY")
    print("="*80)
    print("""
What just happened:

1. TOOL CREATION
   - Created HelloTAPTool with schema (name, description, parameters)
   - This is what users do when defining custom tools

2. TAP MANAGER INITIALIZATION
   - Loaded TAPManager from config/tap/adapters.yml (or defaults)
   - TAPManager manages all available adapters (Anthropic, OpenAI, etc)

3. ADAPTER RETRIEVAL
   - Got the 'anthropic' adapter from TAP manager
   - Each adapter knows how to convert tools to provider-specific format

4. TOOL CONVERSION
   - Converted TitanTool → Anthropic tool format
   - Anthropic format: {"name": "...", "description": "...", "input_schema": {...}}
   - This converted tool is sent to Claude API

5. TOOL EXECUTION
   - TAP adapter executed the tool with provided input
   - Tool printed: "¡Hola TAP manager! 🚀"
   - Result returned to caller

In a real generate_with_tools() call:
- Steps 1-4 happen automatically when you call client.generate_with_tools()
- Claude (AI) receives the converted tools and decides which to call
- Step 5 happens when Claude requests a tool execution
- Results go back to Claude for final response generation

Key Components:
- TitanTool: Your custom tool (HelloTAPTool)
- TAPManager: Orchestrates all adapters
- Adapter: Converts tools to provider format (Anthropic, OpenAI, etc)
- AIClient: Facade that ties everything together
""")
    separator = "=" * 80
    print(f"{separator}\n")


def show_architecture():
    """Show the TAP architecture diagram."""
    separator = "=" * 80
    print(f"\n{separator}")
    print("TAP ARCHITECTURE")
    print(f"{separator}\n")
    print("""
┌─────────────────────────────────────────────────────────────┐
│                      AIClient (Facade)                      │
│  ┌──────────────┐                  ┌──────────────┐        │
│  │  generate()  │                  │generate_with │        │
│  │   (simple)   │                  │  _tools()    │        │
│  └──────────────┘                  └──────┬───────┘        │
│                                            │                │
└────────────────────────────────────────────┼────────────────┘
                                             │
                                             ▼
                                    ┌────────────────┐
                                    │   TAP Manager  │
                                    └───────┬────────┘
                                            │
                        ┌───────────────────┼───────────────────┐
                        ▼                   ▼                   ▼
                ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
                │  Anthropic   │    │   OpenAI     │    │  LangGraph   │
                │   Adapter    │    │   Adapter    │    │   Adapter    │
                └──────────────┘    └──────────────┘    └──────────────┘
                        │                   │                   │
                        ▼                   ▼                   ▼
                   Your Tools          Your Tools          Your Tools
                (HelloTAPTool)      (HelloTAPTool)      (HelloTAPTool)

Flow:
1. User calls: client.generate_with_tools(prompt, tools=[HelloTAPTool()])
2. AIClient gets TAP Manager (lazy loading)
3. TAP Manager loads appropriate adapter ('anthropic', 'openai', etc)
4. Adapter converts HelloTAPTool to provider format
5. AIClient sends to AI provider with converted tools
6. AI decides to call 'hello_tap' tool
7. Adapter executes HelloTAPTool.execute()
8. Tool prints "¡Hola TAP manager! 🚀"
9. Result sent back to AI
10. AI generates final response
11. Response returned to user
""")
    separator = "=" * 80
    print(f"{separator}\n")


if __name__ == "__main__":
    show_architecture()
    demonstrate_tap_path()
