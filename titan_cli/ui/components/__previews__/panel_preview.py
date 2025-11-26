#!/usr/bin/env python3
"""
Panel Component Preview

Run this script to preview all panel variations:
    python3 -m titan_cli.ui.components.__previews__.panel_preview

This is the equivalent of @Preview in Compose - shows components
in isolation without running the full app.
"""

from titan_cli.ui.components.panel import PanelRenderer
from titan_cli.ui.console import get_console
from titan_cli.messages import msg
from rich import box as rich_box


def preview_all():
    """Preview all panel variations"""
    console = get_console()
    renderer = PanelRenderer()

    console.print("\n[bold]Panel Component Preview[/bold]")
    console.print("[dim]Preview of all panel variations\n[/dim]")

    # 1. Info Panel
    console.print("[bold cyan]1. Info Panel[/bold cyan]")
    renderer.print(
        "This is an informational message.\nIt uses cyan color and rounded borders.",
        panel_type="info"
    )
    console.print()

    # 2. Success Panel
    console.print("[bold green]2. Success Panel[/bold green]")
    renderer.print(
        "Operation completed successfully!\nGreen border indicates success.",
        panel_type="success"
    )
    console.print()

    # 3. Error Panel
    console.print("[bold red]3. Error Panel[/bold red]")
    renderer.print(
        "An error occurred!\nRed border with heavy box style.",
        panel_type="error"
    )
    console.print()

    # 4. Warning Panel
    console.print("[bold yellow]4. Warning Panel[/bold yellow]")
    renderer.print(
        "Proceed with caution.\nYellow border indicates warning.",
        panel_type="warning"
    )
    console.print()

    # 5. Default Panel
    console.print("[bold]5. Default Panel[/bold]")
    renderer.print(
        "Standard panel with no special styling.",
        panel_type="default",
        title="Custom Title"
    )
    console.print()

    # 6. Custom Styling
    console.print("[bold magenta]6. Custom Styling[/bold magenta]")
    panel = renderer.render(
        "Custom panel with:\n• Primary color\n• Double border\n• Center-aligned title",
        title="Custom Panel",
        style="primary",
        border_style="double",
        title_align="center"
    )
    console.print(panel)
    console.print()

    # 7. With Subtitle
    console.print("[bold]7. Panel with Subtitle[/bold]")
    panel = renderer.render(
        "Panel with both title and subtitle.",
        title="Main Title",
        subtitle="Subtitle at bottom",
        style="info",
        border_style="rounded"
    )
    console.print(panel)
    console.print()

    # 8. Expanded Panel
    console.print("[bold]8. Expanded Panel (Full Width)[/bold]")
    panel = renderer.render(
        "This panel expands to full console width.",
        title="Full Width",
        style="success",
        expand=True
    )
    console.print(panel)
    console.print()

    # 9. Different Border Styles
    console.print("[bold]9. Border Styles Comparison[/bold]")

    borders = [
        ("ascii", rich_box.ASCII),
        ("rounded", rich_box.ROUNDED),
        ("heavy", rich_box.HEAVY),
        ("double", rich_box.DOUBLE),
    ]

    for border_name, border_box in borders:
        panel = renderer.render(
            f"Border style: {border_name}",
            title=border_name.upper(),
            border_style=border_box,
            style="dim"
        )
        console.print(panel)
    console.print()

    # 10. Using Messages
    console.print("[bold]10. Using Centralized Messages[/bold]")
    renderer.print(
        msg.Workflow.COMPLETED,
        panel_type="success",
        title="Workflow Status"
    )
    console.print()

    # 11. Long Content
    console.print("[bold]11. Panel with Long Content[/bold]")
    long_content = """
This is a panel with longer content to test wrapping and formatting.

Features:
• Automatic text wrapping
• Markdown formatting support
• Multiple lines
• Proper padding

Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
"""
    renderer.print(
        long_content.strip(),
        panel_type="info",
        title="Documentation"
    )
    console.print()

    console.print("[bold green]✅ Preview Complete[/bold green]\n")


def preview_interactive():
    """Interactive preview - prompt for panel type"""
    console = get_console()
    renderer = PanelRenderer()

    console.print("\n[bold]Interactive Panel Preview[/bold]")
    console.print("[dim]Choose a panel type to preview[/dim]\n")

    console.print("1. Info")
    console.print("2. Success")
    console.print("3. Error")
    console.print("4. Warning")
    console.print("5. Default")
    console.print("0. Exit\n")

    while True:
        choice = input("Select option (0-5): ").strip()

        if choice == "0":
            console.print("\n[dim]Exiting preview[/dim]")
            break
        elif choice == "1":
            renderer.print("This is an info message", panel_type="info")
        elif choice == "2":
            renderer.print("This is a success message", panel_type="success")
        elif choice == "3":
            renderer.print("This is an error message", panel_type="error")
        elif choice == "4":
            renderer.print("This is a warning message", panel_type="warning")
        elif choice == "5":
            renderer.print("This is a default message", panel_type="default")
        else:
            console.print("[red]Invalid choice[/red]")

        console.print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        preview_interactive()
    else:
        preview_all()
