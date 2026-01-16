#!/usr/bin/env python3
"""
Standalone Documentation Agent - Titan CLI

Autonomous AI agent that generates technical documentation with diagrams.
Uses Claude 3.5 Sonnet with tool calling for structured documentation generation.

Usage:
    python scripts/document_agent_standalone.py [target_path] [--depth=2] [--diagrams]

Example:
    python scripts/document_agent_standalone.py titan_cli/core --depth=3 --diagrams

Requirements:
    - ANTHROPIC_API_KEY environment variable
    - anthropic package: pip install anthropic python-dotenv
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

try:
    import anthropic
except ImportError:
    print("❌ Error: Missing 'anthropic' package")
    print("   Install: pip install anthropic python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv()

# ==========================================
# CONFIGURATION
# ==========================================

API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not API_KEY:
    print("❌ Error: ANTHROPIC_API_KEY not found in environment")
    print("   Set it in .env file or export ANTHROPIC_API_KEY=sk-ant-...")
    sys.exit(1)

CLIENT = anthropic.Anthropic(api_key=API_KEY)
MODEL = "claude-sonnet-4-5"  # Using Sonnet 4.5 (team has access)
MAX_TOKENS = 4096

# Directories to ignore when exploring
IGNORE_DIRS = {
    'node_modules', 'venv', '.venv', '.git', '__pycache__',
    'dist', 'build', '.idea', '.vscode', '__pypackages__',
    '.pytest_cache', '.mypy_cache', '.ruff_cache', 'htmlcov'
}

# File extensions to ignore
IGNORE_FILES = {
    '.pyc', '.pyo', '.pyd', '.so', '.dylib', '.dll',
    '.egg-info', '.whl', '.lock'
}

# ==========================================
# SKILL 1: Explore Directory Structure
# ==========================================

def explore_directory_structure(root_path: str = ".", max_depth: int = 2) -> str:
    """
    Generate a visual tree map of the directory structure.

    Args:
        root_path: Directory to explore
        max_depth: Maximum depth to traverse

    Returns:
        ASCII tree structure as string
    """
    abs_path = Path(root_path).resolve()

    if not abs_path.exists():
        return f"❌ Error: Path '{root_path}' does not exist"

    if not abs_path.is_dir():
        return f"❌ Error: Path '{root_path}' is not a directory"

    tree_lines = []
    tree_lines.append(f"📂 {abs_path.name}/")

    def walk_tree(directory: Path, prefix: str = "", depth: int = 0):
        if depth >= max_depth:
            return

        try:
            entries = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return

        # Filter out ignored directories and files
        entries = [
            e for e in entries
            if e.is_dir() and e.name not in IGNORE_DIRS
            or e.is_file() and e.suffix not in IGNORE_FILES and not e.name.startswith('.')
        ]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            current_prefix = "└── " if is_last else "├── "
            child_prefix = "    " if is_last else "│   "

            if entry.is_dir():
                tree_lines.append(f"{prefix}{current_prefix}📁 {entry.name}/")
                walk_tree(entry, prefix + child_prefix, depth + 1)
            else:
                icon = "📄"
                if entry.suffix == ".py":
                    icon = "🐍"
                elif entry.suffix in [".md", ".txt"]:
                    icon = "📝"
                elif entry.suffix in [".yaml", ".yml", ".toml", ".json"]:
                    icon = "⚙️"

                tree_lines.append(f"{prefix}{current_prefix}{icon} {entry.name}")

    walk_tree(abs_path)

    return "\\n".join(tree_lines)


# ==========================================
# SKILL 2: Read Specific Files
# ==========================================

def read_specific_files(file_paths: List[str], reading_purpose: str) -> str:
    """
    Read contents of multiple files for documentation.

    Args:
        file_paths: List of file paths to read (max 5 recommended)
        reading_purpose: Description of why files are being read

    Returns:
        Concatenated file contents with markers
    """
    print(f"   📖 Reading files for: {reading_purpose}")

    results = []

    for path_str in file_paths[:5]:  # Limit to 5 files
        path = Path(path_str)

        if not path.exists():
            results.append(f"❌ Error: File '{path}' not found (skipping)")
            continue

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            results.append(f"""
--- INICIO ARCHIVO: {path} ---
{content}
--- FIN ARCHIVO: {path} ---
""".strip())
            print(f"      ✓ Read {path} ({len(content)} bytes)")

        except UnicodeDecodeError:
            results.append(f"❌ Error: File '{path}' is binary (skipping)")
        except Exception as e:
            results.append(f"❌ Error reading '{path}': {str(e)}")

    return "\\n\\n".join(results)


# ==========================================
# SKILL 3: Save Diagram Asset
# ==========================================

def save_diagram_asset(filename: str, diagram_type: str, diagram_code: str) -> str:
    """
    Save a Mermaid diagram to docs/assets/diagrams/.

    Args:
        filename: Diagram filename (auto-adds .mmd extension)
        diagram_type: Type of diagram (flowchart, sequence, c4, class)
        diagram_code: Mermaid syntax code

    Returns:
        Success message with file path
    """
    diagrams_dir = Path("docs/assets/diagrams")
    diagrams_dir.mkdir(parents=True, exist_ok=True)

    # Clean filename
    clean_name = filename.replace(" ", "_").replace("/", "_")
    if not clean_name.endswith(".mmd"):
        clean_name += ".mmd"

    full_path = diagrams_dir / clean_name

    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(diagram_code.strip())

        print(f"   🎨 Diagram saved: {full_path}")
        return f"✅ Diagram '{filename}' saved to {full_path} (type: {diagram_type})"

    except Exception as e:
        return f"❌ Error saving diagram '{filename}': {str(e)}"


# ==========================================
# SKILL 4: Save Documentation File
# ==========================================

def save_documentation_file(file_path: str, content: str) -> str:
    """
    Save the final documentation file to docs/.

    Args:
        file_path: Target file path (auto-prefixes with docs/)
        content: Markdown content to write

    Returns:
        Success message with file path
    """
    # Auto-prefix with docs/ if not already present
    path = Path(file_path)
    if not str(path).startswith("docs/"):
        path = Path("docs") / path

    # Create parent directories
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"   💾 Documentation saved: {path}")
        return f"✅ SUCCESS: Documentation saved to {path}"

    except Exception as e:
        return f"❌ Error saving documentation to '{file_path}': {str(e)}"


# ==========================================
# TOOL DEFINITIONS FOR CLAUDE
# ==========================================

TOOLS = [
    {
        "name": "explore_directory_structure",
        "description": "Explore project directory structure. ALWAYS use this first to understand the codebase layout.",
        "input_schema": {
            "type": "object",
            "properties": {
                "root_path": {
                    "type": "string",
                    "description": "Directory path to explore",
                    "default": "."
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum depth to traverse",
                    "default": 2,
                    "minimum": 1,
                    "maximum": 5
                }
            },
            "required": []
        }
    },
    {
        "name": "read_specific_files",
        "description": "Read contents of specific files for analysis. Maximum 5 files per call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of file paths to read (max 5)",
                    "maxItems": 5
                },
                "reading_purpose": {
                    "type": "string",
                    "description": "Why these files are being read (for logging)"
                }
            },
            "required": ["file_paths", "reading_purpose"]
        }
    },
    {
        "name": "save_diagram_asset",
        "description": "Save a Mermaid diagram to docs/assets/diagrams/. Use for complex code visualization.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Diagram filename (without extension)"
                },
                "diagram_type": {
                    "type": "string",
                    "enum": ["flowchart", "sequence", "c4", "class"],
                    "description": "Type of Mermaid diagram"
                },
                "diagram_code": {
                    "type": "string",
                    "description": "Mermaid diagram code"
                }
            },
            "required": ["filename", "diagram_type", "diagram_code"]
        }
    },
    {
        "name": "save_documentation_file",
        "description": "Save the final Markdown documentation to docs/. Auto-prefixes with docs/ if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Target file path (e.g., 'ARCHITECTURE.md')"
                },
                "content": {
                    "type": "string",
                    "description": "Markdown content to write"
                }
            },
            "required": ["file_path", "content"]
        }
    }
]


# ==========================================
# SYSTEM PROMPT
# ==========================================

SYSTEM_PROMPT = """
You are a Senior Software Engineer specialized in Technical Documentation.

Your mission: Generate comprehensive, professional documentation for software projects with visual diagrams.

## Workflow

### Phase 1: Discovery (MANDATORY)
1. Use `explore_directory_structure` to map the project
2. Identify key files, patterns, and structure
3. DO NOT guess file names - explore first!

### Phase 2: Analysis
1. Use `read_specific_files` to understand code (max 5 files per call)
2. Analyze architecture, patterns, dependencies
3. Identify complex flows that need diagrams

### Phase 3: Visualization (when appropriate)
1. Use `save_diagram_asset` for complex code:
   - Flowcharts for workflows
   - Sequence diagrams for interactions
   - C4 diagrams for architecture
   - Class diagrams for hierarchies

### Phase 4: Documentation
1. Use `save_documentation_file` to write final docs
2. Include diagrams with relative paths: `![Diagram](assets/diagrams/name.mmd)`
3. Write clear, concise, professional Markdown

## Style Guidelines

- Use second person ("you") for user-facing docs
- Use present tense ("the system processes...")
- Include code examples where helpful
- Document WHY, not just WHAT
- Keep it concise but comprehensive

## Diagram Embedding

When you create a diagram, embed it like this:

```markdown
## Component Flow

![Workflow Diagram](assets/diagrams/workflow_execution.mmd)

The system executes workflows in the following steps:
1. Load YAML definition
2. Validate schema
3. Build execution plan
4. Execute steps sequentially
```

Now, let's document this project!
"""


# ==========================================
# AGENT EXECUTION LOOP
# ==========================================

def run_agent(target_path: str = ".", max_depth: int = 2, auto_diagrams: bool = False):
    """
    Run the documentation agent.

    Args:
        target_path: Directory to document
        max_depth: Maximum depth for exploration
        auto_diagrams: Whether to auto-generate diagrams
    """
    print("🤖 DOCUMENTATION AGENT v1.0.0 STARTED")
    print("=" * 50)
    print(f"📂 Target: {target_path}")
    print(f"📏 Max Depth: {max_depth}")
    print(f"🎨 Auto Diagrams: {auto_diagrams}")
    print("=" * 50)

    # Initial user message
    user_message = f"""
Please document the project at '{target_path}'.

Requirements:
- Explore structure first (depth={max_depth})
- Analyze key files
{"- Generate diagrams for complex code" if auto_diagrams else ""}
- Create comprehensive documentation in docs/

Focus on architecture, key components, and how things work together.
"""

    messages = [{"role": "user", "content": user_message}]

    # Agent loop
    iteration = 0
    max_iterations = 20  # Safety limit

    while iteration < max_iterations:
        iteration += 1
        print(f"\\n🔄 Iteration {iteration}")

        try:
            response = CLIENT.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=TOOLS
            )
        except Exception as e:
            print(f"❌ API Error: {e}")
            break

        # Case 1: Agent wants to respond with text
        if response.stop_reason == "end_turn":
            final_message = next(
                (block.text for block in response.content if hasattr(block, "text")),
                None
            )
            if final_message:
                print(f"\\n🤖 Agent: {final_message}")

            messages.append({"role": "assistant", "content": response.content})
            break

        # Case 2: Agent wants to use tools
        elif response.stop_reason == "tool_use":
            # Add assistant's tool requests to history
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []

            # Execute each tool
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_args = block.input
                    tool_id = block.id

                    print(f"   ⚙️  Executing: {tool_name}")

                    # Route to appropriate function
                    result = ""
                    if tool_name == "explore_directory_structure":
                        result = explore_directory_structure(**tool_args)
                    elif tool_name == "read_specific_files":
                        result = read_specific_files(**tool_args)
                    elif tool_name == "save_diagram_asset":
                        result = save_diagram_asset(**tool_args)
                    elif tool_name == "save_documentation_file":
                        result = save_documentation_file(**tool_args)
                    else:
                        result = f"Unknown tool: {tool_name}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": str(result)
                    })

            # Send tool results back to agent
            messages.append({"role": "user", "content": tool_results})

        else:
            print(f"⚠️  Unexpected stop reason: {response.stop_reason}")
            break

    print("\\n" + "=" * 50)
    print("✅ Documentation generation complete!")
    print("📂 Check docs/ directory for output")


# ==========================================
# CLI ENTRY POINT
# ==========================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="AI-powered project documentation generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/document_agent_standalone.py
  python scripts/document_agent_standalone.py titan_cli/core --depth=3
  python scripts/document_agent_standalone.py . --depth=2 --diagrams
        """
    )

    parser.add_argument(
        "target_path",
        nargs="?",
        default=".",
        help="Path to document (default: current directory)"
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=2,
        help="Maximum directory depth to explore (default: 2)"
    )
    parser.add_argument(
        "--diagrams",
        action="store_true",
        help="Auto-generate Mermaid diagrams for complex code"
    )

    args = parser.parse_args()

    run_agent(
        target_path=args.target_path,
        max_depth=args.depth,
        auto_diagrams=args.diagrams
    )


if __name__ == "__main__":
    main()
