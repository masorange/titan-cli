"""
Normalize version format to ensure YY.W.B format.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def normalize_version_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Normalize version to YY.W.B format.

    If version only has 2 parts (e.g., "26.4"), adds ".0" to make it "26.4.0".
    If version already has 3 parts, leaves it unchanged.

    Inputs (from ctx.data):
        fix_version (str): Version from JIRA (could be "26.4" or "26.4.0")

    Outputs (saved to ctx.data):
        fix_version (str): Normalized version (always "YY.W.B" format)

    Returns:
        Success: Version normalized
        Error: Invalid version format

    Example usage in workflow:
        ```yaml
        - id: normalize_version
          plugin: jira
          step: normalize_version
          requires:
            - fix_version
        ```
    """
    # Get version from context
    version = ctx.get("fix_version")

    if not version:
        return Error("No fix_version found in context")

    # Normalize version format
    parts = version.split(".")

    if len(parts) == 2:
        # Version is YY.W (e.g., "26.4") → add ".0" to make "26.4.0"
        normalized_version = f"{version}.0"
        was_normalized = True
    elif len(parts) == 3:
        # Version is already YY.W.B (e.g., "26.4.0") → leave as is
        normalized_version = version
        was_normalized = False
    else:
        # Invalid format
        return Error(
            f"Invalid version format: {version}. Expected YY.W or YY.W.B (e.g., '26.4' or '26.4.0')"
        )

    # Textual TUI (new UI)
    if ctx.textual:
        from titan_cli.ui.tui.widgets import Panel

        if was_normalized:
            ctx.textual.text("")
            ctx.textual.text("🔧 Normalizando Versión", markup="bold cyan")
            ctx.textual.text("")
            ctx.textual.text(f"Versión original: {version}", markup="dim")
            ctx.textual.text(f"Versión normalizada: {normalized_version}", markup="bold green")
            ctx.textual.text("")
            ctx.textual.mount(
                Panel(
                    f"Versión normalizada de '{version}' a '{normalized_version}'",
                    panel_type="info"
                )
            )
        else:
            ctx.textual.text("")
            ctx.textual.text(f"✓ Versión ya tiene formato correcto: {normalized_version}", markup="green")
            ctx.textual.text("")

    # Rich UI (legacy)
    elif ctx.ui:
        if was_normalized:
            ctx.ui.text.warning(f"⚠️  Version '{version}' normalized to '{normalized_version}'")
        else:
            ctx.ui.text.success(f"✓ Version already correct: {normalized_version}")

    # Update context with normalized version
    ctx.set("fix_version", normalized_version)

    return Success(
        f"Version normalized: {normalized_version}",
        metadata={
            "fix_version": normalized_version,
            "original_version": version,
            "was_normalized": was_normalized
        }
    )


__all__ = ["normalize_version_step"]
