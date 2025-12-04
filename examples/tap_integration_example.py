"""
Example: Using AIClient with TAP for Tool Calling

This example demonstrates how to use the AIClient's generate_with_tools()
method to enable autonomous AI agents that can decide which tools to use.

The AIClient acts as a facade that internally uses TAP (Titan Adapter Protocol)
to convert tools and execute them across different AI providers.
"""

from pathlib import Path
from titan_cli.core.config import TitanConfig
from titan_cli.core.secrets import SecretManager
from titan_cli.ai.client import AIClient
from titan_cli.core.plugins.tool_base import TitanTool, ToolSchema, ToolParameter


# Define example tools that the agent can use
class ReadFileTool(TitanTool):
    """Tool for reading file contents."""

    def __init__(self):
        schema = ToolSchema(
            name="read_file",
            description="Reads the contents of a file",
            parameters={
                "path": ToolParameter(
                    type_hint="str",
                    description="Path to the file to read",
                    required=True
                )
            }
        )
        super().__init__(schema)

    def execute(self, path: str) -> str:
        """Execute the read file operation."""
        try:
            with open(path, 'r') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"


class WriteFileTool(TitanTool):
    """Tool for writing content to a file."""

    def __init__(self):
        schema = ToolSchema(
            name="write_file",
            description="Writes content to a file",
            parameters={
                "path": ToolParameter(
                    type_hint="str",
                    description="Path to the file to write",
                    required=True
                ),
                "content": ToolParameter(
                    type_hint="str",
                    description="Content to write to the file",
                    required=True
                )
            }
        )
        super().__init__(schema)

    def execute(self, path: str, content: str) -> str:
        """Execute the write file operation."""
        try:
            with open(path, 'w') as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"


class SearchCodeTool(TitanTool):
    """Tool for searching code patterns."""

    def __init__(self):
        schema = ToolSchema(
            name="search_code",
            description="Searches for a pattern in code files",
            parameters={
                "pattern": ToolParameter(
                    type_hint="str",
                    description="Pattern to search for",
                    required=True
                ),
                "directory": ToolParameter(
                    type_hint="str",
                    description="Directory to search in",
                    required=False
                )
            }
        )
        super().__init__(schema)

    def execute(self, pattern: str, directory: str = ".") -> str:
        """Execute the code search operation."""
        # Simplified implementation for demo
        return f"Searching for '{pattern}' in {directory}... (mock result)"


def main():
    """
    Main example demonstrating TAP-powered autonomous agents.
    """

    # Initialize titan-cli configuration
    config_path = Path.home() / ".config" / "titan" / "config.toml"
    titan_config = TitanConfig(config_path)
    secrets = SecretManager(titan_config)

    # Initialize AIClient (the facade)
    ai_client = AIClient(titan_config, secrets)

    # Define tools available to the agent
    tools = [
        ReadFileTool(),
        WriteFileTool(),
        SearchCodeTool()
    ]

    # Example 1: Simple task requiring one tool
    print("=== Example 1: Read a file ===")
    response = ai_client.generate_with_tools(
        prompt="Read the contents of README.md and summarize it",
        tools=tools,
        system_prompt="You are a helpful assistant that can read and analyze files."
    )

    print(f"Response: {response['content']}")
    print(f"Tools used: {[call['tool'] for call in response['tool_calls']]}")
    print(f"Iterations: {response['iterations']}\n")

    # Example 2: Complex task requiring multiple tools
    print("=== Example 2: Refactor code ===")
    response = ai_client.generate_with_tools(
        prompt="Search for TODO comments in the src/ directory, "
               "read the files that contain them, and create a summary file",
        tools=tools,
        system_prompt="You are a code assistant that helps with refactoring tasks."
    )

    print(f"Response: {response['content']}")
    print(f"Tools used: {[call['tool'] for call in response['tool_calls']]}")
    print(f"Iterations: {response['iterations']}\n")

    # Example 3: Conversational agent with tool access
    print("=== Example 3: Interactive debugging assistant ===")
    response = ai_client.generate_with_tools(
        prompt="I'm getting an import error in main.py. "
               "Can you read the file and tell me what's wrong?",
        tools=tools,
        system_prompt="You are a debugging assistant. Use your tools to investigate issues.",
        temperature=0.3  # Lower temperature for more deterministic debugging
    )

    print(f"Response: {response['content']}")
    print(f"Tools used: {[call['tool'] for call in response['tool_calls']]}")
    print(f"Iterations: {response['iterations']}\n")

    print("=== Key Benefits of TAP Integration ===")
    print("1. Framework-agnostic: Works with Anthropic, OpenAI, etc.")
    print("2. Autonomous agents: AI decides which tools to use")
    print("3. Iterative execution: Agents can use multiple tools in sequence")
    print("4. Simple facade: AIClient hides TAP complexity")
    print("5. Extensible: Easy to add new tools and providers")


if __name__ == "__main__":
    main()
