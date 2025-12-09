from typing import Any

class Messages:
    class Prompts:
        ENTER_COMMIT_MESSAGE: str = "Enter commit message:"

    class Git:
        """Git operations messages"""
        CLI_NOT_FOUND: str = "Git CLI not found. Please install Git."
        NOT_A_REPOSITORY: str = "'{repo_path}' is not a git repository"
        COMMAND_FAILED: str = "Git command failed: {error_msg}"
        UNEXPECTED_ERROR: str = "An unexpected error occurred: {e}"
        UNCOMMITTED_CHANGES_OVERWRITE_KEYWORD: str = "would be overwritten"
        CANNOT_CHECKOUT_UNCOMMITTED_CHANGES: str = "Cannot checkout: uncommitted changes would be overwritten"
        MERGE_CONFLICT_KEYWORD: str = "Merge conflict"
        MERGE_CONFLICT_WHILE_UPDATING: str = "Merge conflict while updating branch '{branch}'"
        AUTO_STASH_MESSAGE: str = "titan-cli-auto-stash at {timestamp}"
        CANNOT_CHECKOUT_UNCOMMITTED_CHANGES_EXIST: str = "Cannot checkout {branch}: uncommitted changes exist"
        STASH_FAILED_BEFORE_CHECKOUT: str = "Failed to stash changes before checkout"
        SAFE_SWITCH_STASH_MESSAGE: str = "titan-cli-safe-switch: from {current} to {branch}"
        
        # Commits
        COMMITTING = "Committing changes..."
        COMMIT_SUCCESS = "Committed: {sha}"
        COMMIT_FAILED = "Commit failed: {error}"
        NO_CHANGES = "No changes to commit"

        # Branches
        BRANCH_CREATING = "Creating branch: {name}"
        BRANCH_CREATED = "Branch created: {name}"
        BRANCH_SWITCHING = "Switching to branch: {name}"
        BRANCH_SWITCHED = "Switched to branch: {name}"
        BRANCH_DELETING = "Deleting branch: {name}"
        BRANCH_DELETED = "Branch deleted: {name}"
        BRANCH_EXISTS = "Branch already exists: {name}"
        BRANCH_NOT_FOUND = "Branch not found: {name}"
        BRANCH_INVALID_NAME = "Invalid branch name: {name}"
        BRANCH_PROTECTED = "Cannot delete protected branch: {branch}"

        # Push/Pull
        PUSHING = "Pushing to remote..."
        PUSH_SUCCESS = "Pushed to {remote}/{branch}"
        PUSH_FAILED = "Push failed: {error}"
        PULLING = "Pulling from remote..."
        PULL_SUCCESS = "Pulled from {remote}/{branch}"
        PULL_FAILED = "Pull failed: {error}"

        # Status
        STATUS_CLEAN = "Working directory clean"
        STATUS_DIRTY = "Uncommitted changes detected"

        # Repository
        REPO_INIT = "Initializing git repository..."
        REPO_INITIALIZED = "Git repository initialized"
    
    class Steps:
        class Status:
            GIT_CLIENT_NOT_AVAILABLE: str = "Git client is not available in the workflow context."
            STATUS_RETRIEVED_SUCCESS: str = "Git status retrieved successfully."
            WORKING_DIRECTORY_NOT_CLEAN: str = " Working directory is not clean."
            FAILED_TO_GET_STATUS: str = "Failed to get git status: {e}"

        class Commit:
            GIT_CLIENT_NOT_AVAILABLE: str = "Git client is not available in the workflow context."
            COMMIT_MESSAGE_REQUIRED: str = "Commit message cannot be empty."
            COMMIT_SUCCESS: str = "Commit created successfully: {commit_hash}"
            CLIENT_ERROR_DURING_COMMIT: str = "Git client error during commit: {e}"
            COMMAND_FAILED_DURING_COMMIT: str = "Git command failed during commit: {e}"
            UNEXPECTED_ERROR_DURING_COMMIT: str = "An unexpected error occurred during commit: {e}"

        class Push:
            GIT_CLIENT_NOT_AVAILABLE: str = "Git client is not available in the workflow context."
            PUSH_FAILED: str = "Git push failed: {e}"

        class HandleChanges:
            GIT_CLIENT_NOT_AVAILABLE: str = "Git client is not available in the workflow context."
            NO_UNCOMMITTED_CHANGES: str = "No uncommitted changes to handle."
            UNCOMMITTED_CHANGES_WARNING: str = "⚠️  You have uncommitted changes: {summary}"

            # Prompts
            PROMPT_HOW_TO_HANDLE: str = "How do you want to handle uncommitted changes?"
            CHOICE_AI_COMMIT: str = "Commit with AI-generated message"
            CHOICE_MANUAL_COMMIT: str = "Commit changes (you'll be prompted for a message)"
            CHOICE_STASH: str = "Stash changes (temporarily save them)"
            CHOICE_CANCEL: str = "Cancel PR creation"

            # Messages
            USER_CANCELLED: str = "User cancelled PR creation due to uncommitted changes."
            STASH_SUCCESS: str = "✅ Changes stashed successfully"
            STASH_FAILED: str = "Failed to stash changes"
            STASH_ERROR: str = "Failed to stash changes: {e}"

            # AI Commit
            AI_GENERATING: str = "🤖 Generating commit message with AI..."
            AI_GENERATED_MESSAGE: str = "\n📝 AI-generated commit message:"
            AI_CONFIRM_PROMPT: str = "Use this commit message?"
            AI_FAILED_WARNING: str = "⚠️  AI commit failed: {e}"
            AI_FALLBACK: str = "Falling back to manual commit message..."

            # Manual Commit
            COMMIT_PROMPT: str = "Enter commit message:"
            COMMIT_PROMPT_DEFAULT: str = "# Enter your commit message above this line"
            COMMIT_MESSAGE_EMPTY: str = "Commit message cannot be empty"
            COMMIT_SUCCESS: str = "✅ Changes committed: {commit_hash_short}"
            COMMIT_SUCCESS_FULL: str = "Changes committed: {commit_hash}"
            COMMIT_SUCCESS_AI: str = "Changes committed with AI message: {commit_hash}"
            COMMIT_FAILED: str = "Failed to commit changes: {e}"

            # Errors
            NO_CHANGES_TO_COMMIT: str = "No changes to commit"
            AI_MESSAGE_GENERATION_FAILED: str = "Failed to generate AI commit message"
            USER_CANCELLED_OPERATION: str = "User cancelled."
            HANDLE_CHANGES_FAILED: str = "Failed to handle uncommitted changes: {e}"

            # Stash
            STASH_MESSAGE_TEMPLATE: str = "Titan CLI: Auto-stash before PR creation"
            STASH_RESULT_SUCCESS: str = "Changes stashed successfully"

    class Plugin:
        GIT_CLIENT_INIT_WARNING: str = "Warning: GitPlugin could not initialize GitClient: {e}"
        GIT_CLIENT_NOT_AVAILABLE: str = "GitPlugin not initialized or Git CLI not available."



msg = Messages()
