# plugins/titan-plugin-git/titan_plugin_git/steps/diff_summary_step.py
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from titan_plugin_git.messages import msg


def show_uncommitted_diff_summary(ctx: WorkflowContext) -> WorkflowResult:
    """
    Show summary of uncommitted changes (git diff --stat).

    Provides a visual overview of files changed and lines modified
    before generating commit messages.

    Returns:
        Success: Always (even if no changes, for workflow continuity)
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    if not ctx.git:
        return Error(msg.Steps.Push.GIT_CLIENT_NOT_AVAILABLE)

    # Begin step container
    ctx.textual.begin_step("Show Changes Summary")

    try:
        # Get diff stat for uncommitted changes
        stat_output = ctx.git._run_command(["git", "diff", "--stat", "HEAD"])

        if not stat_output or not stat_output.strip():
            ctx.textual.text("No uncommitted changes to show", markup="dim")
            ctx.textual.end_step("success")
            return Success("No changes")

        # Show the stat summary with colors
        ctx.textual.text("")  # spacing
        ctx.textual.text("Changes summary:", markup="bold")
        ctx.textual.text("")  # spacing

        # Parse lines to find max filename length for alignment
        file_lines = []
        summary_lines = []
        max_filename_len = 0

        for line in stat_output.split('\n'):
            if not line.strip():
                continue

            if '|' in line:
                parts = line.split('|')
                filename = parts[0].strip()
                stats = '|'.join(parts[1:]) if len(parts) > 1 else ''
                file_lines.append((filename, stats))
                max_filename_len = max(max_filename_len, len(filename))
            else:
                summary_lines.append(line)

        # Display aligned file changes
        for filename, stats in file_lines:
            # Pad filename to align pipes
            padded_filename = filename.ljust(max_filename_len)

            # Replace + with green and - with red
            stats = stats.replace('+', '[green]+[/green]')
            stats = stats.replace('-', '[red]-[/red]')

            ctx.textual.text(f"  {padded_filename} | {stats}")

        # Display summary lines
        for line in summary_lines:
            colored_line = line.replace('(+)', '[green](+)[/green]')
            colored_line = colored_line.replace('(-)', '[red](-)[/red]')
            ctx.textual.text(f"  {colored_line}", markup="dim")

        ctx.textual.text("")  # spacing

        # End step container with success
        ctx.textual.end_step("success")

        return Success("Diff summary displayed")

    except Exception as e:
        # Don't fail the workflow, just skip
        ctx.textual.end_step("skip")
        return Skip(f"Could not show diff summary: {e}")


def show_branch_diff_summary(ctx: WorkflowContext) -> WorkflowResult:
    """
    Show summary of branch changes (git diff base...head --stat).

    Provides a visual overview of files changed between branches
    before generating PR descriptions.

    Inputs (from ctx.data):
        pr_head_branch (str): Head branch name

    Returns:
        Success: Always (even if no changes, for workflow continuity)
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Begin step container
    ctx.textual.begin_step("Show Branch Changes Summary")

    if not ctx.git:
        ctx.textual.text(msg.Steps.Push.GIT_CLIENT_NOT_AVAILABLE, markup="red")
        ctx.textual.end_step("error")
        return Error(msg.Steps.Push.GIT_CLIENT_NOT_AVAILABLE)

    head_branch = ctx.get("pr_head_branch")
    if not head_branch:
        ctx.textual.text("No head branch specified", markup="dim")
        ctx.textual.end_step("skip")
        return Skip("No head branch specified")

    base_branch = ctx.git.main_branch

    try:
        # Get diff stat between branches
        stat_output = ctx.git._run_command([
            "git", "diff", "--stat", f"{base_branch}...{head_branch}"
        ])

        if not stat_output or not stat_output.strip():
            ctx.textual.text(f"No changes between {base_branch} and {head_branch}", markup="dim")
            ctx.textual.end_step("success")
            return Success("No changes")

        # Show the stat summary with colors
        ctx.textual.text("")  # spacing
        ctx.textual.text(f"Changes in {head_branch} vs {base_branch}:", markup="bold")
        ctx.textual.text("")  # spacing

        # Parse lines to find max filename length for alignment
        file_lines = []
        summary_lines = []
        max_filename_len = 0

        for line in stat_output.split('\n'):
            if not line.strip():
                continue

            if '|' in line:
                parts = line.split('|')
                filename = parts[0].strip()
                stats = '|'.join(parts[1:]) if len(parts) > 1 else ''
                file_lines.append((filename, stats))
                max_filename_len = max(max_filename_len, len(filename))
            else:
                summary_lines.append(line)

        # Display aligned file changes
        for filename, stats in file_lines:
            # Pad filename to align pipes
            padded_filename = filename.ljust(max_filename_len)

            # Replace + with green and - with red
            stats = stats.replace('+', '[green]+[/green]')
            stats = stats.replace('-', '[red]-[/red]')

            ctx.textual.text(f"  {padded_filename} | {stats}")

        # Display summary lines
        for line in summary_lines:
            colored_line = line.replace('(+)', '[green](+)[/green]')
            colored_line = colored_line.replace('(-)', '[red](-)[/red]')
            ctx.textual.text(f"  {colored_line}", markup="dim")

        ctx.textual.text("")  # spacing

        ctx.textual.end_step("success")
        return Success("Branch diff summary displayed")

    except Exception as e:
        # Don't fail the workflow, just skip
        ctx.textual.text(f"Could not show branch diff summary: {e}", markup="yellow")
        ctx.textual.end_step("skip")
        return Skip(f"Could not show branch diff summary: {e}")


__all__ = ["show_uncommitted_diff_summary", "show_branch_diff_summary"]
