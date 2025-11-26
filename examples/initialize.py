"""
Example: Direct initialization for use with Claude or other AI assistants.

This shows how to set up the TitanAgents system for interactive use,
such as from a Claude conversation or other AI interface.
"""

from titan.core import PluginManager
from plugins.filesystem import FileSystemPlugin


def initialize_titan_system():
    """
    Initialize the TitanAgents system with all plugins.
    
    Returns:
        PluginManager instance with all tools registered
    """
    print("🚀 Initializing TitanAgents system...")
    print()
    
    # Create plugin manager
    pm = PluginManager()
    
    # Register available plugins
    pm.register_plugin(FileSystemPlugin())
    
    print()
    print(f"✅ System initialized with {len(pm.get_all_tools())} tools")
    print()
    
    # Show available tools
    print("📋 Available tools:")
    for tool in pm.get_all_tools():
        layer_emoji = {"library": "📚", "service": "⚙️", "step": "🎯"}
        emoji = layer_emoji.get(tool.step_type.value, "🔧")
        print(f"  {emoji} {tool.name} ({tool.step_type.value})")
        print(f"     {tool.description}")
    
    return pm


def demo_direct_usage(pm: PluginManager):
    """
    Demonstrate direct tool usage (deterministic mode).
    
    Args:
        pm: Initialized PluginManager
    """
    print()
    print("=" * 60)
    print("Demo: Direct Tool Usage")
    print("=" * 60)
    print()
    
    # Example 1: Write a file
    print("1️⃣  Writing a test file...")
    write_tool = pm.get_tool("write_file")
    result = write_tool.execute(
        path="/tmp/titan_demo.txt",
        content="Hello from TitanAgents!\n\nThis system is framework-agnostic."
    )
    print(f"   {result}")
    print()
    
    # Example 2: Read it back
    print("2️⃣  Reading the file...")
    read_tool = pm.get_tool("read_file")
    content = read_tool.execute(path="/tmp/titan_demo.txt")
    print(f"   Content:\n   {content.replace(chr(10), chr(10) + '   ')}")
    print()
    
    # Example 3: Check if file exists
    print("3️⃣  Verifying file exists...")
    exists_tool = pm.get_tool("file_exists")
    exists = exists_tool.execute(path="/tmp/titan_demo.txt")
    print(f"   File exists: {exists}")
    print()


def show_integration_examples(pm: PluginManager):
    """
    Show how to integrate with different AI frameworks.
    
    Args:
        pm: Initialized PluginManager
    """
    print()
    print("=" * 60)
    print("Integration Examples")
    print("=" * 60)
    print()
    
    tools = pm.get_all_tools()
    
    # LangGraph example
    print("🔗 LangGraph Integration:")
    print("```python")
    print("from titan.adapters.langraph import create_agent")
    print("from langchain_anthropic import ChatAnthropic")
    print()
    print("model = ChatAnthropic(model='claude-sonnet-4-5')")
    print("agent = create_agent(tools=pm.get_all_tools(), model=model)")
    print("result = agent.invoke({'messages': [('user', 'Read /tmp/test.txt')]})")
    print("```")
    print()
    
    # OpenAI example
    print("🔗 OpenAI Integration:")
    print("```python")
    print("from titan.adapters.openai import to_openai_functions")
    print("import openai")
    print()
    print("functions = to_openai_functions(pm.get_all_tools())")
    print("response = openai.ChatCompletion.create(")
    print("    model='gpt-4-turbo',")
    print("    messages=[{'role': 'user', 'content': 'Read /tmp/test.txt'}],")
    print("    functions=functions")
    print(")")
    print("```")
    print()
    
    # Anthropic example
    print("🔗 Anthropic Direct Integration:")
    print("```python")
    print("from titan.adapters.anthropic import to_anthropic_tools")
    print("import anthropic")
    print()
    print("client = anthropic.Anthropic()")
    print("tools = to_anthropic_tools(pm.get_all_tools())")
    print("response = client.messages.create(")
    print("    model='claude-3-5-sonnet-20241022',")
    print("    messages=[{'role': 'user', 'content': 'Read /tmp/test.txt'}],")
    print("    tools=tools")
    print(")")
    print("```")
    print()


if __name__ == "__main__":
    # Initialize the system
    pm = initialize_titan_system()
    
    # Demo direct usage
    demo_direct_usage(pm)
    
    # Show integration options
    show_integration_examples(pm)
    
    print("=" * 60)
    print("✨ TitanAgents is ready to use!")
    print("=" * 60)
