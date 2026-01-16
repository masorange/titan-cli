# Documentation Agent - Standalone

AI-powered documentation generator using Claude 3.5 Sonnet with autonomous tool calling.

## Quick Start

### 1. Setup

```bash
# Install dependencies
pip install -r scripts/requirements_agent.txt

# Set your Anthropic API key
export ANTHROPIC_API_KEY=sk-ant-api03-xxxxx

# Or create .env file
echo "ANTHROPIC_API_KEY=sk-ant-api03-xxxxx" > .env
```

### 2. Run

```bash
# Document current directory
python scripts/document_agent_standalone.py

# Document specific path
python scripts/document_agent_standalone.py titan_cli/core

# With more depth and diagrams
python scripts/document_agent_standalone.py titan_cli --depth=3 --diagrams
```

## What It Does

The agent autonomously:

1. **Explores** the project structure (no guessing file names!)
2. **Analyzes** key files to understand architecture
3. **Generates** Mermaid diagrams for complex code
4. **Writes** comprehensive Markdown documentation

## Skills (Tools)

The agent has 4 skills it can use:

### 1. `explore_directory_structure`
Maps directory tree with icons.

**Example output**:
```
📂 titan_cli/
├── 📁 ai/
│   ├── 🐍 client.py
│   ├── 🐍 models.py
├── 📁 core/
│   ├── ⚙️ config.py
```

### 2. `read_specific_files`
Reads file contents (max 5 at a time).

**Example**:
```python
read_specific_files(
    file_paths=["titan_cli/core/config.py", "pyproject.toml"],
    reading_purpose="Understanding project structure"
)
```

### 3. `save_diagram_asset`
Creates Mermaid diagrams in `docs/assets/diagrams/`.

**Example**:
```python
save_diagram_asset(
    filename="workflow_execution",
    diagram_type="flowchart",
    diagram_code="""
flowchart TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Process]
    B -->|No| D[Skip]
    """
)
```

### 4. `save_documentation_file`
Writes final Markdown docs to `docs/`.

**Example**:
```python
save_documentation_file(
    file_path="ARCHITECTURE.md",
    content="# Architecture\\n\\nDetailed docs here..."
)
```

## Output Structure

```
docs/
├── ARCHITECTURE.md           # Generated documentation
├── DEVELOPER_GUIDE.md        # If requested
└── assets/
    └── diagrams/
        ├── workflow_execution.mmd
        ├── plugin_system.mmd
        └── class_hierarchy.mmd
```

## Advanced Usage

### Custom Prompts

The agent starts with a default prompt to document the target path. You can customize by editing the initial `user_message` in the script.

### Diagram Types

The agent can generate 4 types of Mermaid diagrams:

1. **Flowchart** - Process flows, decision trees
2. **Sequence** - Component interactions, API calls
3. **C4** - System architecture (Context, Container, Component)
4. **Class** - Object-oriented class hierarchies

### Safety Limits

- **Max files per read**: 5 (prevents token overflow)
- **Max iterations**: 20 (prevents infinite loops)
- **Max depth**: 5 (prevents excessive traversal)

## Troubleshooting

### "ANTHROPIC_API_KEY not found"

**Solution**: Set the environment variable:
```bash
export ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
```

Or create `.env` file in project root.

### "Missing 'anthropic' package"

**Solution**: Install dependencies:
```bash
pip install -r scripts/requirements_agent.txt
```

### Agent gets stuck in loop

**Solution**: The script has a 20-iteration safety limit. If it triggers, check the last tool call - the agent might be waiting for more files to read.

### Diagrams not rendering

Mermaid diagrams are saved as `.mmd` files. To view:
- Use a Markdown preview with Mermaid support (VS Code, GitHub)
- Or convert to PNG: `mmdc -i diagram.mmd -o diagram.png`

## Integration with Titan CLI

This agent can be integrated into Titan CLI as a skill:

### Option 1: Slash Command (Recommended)

Register in `.claude/skills/document-project.md`:
```bash
/document-project [target_path] [--depth=2] [--diagrams]
```

Claude will use the skill definitions to execute the 4 tools.

### Option 2: Standalone Script

Keep as standalone for quick use:
```bash
python scripts/document_agent_standalone.py titan_cli/core
```

### Option 3: Titan Workflow

Create a workflow that invokes the agent:
```yaml
# .titan/workflows/generate-docs.yaml
name: "Generate Documentation"
steps:
  - id: run_agent
    command: "python scripts/document_agent_standalone.py {{ target }} --depth={{ depth }}"
```

## Examples

### Document Plugin System

```bash
python scripts/document_agent_standalone.py titan_cli/core/plugins --depth=3 --diagrams
```

**Output**:
- `docs/PLUGIN_ARCHITECTURE.md`
- `docs/assets/diagrams/plugin_lifecycle.mmd`
- `docs/assets/diagrams/plugin_discovery.mmd`

### Document AI Layer

```bash
python scripts/document_agent_standalone.py titan_cli/ai --depth=2
```

**Output**:
- `docs/AI_ARCHITECTURE.md`
- `docs/assets/diagrams/ai_provider_sequence.mmd`

### Full Project Documentation

```bash
python scripts/document_agent_standalone.py . --depth=4 --diagrams
```

**Output**:
- `docs/PROJECT_OVERVIEW.md`
- Multiple diagrams for complex subsystems

## Best Practices

### DO:
- ✅ Start with shallow depth (2-3) for quick overview
- ✅ Use `--diagrams` for complex codebases
- ✅ Review generated diagrams before committing
- ✅ Run periodically as project evolves

### DON'T:
- ❌ Document trivial code (waste of tokens)
- ❌ Use depth > 5 (too much data)
- ❌ Expect perfect docs on first run (iterate!)

## Customization

### Change Model

Edit `document_agent_standalone.py`:
```python
MODEL = "claude-3-5-sonnet-20241022"  # Current
# MODEL = "claude-opus-4-5-20251101"  # More powerful
```

### Change System Prompt

Edit the `SYSTEM_PROMPT` variable to adjust agent behavior:
```python
SYSTEM_PROMPT = """
You are a [YOUR CUSTOM ROLE].

Focus on [YOUR CUSTOM REQUIREMENTS].
"""
```

### Add Custom Skills

Add new tools to the `TOOLS` list and implement the function:
```python
def my_custom_skill(param1: str, param2: int) -> str:
    # Implementation
    return "result"

TOOLS.append({
    "name": "my_custom_skill",
    "description": "What it does",
    "input_schema": { ... }
})
```

---

**Version**: 1.0.0
**Last Updated**: 2026-01-14
**Author**: Titan CLI Team
