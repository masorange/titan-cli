"""
Message constants for Jira plugin.

All user-facing messages in English.
"""


class WorkflowMessages:
    """Workflow metadata messages."""

    CREATE_ISSUE_NAME = "Create Jira Issue"
    CREATE_ISSUE_DESC = "Create a Jira issue with AI assistance"


class StepTitles:
    """Step titles displayed in UI."""

    DESCRIPTION = "Description"
    ISSUE_TYPE = "Issue Type"
    PRIORITY = "Priority"
    AI_GENERATE = "Generate Title and Description"
    REVIEW = "Review Description"
    ASSIGNMENT = "Assignment"
    CREATE_ISSUE = "Create Issue"


class UserPrompts:
    """User-facing prompts and questions."""

    # Description step
    WHAT_TO_DO = "What do you want to do?"
    DESCRIBE_TASK = (
        "Briefly describe what you want to do. "
        "AI will help you complete the details later."
    )

    # Selection prompts
    SELECT_NUMBER = "Enter number ({min}-{max}):"
    WANT_TO_EDIT = "Do you want to edit the description?"
    WANT_TO_ASSIGN = "Assign this issue to yourself?"
    EDIT_DESCRIPTION_PROMPT = "Edit the description below:"
    FINAL_DESCRIPTION_LABEL = "Final description:"

    # Table headers
    ISSUE_TYPES_TABLE_TITLE = "Issue Types"
    PRIORITIES_TABLE_TITLE = "Priorities"
    HEADER_NUMBER = "#"
    HEADER_TYPE = "Type"
    HEADER_DESCRIPTION = "Description"
    HEADER_PRIORITY = "Priority"


class ErrorMessages:
    """Error messages for validation and failures."""

    # Configuration errors
    NO_PROJECT_CONFIGURED = (
        "No project configured. "
        "Please set 'default_project' in Jira plugin configuration."
    )
    JIRA_CLIENT_UNAVAILABLE = (
        "Jira client not available. "
        "Please verify plugin configuration."
    )

    # Validation errors
    DESCRIPTION_EMPTY = "Description cannot be empty."
    MISSING_REQUIRED_DATA = "Missing required data to create issue."
    MISSING_ENHANCED_DESC = "No enhanced description available."
    INVALID_SELECTION = "Invalid selection: '{selection}'\n\nYou must enter a number between {min} and {max}"

    # Data errors
    NO_ISSUE_TYPES_FOUND = "No issue types found in project."
    ONLY_SUBTASKS_AVAILABLE = (
        "Only subtasks are available. "
        "Cannot create subtasks directly."
    )
    SELECTED_TYPE_NOT_FOUND = "Selected issue type not found."
    NO_PRIORITIES_FOUND = "No priorities found in Jira"

    # AI errors
    AI_NOT_AVAILABLE = (
        "No AI provider configured. "
        "The brief description will be used as is."
    )
    AI_GENERATION_FAILED = (
        "Failed to generate description\n\n{error}\n\n"
        "The brief description will be used as is."
    )
    TEMPLATE_RENDER_FAILED = (
        "Failed to render template\n\n{error}\n\n"
        "AI response will be used without formatting."
    )

    # API errors
    FAILED_TO_GET_ISSUE_TYPES = "Failed to get issue types: {error}"
    FAILED_TO_GET_PRIORITIES = "Failed to get priorities: {error}"
    FAILED_TO_CREATE_ISSUE = "Failed to create issue: {error}"
    FAILED_TO_GET_CURRENT_USER = (
        "Failed to get current user\n\n{error}\n\n"
        "Issue will remain unassigned."
    )
    FAILED_TO_TRANSITION = "Could not change status: {error}"
    UNEXPECTED_ERROR_PRIORITIES = (
        "Unexpected error getting priorities\n\n{error}\n\n"
        "Using standard priorities."
    )


class SuccessMessages:
    """Success messages for completed operations."""

    DESCRIPTION_CAPTURED = "Description captured ({length} characters)"
    TYPE_SELECTED = "Type selected: {type}"
    PRIORITY_SELECTED = "Priority: {priority}"
    TITLE_GENERATED = "Title generated: {title}"
    DESCRIPTION_GENERATED = "Description generated with AI"
    DESCRIPTION_EDITED = "Description edited"
    DESCRIPTION_READY = "Description ready ({length} characters)"
    WILL_ASSIGN_TO = "Will be assigned to: {user}"
    ISSUE_CREATED = "Issue created: {key}"
    STATUS_CHANGED = "Status changed to: {status}"


class InfoMessages:
    """Informational messages."""

    # Step descriptions
    GETTING_ISSUE_TYPES = "Getting issue types for project {project}..."
    GETTING_PRIORITIES = "Getting project priorities..."
    CREATING_ISSUE = "Creating issue..."
    GENERATING_AI_DESC = (
        "AI will analyze your brief description and generate a detailed "
        "description with objectives and acceptance criteria..."
    )

    # Preview
    PREVIEW_LABEL = "**Preview:**"
    GENERATED_DESC_LABEL = "**Generated description:**"

    # Project info
    PROJECT_LABEL = "Project: {project}"
    TYPE_LABEL = "Type: {type}"
    PRIORITY_LABEL = "Priority: {priority}"
    CURRENT_USER_LABEL = "Current user: {user}"

    # Available items
    AVAILABLE_ISSUE_TYPES = "Available issue types:"
    AVAILABLE_PRIORITIES = "Available priorities:"

    # Fallback messages
    USING_STANDARD_PRIORITIES = "Using standard priorities."
    WILL_REMAIN_UNASSIGNED = "Issue will remain unassigned."
    EMPTY_DESC_USING_AI = "Empty description, will use AI-generated version."

    # Transition
    TRANSITIONING_TO = "Transitioning to '{status}'..."
    NO_READY_TO_DEV_TRANSITION = "No 'Ready to Dev' transition available"

    # Headings
    CREATING_ISSUE_HEADING = "Creating Issue in Jira"
