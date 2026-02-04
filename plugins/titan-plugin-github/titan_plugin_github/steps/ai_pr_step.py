# plugins/titan-plugin-github/titan_plugin_github/steps/ai_pr_step.py
"""
AI-powered PR description generation step.

Uses PRAgent to analyze branch context and generate PR content.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip

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

    # Begin step container
    ctx.textual.begin_step("AI PR Description")

    # Check if AI is configured
    if not ctx.ai or not ctx.ai.is_available():
        ctx.textual.dim_text(msg.GitHub.AI.AI_NOT_CONFIGURED)
        ctx.textual.end_step("skip")
        return Skip(msg.GitHub.AI.AI_NOT_CONFIGURED)

    # Get Git client
    if not ctx.git:
        ctx.textual.end_step("error")
        return Error(msg.GitHub.AI.GIT_CLIENT_NOT_AVAILABLE)

    # Get branch info
    head_branch = ctx.get("pr_head_branch")
    if not head_branch:
        ctx.textual.end_step("error")
        return Error(msg.GitHub.AI.MISSING_PR_HEAD_BRANCH)

    base_branch = ctx.git.main_branch

    try:
        # Show progress
        ctx.textual.dim_text(msg.GitHub.AI.ANALYZING_BRANCH_DIFF.format(
            head_branch=head_branch,
            base_branch=base_branch
        ))

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
            ctx.textual.dim_text("No commits found in branch to generate PR description.")
            ctx.textual.end_step("skip")
            return Skip("No commits found for PR generation")

        # Show PR size info
        if analysis.pr_size:
            ctx.textual.dim_text(msg.GitHub.AI.PR_SIZE_INFO.format(
                pr_size=analysis.pr_size,
                files_changed=analysis.files_changed,
                diff_lines=analysis.lines_changed,
                max_chars="varies by size"
            ))

        # Show PR preview to user
        ctx.textual.text("")  # spacing
        ctx.textual.bold_text(msg.GitHub.AI.AI_GENERATED_PR_TITLE)
        ctx.textual.text("")  # spacing

        # Show title
        ctx.textual.bold_text(msg.GitHub.AI.TITLE_LABEL)
        ctx.textual.primary_text(f"  {analysis.pr_title}")

        # Warn if title is too long
        if len(analysis.pr_title) > 72:
            ctx.textual.warning_text(msg.GitHub.AI.TITLE_TOO_LONG_WARNING.format(
                length=len(analysis.pr_title)
            ))

        ctx.textual.text("")  # spacing

        # Show description
        ctx.textual.bold_text(msg.GitHub.AI.DESCRIPTION_LABEL)
        # Render markdown in a scrollable container
        ctx.textual.markdown(analysis.pr_body)

        ctx.textual.text("")  # spacing

        # Ask user what to do with the AI suggestion
        from titan_cli.ui.tui.widgets import ChoiceOption

        options = [
            ChoiceOption(value="use", label="Use as-is", variant="primary"),
            ChoiceOption(value="edit", label="Edit", variant="default"),
            ChoiceOption(value="reject", label="Reject", variant="error"),
        ]

        choice = ctx.textual.ask_choice(
            "What would you like to do with this PR description?",
            options
        )

        # Handle user choice
        if choice == "reject":
            ctx.textual.warning_text(msg.GitHub.AI.AI_SUGGESTION_REJECTED)
            ctx.textual.end_step("skip")
            return Skip("User rejected AI-generated PR")

        # Store initial values
        pr_title = analysis.pr_title
        pr_body = analysis.pr_body

        if choice == "edit":
            # Edit loop: allow user to edit until they confirm
            while True:
                ctx.textual.text("")
                ctx.textual.dim_text("Edit the PR content below (first line = title, rest = description)")

                # Combine title and body as markdown for editing
                combined_markdown = f"{pr_title}\n\n{pr_body}"

                # Ask user to edit
                edited_content = ctx.textual.ask_multiline(
                    "Edit PR content:",
                    default=combined_markdown
                )

                if not edited_content or not edited_content.strip():
                    ctx.textual.warning_text("PR content cannot be empty")
                    ctx.textual.end_step("skip")
                    return Skip("Empty PR content")

                # Parse: first line = title, rest = body
                lines = edited_content.strip().split("\n", 1)
                pr_title = lines[0].strip()
                pr_body = lines[1].strip() if len(lines) > 1 else ""

                # Show final preview
                ctx.textual.text("")
                ctx.textual.bold_text("Final Preview:")
                ctx.textual.text("")
                ctx.textual.bold_text("Title:")
                ctx.textual.primary_text(f"  {pr_title}")
                ctx.textual.text("")
                ctx.textual.bold_text("Description:")
                ctx.textual.markdown(pr_body)
                ctx.textual.text("")

                # Confirm
                confirmed = ctx.textual.ask_confirm(
                    "Use this PR content?",
                    default=True
                )

                if confirmed:
                    break
                # If not confirmed, loop back to edit

        # Success - save to context
        metadata = {
            "ai_generated": True,
            "pr_title": pr_title,
            "pr_body": pr_body,
            "pr_size": analysis.pr_size
        }

        ctx.textual.end_step("success")
        return Success(
            msg.GitHub.AI.AI_GENERATED_PR_DESCRIPTION_SUCCESS,
            metadata=metadata
        )

    except Exception as e:
        # Don't fail the workflow, just skip AI and use manual prompts
        ctx.textual.warning_text(msg.GitHub.AI.AI_GENERATION_FAILED.format(e=e))
        ctx.textual.dim_text(msg.GitHub.AI.FALLBACK_TO_MANUAL)

        ctx.textual.end_step("skip")
        return Skip(msg.GitHub.AI.AI_GENERATION_FAILED.format(e=e))


# Export for plugin registration
__all__ = ["ai_suggest_pr_description_step"]
