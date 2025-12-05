# plugins/titan-plugin-git/titan_plugin_git/steps/prompt_step.py
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from titan_plugin_git.messages import msg

def prompt_for_commit_message_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Prompts the user for a commit message and saves it to the context.
    Skips if the working directory is clean.

    Sets:
        ctx.data['commit_message']: The message entered by the user.
    """
    # Skip if there's nothing to commit
    git_status = ctx.data.get("git_status")
    if git_status and git_status.is_clean:
        return Skip("Working directory is clean, no need for a commit message.")

    try:
        # Using a generic prompt message, can be customized if needed
        message = ctx.views.prompts.ask_text(msg.Prompts.ENTER_COMMIT_MESSAGE)
        if not message:
            return Error(msg.Steps.Commit.COMMIT_MESSAGE_REQUIRED)
        return Success(
            message="Commit message captured",
            metadata={"commit_message": message}
        )
    except (KeyboardInterrupt, EOFError):
        return Error("User cancelled.")
    except Exception as e:
        return Error(f"Failed to prompt for commit message: {e}", exception=e)
