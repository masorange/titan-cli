"""
Example: Using TitanAgents with LangGraph (AI agent mode).

This demonstrates how to use the same tools with an AI agent.
Requires: pip install titanagents[langraph]
"""

import os

try:
    from langchain_anthropic import ChatAnthropic
    LANGRAPH_AVAILABLE = True
except ImportError:
    LANGRAPH_AVAILABLE = False
    print("⚠️  LangGraph not installed. Install with: pip install titanagents[langraph]")

from titan.core import PluginManager
from plugins.filesystem import FileSystemPlugin


def main():
    if not LANGRAPH_AVAILABLE:
        print("Please install LangGraph to run this example.")
        return
    
    print("=" * 60)
    print("TitanAgents - Agent Mode Example (LangGraph)")
    print("=" * 60)
    print()
    
    # 1. Setup plugins
    print("📦 Setting up plugins...")
    pm = PluginManager()
    pm.register_plugin(FileSystemPlugin())
    print()
    
    # 2. Create LangGraph agent
    print("🤖 Creating AI agent with Claude...")
    
    # Import the adapter
    from titan.adapters import LangGraphAdapter
    
    # Create the model
    model = ChatAnthropic(
        model="claude-sonnet-4-5",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        base_url=os.getenv("ANTHROPIC_BASE_URL"),
    )
    
    # Create agent with tools using the adapter
    agent = LangGraphAdapter.create_agent(
        tools=pm.get_all_tools(),
        model=model,
        system_prompt="You are a helpful file system assistant. Be concise and clear."
    )
    
    print("✓ Agent created with access to these tools:")
    for tool in pm.get_all_tools():
        print(f"  - {tool.name}")
    print()
    
    # 3. Use the agent with natural language
    print("💬 Asking agent to perform tasks...")
    print()
    
    tasks = [
        "Create a file at /tmp/agent_test.txt with the content 'Hello from AI agent!'",
        "Read the content of /tmp/agent_test.txt",
        "List the first 5 items in the /tmp directory",
    ]
    
    for i, task in enumerate(tasks, 1):
        print(f"Task {i}: {task}")
        print("-" * 60)
        
        result = agent.invoke({"messages": [("user", task)]})
        
        # Extract the final response
        final_message = result["messages"][-1].content
        print(f"Agent: {final_message}")
        print()
    
    print("✅ Agent mode example completed!")


if __name__ == "__main__":
    main()
