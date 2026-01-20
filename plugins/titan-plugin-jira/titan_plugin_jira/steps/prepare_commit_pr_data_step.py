"""
Prepare commit message and PR data for release notes workflow.
"""

from pathlib import Path
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def prepare_commit_pr_data_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Prepare commit message and PR data for release notes.

    Sets the following in context for git and github plugins:
        - commit_message: "docs: Add release notes for {fix_version}"
        - pr_title: "notes: Add release notes for {fix_version}"
        - pr_body: Multi-line PR description (from template)
        - pr_head_branch: Current branch name
        - pr_base_branch: "develop" (target branch for PR)
        - pr_labels: Auto-assigned labels (searches for "release notes" label)
        - pr_assignees: Auto-assigned to current GitHub user
        - all_files: True (to commit all changes)

    Expected context data:
        fix_version (str): Version number (e.g., "26.4.0")
        platform (str, optional): Platform name (default: "iOS")
        issues (list, optional): List of JIRA issues (default: [])

    Returns:
        Success: Data prepared
        Error: Missing required data

    Example usage in workflow:
        ```yaml
        - id: prepare_data
          plugin: jira
          step: prepare_commit_pr_data
          requires:
            - fix_version
            - issues
          params:
            platform: "iOS"
        ```
    """
    # Get data from context
    fix_version = ctx.get("fix_version")
    platform = ctx.get("platform", "iOS")
    issues = ctx.get("issues", [])

    if not fix_version:
        return Error("No fix_version found in context")

    if not ctx.git:
        return Error("GitClient not available in context")

    # Build commit message (user specified: "docs: Add release notes for X.X.X")
    commit_message = f"docs: Add release notes for {fix_version}"

    # Build PR title (user specified: "notes: Add release notes for X.X.X")
    pr_title = f"notes: Add release notes for {fix_version}"

    # Build issue list for PR body
    issue_list = ""
    if issues:
        try:
            issue_list = "\n".join([f"- [{issue.key}] {issue.summary}" for issue in issues[:10]])
            if len(issues) > 10:
                issue_list += f"\n- ... y {len(issues) - 10} issues más"
        except AttributeError:
            # Fallback if issues don't have key/summary attributes
            issue_list = f"_{len(issues)} issues incluidos en esta versión_"
    else:
        issue_list = "_No se encontraron issues para esta versión_"

    # Read PR template from plugin's templates directory
    try:
        # Get template path relative to this file
        template_path = Path(__file__).parent.parent / "templates" / "release_notes_pr.md"

        if ctx.textual:
            ctx.textual.text(f"Template path: {template_path}", markup="dim")
            ctx.textual.text(f"Template exists: {template_path.exists()}", markup="dim")

        if template_path.exists():
            with open(template_path, "r", encoding="utf-8") as f:
                pr_body = f.read()

            # Replace placeholders
            pr_body = pr_body.replace("{version}", fix_version)
            pr_body = pr_body.replace("{platform}", platform.lower())
            pr_body = pr_body.replace("{issue_list}", issue_list)

            # Mark platform checkbox
            if platform.lower() == "ios":
                pr_body = pr_body.replace("- [ ] iOS", "- [x] iOS")
            else:
                pr_body = pr_body.replace("- [ ] Android", "- [x] Android")
        else:
            # Fallback if template doesn't exist
            pr_body = f"""# Release Notes {fix_version}

## 📋 Resumen

Este PR añade las release notes para la versión **{fix_version}**.

## 📝 Cambios Incluidos

- Añadido archivo `release-notes-{fix_version}.md`
- Actualizado LatestPublishers.md (solo iOS)

## 🔍 Issues Incluidos

{issue_list}

---

🤖 **Generado automáticamente** por Titan CLI
"""
    except Exception as e:
        # Fallback on error
        pr_body = f"""# Release Notes {fix_version}

Este PR añade las release notes para la versión **{fix_version}**.

**Issues incluidos:** {len(issues) if issues else 0}

🤖 Generado automáticamente por Titan CLI
"""

    # Get current branch for PR
    try:
        pr_head_branch = ctx.git.get_current_branch()
    except Exception as e:
        return Error(f"Error getting current branch: {e}")

    # Auto-assign label for release notes PR (dynamic search for matching label)
    pr_labels = None
    if ctx.github:
        try:
            all_labels = ctx.github.list_labels()
            # Search for label containing "release notes" (case-insensitive)
            matching_labels = [label for label in all_labels if "release notes" in label.lower()]
            if matching_labels:
                pr_labels = [matching_labels[0]]
                if ctx.textual:
                    ctx.textual.text(f"Auto-assigning label: {matching_labels[0]}", markup="dim")
                elif ctx.ui:
                    ctx.ui.text.body(f"Auto-assigning label: {matching_labels[0]}", style="dim")
            else:
                # Warn if no matching label found
                if ctx.textual:
                    ctx.textual.text("No 'release notes' label found in repository", markup="yellow")
                elif ctx.ui:
                    ctx.ui.text.body("No 'release notes' label found in repository", style="yellow")
        except Exception as e:
            # Log warning but continue without label
            if ctx.textual:
                ctx.textual.text(f"Could not get labels for auto-assign: {e}", markup="yellow")
            elif ctx.ui:
                ctx.ui.text.body(f"Could not get labels for auto-assign: {e}", style="yellow")

    # Auto-assign PR to current GitHub user
    pr_assignees = None
    if ctx.github:
        try:
            current_user = ctx.github.get_current_user()
            pr_assignees = [current_user]
            if ctx.textual:
                ctx.textual.text(f"Auto-assigning PR to: {current_user}", markup="dim")
            elif ctx.ui:
                ctx.ui.text.body(f"Auto-assigning PR to: {current_user}", style="dim")
        except Exception as e:
            # Log warning but continue without assignee
            if ctx.textual:
                ctx.textual.text(f"Could not get current user for auto-assign: {e}", markup="yellow")
            elif ctx.ui:
                ctx.ui.text.body(f"Could not get current user for auto-assign: {e}", style="yellow")

    # Textual TUI (new UI)
    if ctx.textual:
        from titan_cli.ui.tui.widgets import Panel

        ctx.textual.text("")
        ctx.textual.text("📝 Preparando Datos para Commit y PR", markup="bold cyan")
        ctx.textual.text("")

        ctx.textual.text("Commit Message:", markup="bold")
        ctx.textual.text(f"  {commit_message}", markup="dim")
        ctx.textual.text("")

        ctx.textual.text("PR Title:", markup="bold")
        ctx.textual.text(f"  {pr_title}", markup="dim")
        ctx.textual.text("")

        ctx.textual.text("PR Head Branch:", markup="bold")
        ctx.textual.text(f"  {pr_head_branch}", markup="dim")
        ctx.textual.text("")

        ctx.textual.text("PR Body Preview:", markup="bold")
        preview = pr_body[:200] + "..." if len(pr_body) > 200 else pr_body
        ctx.textual.text(f"  {preview}", markup="dim")
        ctx.textual.text("")

        if pr_labels:
            ctx.textual.text("Labels:", markup="bold")
            ctx.textual.text(f"  {', '.join(pr_labels)}", markup="green")
            ctx.textual.text("")

        ctx.textual.mount(
            Panel("Datos preparados para commit y PR", panel_type="success")
        )

    # Rich UI (legacy)
    elif ctx.ui:
        ctx.ui.text.info(f"📝 Commit: {commit_message}")
        ctx.ui.text.info(f"🚀 PR: {pr_title}")
        ctx.ui.text.info(f"🌿 Branch: {pr_head_branch}")
        ctx.ui.text.info(f"📄 PR Body Length: {len(pr_body)} chars")
        ctx.ui.panel.print(f"PR Body Preview:\n{pr_body[:300]}...", panel_type="info")

    # Debug: Show full PR body before setting in context
    if ctx.textual:
        ctx.textual.text("", markup="dim")
        ctx.textual.text("=" * 80, markup="dim")
        ctx.textual.text("FULL PR BODY:", markup="bold yellow")
        ctx.textual.text(pr_body, markup="dim")
        ctx.textual.text("=" * 80, markup="dim")
        ctx.textual.text("", markup="dim")

    # DEBUG: Save pr_body to temp file for inspection
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='_pr_body.md', delete=False) as f:
        f.write(pr_body)
        temp_file = f.name
    if ctx.ui:
        ctx.ui.text.info(f"🐛 DEBUG: PR body saved to {temp_file}")
    elif ctx.textual:
        ctx.textual.text(f"🐛 DEBUG: PR body saved to {temp_file}", markup="yellow")

    # Set data in context for git and github plugins to use
    ctx.set("commit_message", commit_message)
    ctx.set("pr_title", pr_title)
    ctx.set("pr_body", pr_body)
    ctx.set("pr_head_branch", pr_head_branch)
    ctx.set("pr_base_branch", "develop")  # Always target develop for release notes
    if pr_labels:
        ctx.set("pr_labels", pr_labels)  # Auto-assign labels (if found)
    if pr_assignees:
        ctx.set("pr_assignees", pr_assignees)  # Auto-assign to current user
    ctx.set("all_files", True)  # Commit all modified/new files

    return Success(
        "Commit and PR data prepared",
        metadata={
            "commit_message": commit_message,
            "pr_title": pr_title,
            "pr_head_branch": pr_head_branch
        }
    )


__all__ = ["prepare_commit_pr_data_step"]
