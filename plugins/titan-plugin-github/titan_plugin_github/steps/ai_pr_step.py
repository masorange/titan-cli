# plugins/titan-plugin-github/titan_plugin_github/steps/ai_pr_step.py
"""
AI-powered PR description generation step.

Uses PRAgent to analyze branch context and generate PR content.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from titan_cli.ui.tui.widgets import Panel

from ..agents import PRAgent
from ..messages import msg


def ai_suggest_pr_description_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Generate PR title and description using PRAgent.

    Uses PRAgent to analyze the complete branch context and generate:
    - PR title following conventional commits
    - PR description following template (if exists)
    - Appropriate detail level based on PR size

    Requires:
        ctx.ai: An initialized AIClient
        ctx.git: An initialized GitClient
        ctx.github: An initialized GitHubClient

    Inputs (from ctx.data):
        pr_head_branch (str): The head branch for the PR

    Outputs (saved to ctx.data):
        pr_title (str): AI-generated PR title
        pr_body (str): AI-generated PR description
        pr_size (str): Size classification (small/medium/large/very large)
        ai_generated (bool): True if AI generated the content

    Returns:
        Success: PR description generated
        Skip: AI not configured or user declined
        Error: Failed to generate PR description
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Check if AI is configured
    if not ctx.ai or not ctx.ai.is_available():
        ctx.textual.mount(
            Panel(
                text=msg.GitHub.AI.AI_NOT_CONFIGURED,
                panel_type="info"
            )
        )
        return Skip(msg.GitHub.AI.AI_NOT_CONFIGURED)

    # Get Git client
    if not ctx.git:
        return Error(msg.GitHub.AI.GIT_CLIENT_NOT_AVAILABLE)

    # Get branch info
    head_branch = ctx.get("pr_head_branch")
    if not head_branch:
        return Error(msg.GitHub.AI.MISSING_PR_HEAD_BRANCH)

    base_branch = ctx.git.main_branch

    try:
        # Show progress
        ctx.textual.text(msg.GitHub.AI.ANALYZING_BRANCH_DIFF.format(
            head_branch=head_branch,
            base_branch=base_branch
        ), markup="dim")

        # Create PRAgent instance
        pr_agent = PRAgent(
            ai_client=ctx.ai,
            git_client=ctx.git,
            github_client=ctx.github
        )

        # Use PRAgent to analyze and generate PR content with loading indicator
        with ctx.textual.loading(msg.GitHub.AI.GENERATING_PR_DESCRIPTION):
            analysis = pr_agent.analyze_and_plan(
                head_branch=head_branch,
                base_branch=base_branch,
                auto_stage=False  # Only analyze branch commits, not uncommitted changes
            )

        # Check if PR content was generated (need commits in branch)
        if not analysis.pr_title or not analysis.pr_body:
            ctx.textual.mount(
                Panel(
                    text="No commits found in branch to generate PR description.",
                    panel_type="info"
                )
            )
            return Skip("No commits found for PR generation")

        # Show PR size info
        if analysis.pr_size:
            ctx.textual.text(msg.GitHub.AI.PR_SIZE_INFO.format(
                pr_size=analysis.pr_size,
                files_changed=analysis.files_changed,
                diff_lines=analysis.lines_changed,
                max_chars="varies by size"
            ), markup="dim")

        # Show PR preview to user
        ctx.textual.text("")  # spacing
        ctx.textual.text(msg.GitHub.AI.AI_GENERATED_PR_TITLE, markup="bold")
        ctx.textual.text("")  # spacing

        # Show title
        ctx.textual.text(msg.GitHub.AI.TITLE_LABEL, markup="bold")
        ctx.textual.text(f"  {analysis.pr_title}", markup="cyan")

        # Warn if title is too long
        if len(analysis.pr_title) > 72:
            ctx.textual.text(msg.GitHub.AI.TITLE_TOO_LONG_WARNING.format(
                length=len(analysis.pr_title)
            ), markup="yellow")

        ctx.textual.text("")  # spacing

        # Show description
        ctx.textual.text(msg.GitHub.AI.DESCRIPTION_LABEL, markup="bold")
        # Render markdown in a scrollable container
        ctx.textual.markdown(analysis.pr_body)

        ctx.textual.text("")  # spacing

        # Single confirmation for both title and description
        use_ai_pr = ctx.textual.ask_confirm(
            msg.GitHub.AI.CONFIRM_USE_AI_PR,
            default=True
        )

        if not use_ai_pr:
            ctx.textual.text(msg.GitHub.AI.AI_SUGGESTION_REJECTED, markup="yellow")
            return Skip("User rejected AI-generated PR")

        # Show success panel
        ctx.textual.mount(
            Panel(
                text="AI generated PR description successfully",
                panel_type="success"
            )
        )

        # Success - save to context
        metadata = {
            "ai_generated": True,
            "pr_title": analysis.pr_title,
            "pr_body": analysis.pr_body,
            "pr_size": analysis.pr_size
        }

        return Success(
            msg.GitHub.AI.AI_GENERATED_PR_DESCRIPTION_SUCCESS,
            metadata=metadata
        )

    except Exception as e:
        # Don't fail the workflow, just skip AI and use manual prompts
        ctx.textual.text(msg.GitHub.AI.AI_GENERATION_FAILED.format(e=e), markup="yellow")
        ctx.textual.text(msg.GitHub.AI.FALLBACK_TO_MANUAL, markup="dim")

        return Skip(msg.GitHub.AI.AI_GENERATION_FAILED.format(e=e))


# Export for plugin registration
__all__ = ["ai_suggest_pr_description_step"]
