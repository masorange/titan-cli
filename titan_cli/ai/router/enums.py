"""
Enums for the AI execution routing layer.

Vocabulary the routing layer is built on: an AI task (what the step wants
done) is routed to an execution provider (who does it), optionally pinned by
a persisted user preference.
"""

from enum import StrEnum


class AITask(StrEnum):
    """
    Recommended task vocabulary for official plugins.

    `AIRoutePolicy.task` is a plain `str`, not this enum, so community plugins
    can identify their own tasks (used as routing and preference-persistence
    keys) without needing a core code change. These members are the known
    values official plugins should reuse.
    """

    COMMIT_MESSAGE = "commit_message"
    PR_DESCRIPTION = "pr_description"
    ISSUE_GENERATION = "issue_generation"
    JIRA_ANALYSIS = "jira_analysis"
    CODE_REVIEW_TRIAGE = "code_review_triage"
    CODE_REVIEW_FINDINGS = "code_review_findings"
    RESPOND_PR_COMMENT = "respond_pr_comment"
    FIX_TEST_FAILURES = "fix_test_failures"
    FIX_LINT_FAILURES = "fix_lint_failures"
    GENERIC_ASSISTANT = "generic_assistant"


class AIRouteOrigin(StrEnum):
    """Which rung of the precedence supplied one part of a decision.

    Tracked per part because the instance and the model are resolved independently
    (D-008): a session override can name the CLI while the model still comes from the
    global setting, and one label for the whole decision would be false half the time.

    `STEP` is the one users cannot see coming - an explicit `model=` at the call site,
    which outranks even a key just pressed - so naming it is the point of the exercise.
    """

    STEP = "step"
    SESSION = "session"
    PINNED = "pinned"
    DEFAULT = "default"


class AIProviderType(StrEnum):
    """Execution provider that can fulfill an AI task."""

    REMOTE = "remote"
    CLI_HEADLESS = "cli_headless"
    CLI_INTERACTIVE = "cli_interactive"
    OFF = "off"


# Names and explanations for humans. They live beside the enum, not in the screen that
# renders them, so the configuration screen and a running step call the same thing by the
# same name. The names describe WHO DRIVES rather than how it is wired: "headless" is an
# implementation word, and what a user actually needs to know is whether Titan runs the tool
# and keeps the answer, or hands them the terminal.
PROVIDER_TYPE_LABELS = {
    AIProviderType.REMOTE: "Remote model",
    AIProviderType.CLI_HEADLESS: "CLI, automatic",
    AIProviderType.CLI_INTERACTIVE: "CLI, interactive",
    AIProviderType.OFF: "Off",
}

PROVIDER_TYPE_DESCRIPTIONS = {
    AIProviderType.REMOTE: (
        "Sends the prompt to your AI connection. Fastest, but it cannot see your files."
    ),
    AIProviderType.CLI_HEADLESS: (
        "Titan runs your CLI in the background and keeps its answer. "
        "Slower, but it can read your repo."
    ),
    AIProviderType.CLI_INTERACTIVE: (
        "Opens your CLI so you work in it, then returns to Titan. "
        "For fixing things, not for producing text."
    ),
    AIProviderType.OFF: "Skip this task entirely.",
}


def provider_label(provider: AIProviderType) -> str:
    """A readable name for a provider type."""
    return PROVIDER_TYPE_LABELS.get(provider, str(provider))


def provider_description(provider: AIProviderType) -> str:
    """A one-line explanation of what choosing this provider type means."""
    return PROVIDER_TYPE_DESCRIPTIONS.get(provider, "")


__all__ = [
    "AITask",
    "AIRouteOrigin",
    "AIProviderType",
    "PROVIDER_TYPE_LABELS",
    "PROVIDER_TYPE_DESCRIPTIONS",
    "provider_label",
    "provider_description",
]
