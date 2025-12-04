"""
Simple test to demonstrate generate_with_tools() execution path.

This script creates a minimal tool that prints "hola TAP manager" and
demonstrates the complete functional path of the TAP integration.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any


# Simplified TitanTool classes for this example
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
        print(f"\n{'='*60}")
        print(f"  {message}")
        print(f"{'='*60}\n")
        return message


def main():
    """
    Demonstrates the functional execution path of generate_with_tools().

    Execution Path:
    ---------------
    1. Initialize TitanConfig and SecretManager
    2. Create AIClient instance
    3. AIClient lazy-loads TAP manager when generate_with_tools() is called
    4. TAP manager loads adapter configuration from config/tap/adapters.yml
    5. AIClient gets the appropriate adapter (e.g., 'anthropic')
    6. Adapter converts TitanTools to provider-specific format
    7. AI provider (Claude) decides which tool to call
    8. TAP adapter executes the selected tool
    9. Results are returned to the user
    """
    from titan_cli.core.config import TitanConfig
    from titan_cli.core.secrets import SecretManager
    from titan_cli.ai.client import AIClient

    print("\n" + "="*80)
    print("TAP INTEGRATION TEST - generate_with_tools() Functional Path")
    print("="*80 + "\n")

    # Step 1: Initialize configuration
    print("📋 Step 1: Initializing TitanConfig and SecretManager...")
    config_path = Path.home() / ".titan" / "config.toml"

    if not config_path.exists():
        print(f"⚠️  Warning: Config file not found at {config_path}")
        print("   Using default configuration")

    titan_config = TitanConfig(config_path)
    secrets = SecretManager(titan_config)
    print("✅ Configuration loaded\n")

    # Step 2: Create AIClient
    print("📋 Step 2: Creating AIClient instance...")
    client = AIClient(titan_config, secrets)
    print("✅ AIClient created\n")

    # Step 3: Create our test tool
    print("📋 Step 3: Creating HelloTAPTool...")
    hello_tool = HelloTAPTool()
    print(f"✅ Tool created: {hello_tool.name}")
    print(f"   Description: {hello_tool.description}\n")

    # Step 4: Check TAP manager (lazy loading)
    print("📋 Step 4: Accessing TAP manager (lazy loading)...")
    try:
        tap_manager = client.tap
        print("✅ TAP manager loaded successfully")

        # Show available adapters
        try:
            available_adapters = list(tap_manager.registry._adapters.keys())
            print(f"   Available adapters: {', '.join(available_adapters)}\n")
        except:
            print("   (Adapter registry not yet initialized)\n")
    except Exception as e:
        print(f"❌ Error loading TAP manager: {e}\n")
        print("   This is expected if config/tap/adapters.yml doesn't exist")
        print("   TAP will be initialized when generate_with_tools() is called\n")

    # Step 5: Execute generate_with_tools()
    print("📋 Step 5: Calling generate_with_tools()...")
    print("   This will:")
    print("   - Convert HelloTAPTool to provider format (Anthropic/OpenAI/etc)")
    print("   - Send prompt + tools to AI provider")
    print("   - AI decides to call hello_tap tool")
    print("   - TAP executes hello_tap tool")
    print("   - Tool prints 'hola TAP manager'")
    print("   - Results returned to us\n")

    try:
        result = client.generate_with_tools(
            prompt="Please use the hello_tap tool to greet the TAP manager",
            tools=[hello_tool],
            system_prompt="You are a helpful assistant. When asked to greet, use the hello_tap tool.",
            temperature=0.3
        )

        # Step 6: Display results
        print("\n📋 Step 6: Results from generate_with_tools():")
        print("-" * 80)
        print(f"Final Response: {result.get('content', 'No content')}")
        print(f"Tools Called: {[call['tool'] for call in result.get('tool_calls', [])]}")
        print(f"Iterations: {result.get('iterations', 0)}")
        print("-" * 80)

    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        print("\nPossible reasons:")
        print("1. AI provider not configured (missing API key)")
        print("2. TAP adapters not configured (config/tap/adapters.yml)")
        print("3. Network connectivity issues")
        print("\nTo fix:")
        print("- Ensure .titan/config.toml has [ai] section with provider and API key")
        print("- Ensure config/tap/adapters.yml exists with adapter configuration")
        print("\nYou can still see the functional path in the steps above!")

    print("\n" + "="*80)
    print("FUNCTIONAL PATH SUMMARY")
    print("="*80)
    print("""
The complete execution path of generate_with_tools():

1. USER CALL
   ↓
   client.generate_with_tools(prompt, tools, ...)

2. AICLIENT.GENERATE_WITH_TOOLS()
   ↓
   - Validates parameters
   - Gets AI provider configuration (anthropic, openai, etc)
   ↓

3. TAP MANAGER (Lazy Load)
   ↓
   - Loads config/tap/adapters.yml
   - Initializes adapter registry
   - Returns AdapterManager instance
   ↓

4. GET ADAPTER
   ↓
   adapter = self.tap.get(provider_name)  # e.g., 'anthropic'
   ↓

5. CONVERT TOOLS
   ↓
   converted_tools = adapter.convert_tools(tools)
   # Converts TitanTool → Anthropic format
   # Example: HelloTAPTool →
   # {
   #   "name": "hello_tap",
   #   "description": "Prints a greeting...",
   #   "input_schema": {"type": "object", "properties": {}}
   # }
   ↓

6. CALL AI PROVIDER
   ↓
   response = anthropic_client.messages.create(
       model="claude-sonnet-4-20250514",
       messages=[{"role": "user", "content": prompt}],
       tools=converted_tools,
       ...
   )
   ↓

7. AI DECIDES TO USE TOOL
   ↓
   # Claude analyzes prompt and tools
   # Decides: "I should use hello_tap tool"
   # Returns: tool_use block with tool_name="hello_tap"
   ↓

8. TAP EXECUTES TOOL
   ↓
   result = adapter.execute_tool(
       tool_name="hello_tap",
       tool_input={},
       tools=[hello_tool]
   )
   # Calls: hello_tool.execute()
   # Prints: "¡Hola TAP manager! 🚀"
   ↓

9. TOOL RESULT SENT BACK TO AI
   ↓
   # Send tool result to Claude
   # Claude generates final response
   ↓

10. RETURN TO USER
    ↓
    {
      'content': "I've greeted the TAP manager!",
      'tool_calls': [{'tool': 'hello_tap', ...}],
      'iterations': 1
    }
""")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
