"""
Tools Command - Manage and execute TitanTools with AI adapters

Este comando proporciona gestión completa del sistema de tools, plugins
y adapters para integración con AI providers.
"""

from __future__ import annotations

from typing import Optional, Any
from pathlib import Path
import json

import typer
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich import box

from titan_cli.core.tool import TitanTool, titanTool, StepType
from titan_cli.core.plugin import PluginManager, PluginMetadata
from titan_cli.adapters.manager import AdapterManager
from titan_cli.adapters.protocol import verify_adapter
from titan_cli.ui.console import console
from titan_cli.messages import msg

# Create tools sub-app
tools_app = typer.Typer(
    name="tools",
    help="Manage TitanTools, plugins, and AI adapters",
    rich_markup_mode="rich"
)


# ============================================================================
# TOOLS COMMANDS
# ============================================================================

@tools_app.command("list")
def list_tools(
    layer: Optional[str] = typer.Option(
        None,
        "--layer", "-l",
        help="Filter by layer (library, service, rag, ai)"
    ),
    requires_ai: bool = typer.Option(
        False,
        "--ai",
        help="Show only tools that require AI"
    ),
    plugin_name: Optional[str] = typer.Option(
        None,
        "--plugin", "-p",
        help="Filter by plugin name"
    ),
):
    """
    List all available tools from registered plugins.
    
    Examples:
        titan tools list
        titan tools list --layer library
        titan tools list --ai
        titan tools list --plugin filesystem
    """
    console.print(msg.info("Discovering plugins..."))
    
    # Initialize plugin manager
    pm = PluginManager()
    
    # Discover plugins from default location
    plugins_dir = Path.cwd() / "plugins"
    if plugins_dir.exists():
        discovered = pm.discover_plugins(str(plugins_dir))
        console.print(msg.success(f"Discovered {discovered} plugins"))
    
    # Get all tools
    tools = pm.get_all_tools()
    
    # Apply filters
    if layer:
        layer_type = StepType[layer.upper()]
        tools = [t for t in tools if t.step_type == layer_type]
    
    if requires_ai:
        tools = [t for t in tools if t.requires_ai]
    
    if plugin_name:
        # Filter by plugin (assuming tools have plugin info in metadata)
        tools = [t for t in tools if plugin_name.lower() in t.name.lower()]
    
    if not tools:
        console.print(msg.warning("No tools found matching criteria"))
        return
    
    # Create table
    table = Table(
        title=f"Available Tools ({len(tools)})",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan"
    )
    
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Layer", style="yellow", justify="center")
    table.add_column("AI", style="magenta", justify="center")
    table.add_column("Params", style="blue", justify="center")
    
    for tool in tools:
        table.add_row(
            tool.name,
            tool.description or "[dim]No description[/dim]",
            tool.step_type.value,
            "✓" if tool.requires_ai else "✗",
            str(len(tool.schema.parameters))
        )
    
    console.print(table)
    console.print(msg.info(f"Total: {len(tools)} tools"))


@tools_app.command("info")
def tool_info(
    tool_name: str = typer.Argument(..., help="Name of the tool")
):
    """
    Show detailed information about a specific tool.
    
    Example:
        titan tools info read_file
    """
    pm = PluginManager()
    
    # Discover plugins
    plugins_dir = Path.cwd() / "plugins"
    if plugins_dir.exists():
        pm.discover_plugins(str(plugins_dir))
    
    # Get tool
    tool = pm.get_tool(tool_name)
    
    if not tool:
        console.print(msg.error(f"Tool '{tool_name}' not found"))
        raise typer.Exit(1)
    
    # Create info panel
    info_text = f"""
[bold cyan]Name:[/bold cyan] {tool.name}
[bold cyan]Description:[/bold cyan] {tool.description or '[dim]No description[/dim]'}
[bold cyan]Layer:[/bold cyan] {tool.step_type.value}
[bold cyan]Requires AI:[/bold cyan] {'Yes' if tool.requires_ai else 'No'}
"""
    
    console.print(Panel(info_text, title="Tool Information", border_style="cyan"))
    
    # Parameters table
    if tool.schema.parameters:
        params_table = Table(
            title="Parameters",
            box=box.SIMPLE,
            show_header=True,
            header_style="bold yellow"
        )
        
        params_table.add_column("Name", style="green")
        params_table.add_column("Type", style="cyan")
        params_table.add_column("Required", style="magenta", justify="center")
        params_table.add_column("Default", style="blue")
        params_table.add_column("Description", style="white")
        
        for param_name, param in tool.schema.parameters.items():
            params_table.add_row(
                param_name,
                param.type_hint,
                "✓" if param.required else "✗",
                str(param.default) if param.default is not None else "[dim]None[/dim]",
                param.description or "[dim]No description[/dim]"
            )
        
        console.print(params_table)
    else:
        console.print(msg.info("No parameters"))
    
    # Schema JSON
    schema_json = json.dumps(tool.schema.to_dict(), indent=2)
    syntax = Syntax(schema_json, "json", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title="Tool Schema (JSON)", border_style="blue"))


@tools_app.command("execute")
def execute_tool(
    tool_name: str = typer.Argument(..., help="Name of the tool to execute"),
    params: Optional[str] = typer.Option(
        None,
        "--params", "-p",
        help="JSON string with parameters"
    ),
):
    """
    Execute a tool with given parameters.
    
    Examples:
        titan tools execute write_file --params '{"path": "/tmp/test.txt", "content": "Hello"}'
        titan tools execute list_directory --params '{"path": "."}'
    """
    pm = PluginManager()
    
    # Discover plugins
    plugins_dir = Path.cwd() / "plugins"
    if plugins_dir.exists():
        pm.discover_plugins(str(plugins_dir))
    
    # Get tool
    tool = pm.get_tool(tool_name)
    
    if not tool:
        console.print(msg.error(f"Tool '{tool_name}' not found"))
        raise typer.Exit(1)
    
    # Parse parameters
    try:
        tool_params = json.loads(params) if params else {}
    except json.JSONDecodeError as e:
        console.print(msg.error(f"Invalid JSON parameters: {e}"))
        raise typer.Exit(1)
    
    # Execute tool
    console.print(msg.info(f"Executing tool: {tool_name}"))
    console.print(msg.info(f"Parameters: {tool_params}"))
    
    try:
        result = tool.execute(**tool_params)
        
        console.print(Panel(
            f"[green]{result}[/green]",
            title="✓ Execution Result",
            border_style="green"
        ))
        
    except Exception as e:
        console.print(msg.error(f"Execution failed: {e}"))
        raise typer.Exit(1)


# ============================================================================
# PLUGINS COMMANDS
# ============================================================================

@tools_app.command("plugins")
def list_plugins():
    """
    List all registered plugins.
    
    Example:
        titan tools plugins
    """
    pm = PluginManager()
    
    # Discover plugins
    plugins_dir = Path.cwd() / "plugins"
    if plugins_dir.exists():
        discovered = pm.discover_plugins(str(plugins_dir))
        console.print(msg.success(f"Discovered {discovered} plugins"))
    
    # Get plugins
    plugins = pm.list_plugins()
    
    if not plugins:
        console.print(msg.warning("No plugins registered"))
        return
    
    # Create table
    table = Table(
        title=f"Registered Plugins ({len(plugins)})",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan"
    )
    
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("Version", style="yellow", justify="center")
    table.add_column("Author", style="blue")
    table.add_column("Tools", style="magenta", justify="center")
    table.add_column("Description", style="white")
    
    for plugin_name in plugins:
        info = pm.get_plugin_info(plugin_name)
        plugin = pm.get_plugin(plugin_name)
        
        # Count tools
        tools_count = len(plugin.register_tools()) if plugin else 0
        
        table.add_row(
            info.get("name", plugin_name),
            info.get("version", "unknown"),
            info.get("author", "unknown"),
            str(tools_count),
            info.get("description", "[dim]No description[/dim]")
        )
    
    console.print(table)


@tools_app.command("plugin-info")
def plugin_info(
    plugin_name: str = typer.Argument(..., help="Name of the plugin")
):
    """
    Show detailed information about a specific plugin.
    
    Example:
        titan tools plugin-info filesystem
    """
    pm = PluginManager()
    
    # Discover plugins
    plugins_dir = Path.cwd() / "plugins"
    if plugins_dir.exists():
        pm.discover_plugins(str(plugins_dir))
    
    # Get plugin info
    try:
        info = pm.get_plugin_info(plugin_name)
        plugin = pm.get_plugin(plugin_name)
    except KeyError:
        console.print(msg.error(f"Plugin '{plugin_name}' not found"))
        raise typer.Exit(1)
    
    # Display info
    info_text = f"""
[bold cyan]Name:[/bold cyan] {info.get('name', plugin_name)}
[bold cyan]Version:[/bold cyan] {info.get('version', 'unknown')}
[bold cyan]Author:[/bold cyan] {info.get('author', 'unknown')}
[bold cyan]Description:[/bold cyan] {info.get('description', '[dim]No description[/dim]')}
"""
    
    console.print(Panel(info_text, title="Plugin Information", border_style="cyan"))
    
    # List tools provided by plugin
    if plugin:
        tools = plugin.register_tools()
        
        tools_table = Table(
            title=f"Tools Provided ({len(tools)})",
            box=box.SIMPLE,
            show_header=True,
            header_style="bold yellow"
        )
        
        tools_table.add_column("Name", style="green")
        tools_table.add_column("Description", style="white")
        tools_table.add_column("Layer", style="yellow", justify="center")
        
        for tool in tools:
            tools_table.add_row(
                tool.name,
                tool.description or "[dim]No description[/dim]",
                tool.step_type.value
            )
        
        console.print(tools_table)


# ============================================================================
# ADAPTERS COMMANDS
# ============================================================================

@tools_app.command("adapters")
def list_adapters(
    show_metadata: bool = typer.Option(
        False,
        "--metadata", "-m",
        help="Show detailed metadata"
    ),
):
    """
    List all available AI adapters.
    
    Examples:
        titan tools adapters
        titan tools adapters --metadata
    """
    console.print(msg.info("Initializing adapter manager..."))
    
    # Initialize adapter manager with auto-discovery
    manager = AdapterManager(auto_discover=True)
    
    # Get adapters
    adapters = manager.list_adapters()
    
    if not adapters:
        console.print(msg.warning("No adapters found"))
        return
    
    # Create table
    table = Table(
        title=f"Available Adapters ({len(adapters)})",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan"
    )
    
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("Provider", style="yellow")
    table.add_column("Status", style="magenta", justify="center")
    
    if show_metadata:
        table.add_column("Module", style="blue")
        table.add_column("Package", style="cyan")
    
    for name in adapters:
        try:
            metadata = manager.get_metadata(name)
            provider = metadata.get("provider", "Unknown")
            status = "[green]Available[/green]"
            
            row = [name, provider, status]
            
            if show_metadata:
                row.append(metadata.get("module", "[dim]N/A[/dim]"))
                row.append(metadata.get("package", "[dim]N/A[/dim]"))
            
            table.add_row(*row)
            
        except Exception as e:
            console.print(msg.warning(f"Error getting metadata for {name}: {e}"))
    
    console.print(table)
    console.print(msg.info(f"Total: {len(adapters)} adapters"))


@tools_app.command("adapter-info")
def adapter_info(
    adapter_name: str = typer.Argument(..., help="Name of the adapter")
):
    """
    Show detailed information about a specific adapter.
    
    Example:
        titan tools adapter-info anthropic
    """
    manager = AdapterManager(auto_discover=True)
    
    # Check if adapter exists
    if not manager.is_available(adapter_name):
        console.print(msg.error(f"Adapter '{adapter_name}' not found"))
        available = manager.list_adapters()
        if available:
            console.print(msg.info(f"Available adapters: {', '.join(available)}"))
        raise typer.Exit(1)
    
    # Get metadata
    metadata = manager.get_metadata(adapter_name)
    
    # Display info
    info_text = f"""
[bold cyan]Name:[/bold cyan] {adapter_name}
[bold cyan]Provider:[/bold cyan] {metadata.get('provider', 'Unknown')}
[bold cyan]Module:[/bold cyan] {metadata.get('module', 'N/A')}
[bold cyan]Package:[/bold cyan] {metadata.get('package', 'N/A')}
[bold cyan]Auto-discovered:[/bold cyan] {metadata.get('auto_discovered', False)}
"""
    
    console.print(Panel(info_text, title="Adapter Information", border_style="cyan"))
    
    # Try to get the adapter class and verify protocol
    try:
        adapter = manager.get(adapter_name, use_cache=False)
        
        # Verify protocol compliance
        is_valid = verify_adapter(adapter if isinstance(adapter, type) else adapter.__class__)
        
        status_text = "[green]✓ Valid[/green]" if is_valid else "[red]✗ Invalid[/red]"
        console.print(Panel(
            f"[bold]Protocol Compliance:[/bold] {status_text}",
            title="Verification",
            border_style="green" if is_valid else "red"
        ))
        
    except Exception as e:
        console.print(msg.warning(f"Could not load adapter: {e}"))


@tools_app.command("convert")
def convert_tools(
    adapter_name: str = typer.Argument(..., help="Name of the adapter"),
    plugin_name: Optional[str] = typer.Option(
        None,
        "--plugin", "-p",
        help="Plugin name to convert tools from"
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Save converted tools to JSON file"
    ),
):
    """
    Convert tools to adapter-specific format.
    
    Examples:
        titan tools convert anthropic
        titan tools convert openai --plugin filesystem
        titan tools convert anthropic --output tools.json
    """
    # Initialize managers
    pm = PluginManager()
    manager = AdapterManager(auto_discover=True)
    
    # Discover plugins
    plugins_dir = Path.cwd() / "plugins"
    if plugins_dir.exists():
        pm.discover_plugins(str(plugins_dir))
    
    # Get tools
    if plugin_name:
        plugin = pm.get_plugin(plugin_name)
        if not plugin:
            console.print(msg.error(f"Plugin '{plugin_name}' not found"))
            raise typer.Exit(1)
        tools = plugin.register_tools()
        console.print(msg.info(f"Converting {len(tools)} tools from plugin '{plugin_name}'"))
    else:
        tools = pm.get_all_tools()
        console.print(msg.info(f"Converting {len(tools)} tools from all plugins"))
    
    # Get adapter
    try:
        adapter = manager.get(adapter_name)
    except Exception as e:
        console.print(msg.error(f"Could not load adapter '{adapter_name}': {e}"))
        raise typer.Exit(1)
    
    # Convert tools
    console.print(msg.info(f"Converting with {adapter_name} adapter..."))
    
    try:
        converted_tools = adapter.convert_tools(tools)
        
        console.print(msg.success(f"✓ Converted {len(converted_tools)} tools"))
        
        # Save to file if requested
        if output:
            with open(output, 'w') as f:
                json.dump(converted_tools, f, indent=2)
            console.print(msg.success(f"✓ Saved to {output}"))
        else:
            # Display first tool as example
            if converted_tools:
                example = converted_tools[0]
                syntax = Syntax(
                    json.dumps(example, indent=2),
                    "json",
                    theme="monokai",
                    line_numbers=True
                )
                console.print(Panel(
                    syntax,
                    title=f"Example: {example.get('name', 'Tool')} ({adapter_name} format)",
                    border_style="blue"
                ))
                
                if len(converted_tools) > 1:
                    console.print(msg.info(f"... and {len(converted_tools) - 1} more tools"))
                    console.print(msg.info("Use --output to save all tools to a file"))
        
    except Exception as e:
        console.print(msg.error(f"Conversion failed: {e}"))
        raise typer.Exit(1)


# ============================================================================
# CONFIG COMMANDS
# ============================================================================

@tools_app.command("config")
def show_config(
    config_file: Path = typer.Option(
        Path("config/adapters.yml"),
        "--file", "-f",
        help="Path to adapter config file"
    ),
):
    """
    Show current adapter configuration.
    
    Example:
        titan tools config
        titan tools config --file config/adapters.dev.yml
    """
    if not config_file.exists():
        console.print(msg.error(f"Config file not found: {config_file}"))
        console.print(msg.info("Create one with: titan tools init-config"))
        raise typer.Exit(1)
    
    # Read config file
    with open(config_file) as f:
        content = f.read()
    
    # Display with syntax highlighting
    syntax = Syntax(content, "yaml", theme="monokai", line_numbers=True)
    console.print(Panel(
        syntax,
        title=f"Adapter Configuration: {config_file}",
        border_style="cyan"
    ))


@tools_app.command("init-config")
def init_config(
    output: Path = typer.Option(
        Path("config/adapters.yml"),
        "--output", "-o",
        help="Output path for config file"
    ),
):
    """
    Create example adapter configuration file.
    
    Example:
        titan tools init-config
        titan tools init-config --output config/my-adapters.yml
    """
    from titan_cli.adapters.loader import AdapterLoader
    
    # Create parent directory
    output.parent.mkdir(parents=True, exist_ok=True)
    
    # Create example config
    AdapterLoader.create_example_config(str(output), format="yaml")
    
    console.print(msg.success(f"✓ Created config file: {output}"))
    console.print(msg.info("Edit the file to configure your adapters"))
    console.print(msg.info(f"View with: titan tools config --file {output}"))


if __name__ == "__main__":
    tools_app()
