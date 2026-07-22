"""
Enums for the AI execution routing layer.

See harness/ai_execution_service/README.md for the full conceptual model
(AI task -> required capabilities -> available providers -> preferences ->
persistence/fallback) that these enums are drawn from.
"""

from enum import StrEnum


class AITask(StrEnum):
    """
    Recommended task vocabulary for official plugins.

    `AIExecutionRequest.task`/`AIRoutePolicy.task` are plain `str`, not this
    enum, so community plugins can identify their own tasks (used as routing
    and preference-persistence keys) without needing a core code change.
    These members are the known values official plugins should reuse.
    """

    COMMIT_MESSAGE = "commit_message"
    PR_DESCRIPTION = "pr_description"
    ISSUE_GENERATION = "issue_generation"
    JIRA_ANALYSIS = "jira_analysis"
    CODE_REVIEW_PLAN = "code_review_plan"
    CODE_REVIEW_FINDINGS = "code_review_findings"
    RESPOND_PR_COMMENT = "respond_pr_comment"
    FIX_TEST_FAILURES = "fix_test_failures"
    FIX_LINT_FAILURES = "fix_lint_failures"
    GENERIC_ASSISTANT = "generic_assistant"


class AICapability(StrEnum):
    """A single capability a provider may or may not support for a given task."""

    TEXT_GENERATION = "text_generation"
    STRUCTURED_OUTPUT = "structured_output"
    READ_REPO = "read_repo"
    WRITE_FILES = "write_files"
    RUN_COMMANDS = "run_commands"
    INTERACTIVE_SESSION = "interactive_session"
    CREATE_ARTIFACTS = "create_artifacts"
    HUMAN_IN_LOOP = "human_in_loop"


class AIProviderType(StrEnum):
    """Execution provider that can fulfill an AI task."""

    REMOTE = "remote"
    CLI_HEADLESS = "cli_headless"
    CLI_INTERACTIVE = "cli_interactive"
    REMOTE_STRUCTURED = "remote_structured"
    OFF = "off"


__all__ = [
    "AITask",
    "AICapability",
    "AIProviderType",
]
