# plugins/titan-plugin-git/titan_plugin_git/steps/ai_commit_message_step.py
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from titan_plugin_git.messages import msg
from titan_cli.ui.tui.widgets import Panel


def ai_generate_commit_message(ctx: WorkflowContext) -> WorkflowResult:
    """
    Generate a commit message using AI based on the current changes.

    Uses AI to analyze the diff of uncommitted changes and generate a
    conventional commit message (type(scope): description).

    Requires:
        ctx.git: An initialized GitClient.
        ctx.ai: An initialized AIClient.

    Inputs (from ctx.data):
        git_status: Current git status with changes.

    Outputs (saved to ctx.data):
        commit_message (str): AI-generated commit message.

    Returns:
        Success: If the commit message was generated successfully.
        Error: If the operation fails.
        Skip: If no changes, AI not configured, or user declined.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Check if AI is configured
    if not ctx.ai or not ctx.ai.is_available():
        ctx.textual.mount(
            Panel(
                text=msg.Steps.AICommitMessage.AI_NOT_CONFIGURED,
                panel_type="info"
            )
        )
        return Skip(msg.Steps.AICommitMessage.AI_NOT_CONFIGURED)

    # Get git client
    if not ctx.git:
        return Error(msg.Steps.AICommitMessage.GIT_CLIENT_NOT_AVAILABLE)

    # Get git status
    git_status = ctx.get('git_status')
    if not git_status or git_status.is_clean:
        ctx.textual.mount(
            Panel(
                text=msg.Steps.AICommitMessage.NO_CHANGES_TO_COMMIT,
                panel_type="info"
            )
        )
        return Skip(msg.Steps.AICommitMessage.NO_CHANGES_TO_COMMIT)

    try:
        # Get diff of uncommitted changes
        ctx.textual.text(msg.Steps.AICommitMessage.ANALYZING_CHANGES, markup="dim")

        # Get diff of all uncommitted changes
        diff_text = ctx.git.get_uncommitted_diff()

        if not diff_text or diff_text.strip() == "":
            return Skip(msg.Steps.AICommitMessage.NO_UNCOMMITTED_CHANGES)

        # Build AI prompt
        # Get list of modified files for the summary
        all_files = git_status.modified_files + git_status.untracked_files + git_status.staged_files
        files_summary = "\n".join([f"  - {f}" for f in all_files]) if all_files else "(checking diff)"

        # Limit diff size to avoid token overflow (keep first 8000 chars)
        diff_preview = diff_text[:8000] if len(diff_text) > 8000 else diff_text
        if len(diff_text) > 8000:
            diff_preview += f"\n\n{msg.Steps.AICommitMessage.DIFF_TRUNCATED}"

        prompt = f"""Analyze these code changes and generate a conventional commit message.

## Changed Files ({len(all_files)} total)
{files_summary}

## Diff
```diff
{diff_preview}
```

## CRITICAL Instructions
Generate ONE single-line conventional commit message following this EXACT format:
- type(scope): Description
- Types: feat, fix, refactor, docs, test, chore, style, perf
- Scope: area affected (e.g., auth, api, ui)
- Description: clear summary in imperative mood, starting with CAPITAL letter (be descriptive, concise, and at least 5 words long)
- NO line breaks, NO body, NO additional explanation

Examples (notice they start with capital letter and are all one line):
- feat(auth): Add OAuth2 integration with Google provider
- fix(api): Resolve race condition in cache invalidation
- refactor(ui): Simplify menu component and remove unused props
- refactor(workflows): Add support for nested workflow execution

Return ONLY the single-line commit message, absolutely nothing else."""

        # Call AI with loading indicator
        from titan_cli.ai.models import AIMessage

        messages = [AIMessage(role="user", content=prompt)]

        with ctx.textual.loading(msg.Steps.AICommitMessage.GENERATING_MESSAGE):
            response = ctx.ai.generate(messages, max_tokens=1024, temperature=0.7)

        commit_message = response.content.strip()

        # Clean up the message (remove quotes, newlines, extra whitespace)
        commit_message = commit_message.strip('"').strip("'").strip()
        # Take only the first line if AI returned multiple lines
        commit_message = commit_message.split('\n')[0].strip()

        # Ensure subject starts with capital letter (conventional commits requirement)
        # Format: type(scope): Description
        if ':' in commit_message:
            parts = commit_message.split(':', 1)
            if len(parts) == 2:
                prefix = parts[0]  # type(scope)
                subject = parts[1].strip()  # description
                # Capitalize first letter of subject
                if subject and subject[0].islower():
                    subject = subject[0].upper() + subject[1:]
                commit_message = f"{prefix}: {subject}"

        # Show preview to user
        ctx.textual.text("")  # spacing
        ctx.textual.text(msg.Steps.AICommitMessage.GENERATED_MESSAGE_TITLE, markup="bold")
        ctx.textual.text(f"  {commit_message}", markup="bold cyan")

        # Warn if message is too long
        if len(commit_message) > 72:
            ctx.textual.text(msg.Steps.AICommitMessage.MESSAGE_LENGTH_WARNING.format(length=len(commit_message)), markup="yellow")

        ctx.textual.text("")  # spacing

        # Ask user if they want to use it
        use_ai = ctx.textual.ask_confirm(
            msg.Steps.AICommitMessage.CONFIRM_USE_MESSAGE,
            default=True
        )

        if not use_ai:
            try:
                manual_message = ctx.textual.ask_text(msg.Prompts.ENTER_COMMIT_MESSAGE)
                if not manual_message:
                    return Error(msg.Steps.Commit.COMMIT_MESSAGE_REQUIRED)

                # Overwrite the metadata to ensure the manual message is used
                return Success(
                    message=msg.Steps.Prompt.COMMIT_MESSAGE_CAPTURED,
                    metadata={"commit_message": manual_message}
                )
            except (KeyboardInterrupt, EOFError):
                return Error(msg.Steps.Prompt.USER_CANCELLED)

        # Show success panel
        ctx.textual.mount(
            Panel(
                text="AI commit message generated successfully",
                panel_type="success"
            )
        )

        # Success - save to context
        return Success(
            msg.Steps.AICommitMessage.SUCCESS_MESSAGE,
            metadata={"commit_message": commit_message}
        )

    except Exception as e:
        ctx.textual.text(msg.Steps.AICommitMessage.GENERATION_FAILED.format(e=e), markup="yellow")
        ctx.textual.text(msg.Steps.AICommitMessage.FALLBACK_TO_MANUAL, markup="dim")

        return Skip(msg.Steps.AICommitMessage.GENERATION_FAILED.format(e=e))


# Export for plugin registration
__all__ = ["ai_generate_commit_message"]
