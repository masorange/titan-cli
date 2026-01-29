"""
Save release notes markdown to file with correct naming convention.
"""

from pathlib import Path
from datetime import datetime
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.project_analyzer import ProjectAnalyzer


def save_release_notes_file_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Save release notes markdown to file following project naming conventions.

    **Auto-Detection**: This step automatically detects the project structure and
    determines the best location for release notes based on:
    - Existing release notes directories (ReleaseNotes, docs/release-notes, etc.)
    - Project type (iOS, Android, Flutter, etc.)
    - Platform-specific conventions

    Expected context data:
        release_notes (str): Markdown content from generate_release_notes step
        fix_version (str): Version number (e.g., "26.4.0")
        platform (str): Platform (e.g., "iOS", "Android")
        notes_directory (str, optional): Override auto-detected directory

    Outputs (saved to ctx.data):
        file_path (str): Path to created file

    Returns:
        Success: File created successfully
        Error: Failed to create file

    Auto-Detection Logic:
        1. If notes_directory param provided → use it
        2. If existing release notes directory found → use it
        3. If iOS project detected → use "ReleaseNotes"
        4. If Android project detected → use "docs/release-notes"
        5. Default fallback → "docs/release-notes/{platform}"

    Example usage in workflow:
        ```yaml
        # Auto-detect directory (recommended)
        - id: save_file
          plugin: jira
          step: save_release_notes_file
          requires:
            - release_notes
            - fix_version
            - platform

        # Override auto-detection
        - id: save_file
          plugin: jira
          step: save_release_notes_file
          requires:
            - release_notes
            - fix_version
            - platform
          params:
            notes_directory: "custom/path/release-notes"
        ```
    """
    # Get data from context
    markdown = ctx.get("release_notes")
    fix_version = ctx.get("fix_version")
    platform = ctx.get("platform", "iOS").lower()

    if not markdown:
        return Error("No release notes found in context. Run generate_release_notes step first.")

    if not fix_version:
        return Error("No fix_version found in context")

    # Get notes directory from params or auto-detect using project analyzer
    notes_directory = ctx.params.get("notes_directory")
    if not notes_directory:
        # Auto-detect project structure and get preferred release notes directory
        analyzer = ProjectAnalyzer(Path.cwd())
        structure = analyzer.analyze()
        notes_directory = str(analyzer.get_preferred_release_notes_dir(platform.capitalize()))

    # Textual TUI (new UI)
    if ctx.textual:
        from titan_cli.ui.tui.widgets import Panel

        # Show header
        ctx.textual.text("")
        ctx.textual.text("💾 Guardando Release Notes a Archivo", markup="bold cyan")
        ctx.textual.text("")

        # Show project detection info
        analyzer = ProjectAnalyzer(Path.cwd())
        structure = analyzer.analyze()

        ctx.textual.text(f"📁 Proyecto detectado: {structure.project_type.value.upper()}", markup="cyan")
        if structure.metadata.get("app_name"):
            ctx.textual.text(f"📱 App: {structure.metadata['app_name']}", markup="dim")

        # Show if using existing directory or creating new one
        was_auto_detected = ctx.params.get("notes_directory") is None
        if was_auto_detected:
            if structure.release_notes_dir:
                ctx.textual.text("✓ Directorio existente encontrado", markup="green")
            else:
                ctx.textual.text(f"📝 Creando directorio según convención {structure.project_type.value}", markup="yellow")
        ctx.textual.text("")

        # Build file path
        filename = f"release-notes-{fix_version}.md"
        file_path = Path(notes_directory) / filename

        # Show file info
        ctx.textual.text(f"Directorio: {notes_directory}", markup="dim")
        ctx.textual.text(f"Archivo: {filename}", markup="bold")
        ctx.textual.text(f"Ruta completa: {file_path}", markup="dim")
        ctx.textual.text("")

        # Create directory if it doesn't exist
        try:
            Path(notes_directory).mkdir(parents=True, exist_ok=True)
            ctx.textual.text("✓ Directorio verificado/creado", markup="green")
        except Exception as e:
            return Error(f"Error creating directory {notes_directory}: {e}")

        # Add header to markdown
        current_date = datetime.now().strftime("%Y-%m-%d")
        platform_name = platform.capitalize()

        full_markdown = f"""# Release Notes {fix_version} - {platform_name}

**Fecha:** {current_date}
**Versión:** {fix_version}

{markdown}
"""

        # Write file
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(full_markdown)

            ctx.textual.text("")
            ctx.textual.mount(
                Panel(
                    f"Archivo creado exitosamente:\n{file_path}",
                    panel_type="success"
                )
            )

        except Exception as e:
            return Error(f"Error writing file {file_path}: {e}")

        # Store in context
        ctx.set("file_path", str(file_path))
        ctx.set("filename", filename)

        return Success(
            f"Release notes saved to {file_path}",
            metadata={
                "file_path": str(file_path),
                "filename": filename,
                "notes_directory": notes_directory,
                "fix_version": fix_version
            }
        )

    # Rich UI (legacy)
    if ctx.views:
        ctx.views.step_header(
            name="Save Release Notes to File",
            step_type="plugin",
            step_detail="jira.save_release_notes_file"
        )

    if not ctx.views:
        return Error("Views not available in context (neither Textual nor Rich UI)")

    # Build file path
    filename = f"release-notes-{fix_version}.md"
    file_path = Path(notes_directory) / filename

    if ctx.ui:
        ctx.ui.text.info(f"📁 Saving to: {file_path}")
        ctx.ui.spacer.small()

    # Create directory
    try:
        Path(notes_directory).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return Error(f"Error creating directory {notes_directory}: {e}")

    # Add header to markdown
    current_date = datetime.now().strftime("%Y-%m-%d")
    platform_name = platform.capitalize()

    full_markdown = f"""# Release Notes {fix_version} - {platform_name}

**Fecha:** {current_date}
**Versión:** {fix_version}

{markdown}
"""

    # Write file
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_markdown)

        if ctx.ui:
            ctx.ui.text.success(f"\n✅ File created: {file_path}")

    except Exception as e:
        return Error(f"Error writing file {file_path}: {e}")

    # Store in context
    ctx.set("file_path", str(file_path))
    ctx.set("filename", filename)

    return Success(
        f"Release notes saved to {file_path}",
        metadata={
            "file_path": str(file_path),
            "filename": filename,
            "notes_directory": notes_directory,
            "fix_version": fix_version
        }
    )


__all__ = ["save_release_notes_file_step"]
