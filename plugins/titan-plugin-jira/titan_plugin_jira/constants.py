"""
Constants for Jira Plugin

All user-facing text, error messages, prompts, and other constants.
Centralized to avoid hardcoding and enable easy i18n in the future.
"""

# ==================== Step Titles ====================


class StepTitles:
    """Titles for workflow steps"""

    DESCRIPTION = "Description"
    ISSUE_TYPE = "Issue Type"
    PRIORITY = "Priority"
    AI_GENERATE = "Generate with AI"
    REVIEW = "Review Description"
    ASSIGNMENT = "Assignment"
    CREATE_ISSUE = "Create Issue"


# ==================== User Prompts ====================


class UserPrompts:
    """User-facing prompts and questions"""

    # General
    DESCRIBE_TASK = (
        "Briefly describe what you want to do. "
        "AI will help complete the details later."
    )
    WHAT_TO_DO = "What do you want to do?"
    WANT_TO_EDIT = "Do you want to edit the description?"
    WANT_TO_ASSIGN = "Assign this issue to yourself?"
    EDIT_DESCRIPTION_PROMPT = "Edit the description below:"
    FINAL_DESCRIPTION_LABEL = "Final description:"

    # Selection prompts
    SELECT_NUMBER = "Enter number ({min}-{max}):"

    # Table headers
    HEADER_NUMBER = "#"
    HEADER_TYPE = "Type"
    HEADER_PRIORITY = "Priority"
    HEADER_DESCRIPTION = "Description"

    # Table titles
    ISSUE_TYPES_TABLE_TITLE = "Issue Types"
    PRIORITIES_TABLE_TITLE = "Priorities"


# ==================== Error Messages ====================


class ErrorMessages:
    """Error messages"""

    # Validation errors
    DESCRIPTION_EMPTY = "❌ Error\n\nDescription cannot be empty."
    INVALID_SELECTION = (
        "❌ Invalid selection: '{selection}'\n\n"
        "Please enter a number between {min} and {max}"
    )

    # Configuration errors
    NO_PROJECT_CONFIGURED = (
        "❌ Configuration Error\n\n"
        "No project configured. Set 'default_project' "
        "in the Jira plugin configuration."
    )

    # Data errors
    MISSING_REQUIRED_DATA = (
        "❌ Error\n\nMissing required data (description, type, priority)."
    )
    MISSING_ENHANCED_DESC = (
        "❌ Error\n\nNo enhanced description available."
    )
    NO_ISSUE_TYPES_FOUND = (
        "❌ Error\n\nNo issue types found in the project."
    )
    ONLY_SUBTASKS_AVAILABLE = (
        "❌ Error\n\nOnly subtasks available. "
        "Cannot create subtasks directly."
    )
    SELECTED_TYPE_NOT_FOUND = (
        "❌ Error\n\nSelected issue type not found."
    )
    NO_PRIORITIES_FOUND = (
        "⚠️ No priorities found in Jira\n\n"
        "Using standard priorities."
    )

    # API errors
    FAILED_TO_GET_ISSUE_TYPES = (
        "❌ Failed to fetch issue types\n\n{error}"
    )
    FAILED_TO_GET_PRIORITIES = (
        "⚠️ Failed to fetch priorities\n\n{error}\n\n"
        "Using standard priorities."
    )
    FAILED_TO_GET_CURRENT_USER = (
        "⚠️ Failed to get current user\n\n{error}\n\n"
        "Issue will remain unassigned."
    )
    FAILED_TO_CREATE_ISSUE = (
        "❌ Failed to create issue\n\n{error}"
    )
    FAILED_TO_TRANSITION = (
        "Could not change status: {error}"
    )

    # AI errors
    AI_NOT_AVAILABLE = (
        "⚠️ AI not available\n\n"
        "No AI provider configured. "
        "Will use brief description as-is."
    )
    AI_GENERATION_FAILED = (
        "❌ Failed to generate description\n\n{error}\n\n"
        "Will use brief description as-is."
    )
    TEMPLATE_RENDER_FAILED = (
        "❌ Failed to render template\n\n{error}\n\n"
        "Will use AI response without formatting."
    )


# ==================== Success Messages ====================


class SuccessMessages:
    """Success messages"""

    DESCRIPTION_CAPTURED = "✓ Description captured ({length} characters)"
    TYPE_SELECTED = "✓ Selected type: {type}"
    PRIORITY_SELECTED = "✓ Priority: {priority}"
    TITLE_GENERATED = "✓ Title generated: {title}"
    DESCRIPTION_GENERATED = "✓ Description generated with AI"
    DESCRIPTION_EDITED = "✓ Description edited"
    DESCRIPTION_READY = "✓ Description ready ({length} characters)"
    WILL_ASSIGN_TO = "✓ Will be assigned to: {user}"
    ISSUE_CREATED = "✓ Issue created: {key}"
    STATUS_CHANGED = "✓ Status changed to: {status}"


# ==================== Info Messages ====================


class InfoMessages:
    """Informational messages"""

    GENERATING_AI_DESC = (
        "AI will analyze your brief description and generate "
        "a detailed description with objectives and acceptance criteria..."
    )
    PREVIEW_LABEL = "**Preview:**"
    GENERATED_DESC_LABEL = "**Generated description:**"
    EMPTY_DESC_USING_AI = (
        "⚠️ Empty description, will use AI-generated version."
    )
    CURRENT_USER_LABEL = "Current user: {user}"
    WILL_REMAIN_UNASSIGNED = "Issue will remain unassigned"

    # Status messages
    GETTING_ISSUE_TYPES = "Fetching issue types from project {project}..."
    GETTING_PRIORITIES = "Fetching priorities from project..."
    AVAILABLE_ISSUE_TYPES = "Available issue types:"
    AVAILABLE_PRIORITIES = "Available priorities:"

    # Creation messages
    CREATING_ISSUE_HEADING = "Creating Issue in Jira"
    PROJECT_LABEL = "Project: {project}"
    TYPE_LABEL = "Type: {type}"
    PRIORITY_LABEL = "Priority: {priority}"
    CREATING_ISSUE = "Creating issue..."
    TRANSITIONING_TO = "Transitioning to '{status}'..."
    NO_READY_TO_DEV_TRANSITION = "No 'Ready to Dev' transition available"


# ==================== AI Prompts ====================

AI_PROMPT_TEMPLATE = """You are an assistant that helps create well-structured Jira issues.

**Issue type:** {issue_type}
**Brief description from user:**
{brief_description}

Your task is to generate:
1. A **concise title** (maximum 60 characters, clear and descriptive)
2. A **detailed description** with the following sections:
   - Expanded description (2-3 clear paragraphs)
   - Objective (1-2 sentences about what is to be achieved)
   - Acceptance Criteria (checkbox list, minimum 3, specific and testable)
   - Gherkin Tests (test scenarios in Given-When-Then format)
   - Technical Notes (optional, if applicable)
   - Dependencies (optional, if it depends on other tasks/services)

Generate in this exact format:

TITLE:
[concise title here]

DESCRIPTION:
[expanded description in 2-3 paragraphs, DO NOT number]

OBJECTIVE:
[objective in 1-2 sentences, DO NOT number]

ACCEPTANCE_CRITERIA:
- [ ] Specific criterion 1
- [ ] Specific criterion 2
- [ ] Specific criterion 3

GHERKIN_TESTS:
Scenario: [scenario name]
  Given [initial context]
  When [user action]
  Then [expected result]

TECHNICAL_NOTES:
[technical notes or "N/A"]

DEPENDENCIES:
[dependencies or "N/A"]

IMPORTANT:
- Title should be brief (max 60 chars) and descriptive
- DO NOT number sections (no "1.", "2.", etc.)
- Be concise, specific, and professional
- Use technical but clear language
- Acceptance criteria must be verifiable
- Gherkin tests should cover main use cases
"""


# ==================== Default Values ====================

DEFAULT_TITLE = "New Task"

FALLBACK_ISSUE_TEMPLATE = """{{ description }}

---

**Objective:**
{{ objective }}

---

**Acceptance Criteria:**
{{ acceptance_criteria }}
"""


__all__ = [
    "StepTitles",
    "UserPrompts",
    "ErrorMessages",
    "SuccessMessages",
    "InfoMessages",
    "AI_PROMPT_TEMPLATE",
    "DEFAULT_TITLE",
    "FALLBACK_ISSUE_TEMPLATE",
]
