# plugins/titan-plugin-git/titan_plugin_git/steps/handle_changes_step.py
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from titan_plugin_git.exceptions import GitClientError, GitCommandError
from titan_plugin_git.messages import msg


def handle_uncommitted_changes_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Handles uncommitted changes before creating a PR.

    If there are uncommitted changes, prompts the user to:
    1. Commit them (optionally with AI-generated message)
    2. Stash them
    3. Cancel the operation

    Requires:
        ctx.git: An initialized GitClient.
        ctx.views.prompts: A PromptsRenderer instance.

    Inputs (from ctx.data):
        git_status (GitStatus): The git status object.
        ai_available (bool, optional): Whether AI is available for commit messages.

    Outputs (saved to ctx.data):
        stashed_changes (bool): True if changes were stashed.
        commit_hash (str, optional): The hash of the created commit if user chose to commit.

    Returns:
        Success: If changes were handled successfully (committed or stashed).
        Error: If the operation fails or user cancels.
        Skip: If there are no uncommitted changes.
    """
    # Skip if working directory is clean
    git_status = ctx.data.get("git_status")
    if not git_status or git_status.is_clean:
        return Skip("No uncommitted changes to handle.", silent=True)

    if not ctx.git:
        return Error(msg.Steps.Commit.GIT_CLIENT_NOT_AVAILABLE)

    # Show uncommitted changes summary
    changes_summary = []
    if git_status.staged_files:
        changes_summary.append(f"Staged files: {len(git_status.staged_files)}")
    if git_status.modified_files:
        changes_summary.append(f"Modified files: {len(git_status.modified_files)}")
    if git_status.untracked_files:
        changes_summary.append(f"Untracked files: {len(git_status.untracked_files)}")

    ctx.ui.text.warning(f"⚠️  You have uncommitted changes: {', '.join(changes_summary)}")

    # Prompt user for action
    try:
        choices = [
            ("commit", "Commit changes (you'll be prompted for a message)"),
            ("stash", "Stash changes (temporarily save them)"),
            ("cancel", "Cancel PR creation")
        ]

        # If AI is available, offer AI commit message option
        if ctx.ai:
            choices.insert(0, ("ai_commit", "Commit with AI-generated message"))

        action = ctx.views.prompts.ask_choice(
            "How do you want to handle uncommitted changes?",
            choices
        )

        if action == "cancel":
            return Error("User cancelled PR creation due to uncommitted changes.")

        elif action == "stash":
            # Stash changes
            try:
                stash_message = f"Titan CLI: Auto-stash before PR creation"
                success = ctx.git.stash_push(message=stash_message)
                if success:
                    ctx.ui.text.success(f"✅ Changes stashed successfully")
                    return Success(
                        "Changes stashed successfully",
                        metadata={"stashed_changes": True, "stash_message": stash_message}
                    )
                else:
                    return Error("Failed to stash changes")
            except (GitClientError, GitCommandError) as e:
                return Error(f"Failed to stash changes: {e}")

        elif action == "ai_commit":
            # Generate AI commit message and commit
            try:
                # Get uncommitted diff
                diff = ctx.git.get_uncommitted_diff()
                if not diff:
                    return Error("No changes to commit")

                # Build AI prompt
                all_files = git_status.modified_files + git_status.untracked_files + git_status.staged_files
                files_summary = "\n".join([f"  - {f}" for f in all_files]) if all_files else "(checking diff)"

                # Limit diff size to avoid token overflow
                diff_preview = diff[:4000] if len(diff) > 4000 else diff
                if len(diff) > 4000:
                    diff_preview += "\n\n... (diff truncated for brevity)"

                prompt = f"""Analyze these code changes and generate a conventional commit message.

## Changed Files ({len(all_files)} total)
{files_summary}

## Diff
```diff
{diff_preview}
```

## Instructions
Generate a single conventional commit message following this format:
- type(scope): description
- Types: feat, fix, refactor, docs, test, chore, style, perf
- Scope: area affected (e.g., auth, api, ui)
- Description: brief summary in imperative mood (max 72 chars)

Examples:
- feat(auth): add OAuth2 integration
- fix(api): resolve race condition in cache
- refactor(ui): simplify menu component structure

Return ONLY the commit message, nothing else."""

                ctx.ui.text.info("🤖 Generating commit message with AI...")

                # Call AI
                from titan_cli.ai.models import AIMessage
                messages = [AIMessage(role="user", content=prompt)]
                response = ctx.ai.generate(messages, max_tokens=150, temperature=0.7)

                commit_message = response.content.strip().strip('"').strip("'").strip()

                # Show the message and ask for confirmation
                ctx.ui.text.info("\n📝 AI-generated commit message:")
                ctx.ui.text.info(f"\n{commit_message}\n")

                confirm = ctx.views.prompts.ask_yes_no("Use this commit message?", default=True)
                if not confirm:
                    # Fall through to manual commit
                    action = "commit"
                else:
                    # Commit with AI message
                    commit_hash = ctx.git.commit(message=commit_message, all=True)
                    ctx.ui.text.success(f"✅ Changes committed: {commit_hash[:8]}")
                    return Success(
                        f"Changes committed with AI message: {commit_hash}",
                        metadata={"commit_hash": commit_hash, "commit_message": commit_message}
                    )
            except Exception as e:
                ctx.ui.text.warning(f"⚠️  AI commit failed: {e}")
                ctx.ui.text.info("Falling back to manual commit message...")
                action = "commit"

        if action == "commit":
            # Prompt for manual commit message
            try:
                commit_message = ctx.views.prompts.ask_multiline(
                    "Enter commit message:",
                    default_text="# Enter your commit message above this line"
                )

                if not commit_message or commit_message.strip().startswith("#"):
                    return Error("Commit message cannot be empty")

                # Commit changes
                commit_hash = ctx.git.commit(message=commit_message, all=True)
                ctx.ui.text.success(f"✅ Changes committed: {commit_hash[:8]}")
                return Success(
                    f"Changes committed: {commit_hash}",
                    metadata={"commit_hash": commit_hash, "commit_message": commit_message}
                )
            except (GitClientError, GitCommandError) as e:
                return Error(f"Failed to commit changes: {e}")

    except (KeyboardInterrupt, EOFError):
        return Error("User cancelled.")
    except Exception as e:
        return Error(f"Failed to handle uncommitted changes: {e}")
