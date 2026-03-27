"""
Enumerations for Jira models.

Type-safe enums for Jira constants.
"""

from enum import StrEnum


class JiraPriority(StrEnum):
    """
    Standard Jira priority levels.

    These are the standard priority values used across Jira instances.
    Using StrEnum ensures type safety while maintaining string compatibility.
    """

    HIGHEST = "Highest"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    LOWEST = "Lowest"

    @property
    def icon(self) -> str:
        """Get the icon for this priority level."""
        icons = {
            JiraPriority.HIGHEST: "🔴",
            JiraPriority.HIGH: "🟠",
            JiraPriority.MEDIUM: "🟡",
            JiraPriority.LOW: "🟢",
            JiraPriority.LOWEST: "🔵",
        }
        return icons[self]

    @property
    def label(self) -> str:
        """Get the formatted label with icon."""
        return f"{self.icon} {self.value}"

    @classmethod
    def get_icon(cls, priority_name: str) -> str:
        """
        Get icon for any priority name (case-insensitive).

        Handles both standard priorities and common aliases:
        - Blocker → Highest icon
        - Critical → Highest icon
        - Major → High icon
        - Minor → Low icon
        - Trivial → Lowest icon

        Args:
            priority_name: Priority name from Jira

        Returns:
            Icon emoji string
        """
        priority_lower = priority_name.lower()

        # Aliases mapping
        aliases = {
            "blocker": "🚨",
            "critical": cls.HIGHEST.icon,
            "major": cls.HIGH.icon,
            "minor": cls.LOW.icon,
            "trivial": cls.LOWEST.icon,
        }

        # Check if it's an alias
        if priority_lower in aliases:
            return aliases[priority_lower]

        # Try to match standard priority
        try:
            priority = cls(priority_name)
            return priority.icon
        except ValueError:
            # Unknown priority
            return "⚫"


class JiraIssueType(StrEnum):
    """
    Common Jira issue types.

    Standard issue types found across Jira instances.
    """

    BUG = "Bug"
    STORY = "Story"
    TASK = "Task"
    EPIC = "Epic"
    SUB_TASK = "Sub-task"
    SUBTASK = "Subtask"
    IMPROVEMENT = "Improvement"
    NEW_FEATURE = "New Feature"
    TEST = "Test"

    @property
    def icon(self) -> str:
        """Get the icon for this issue type."""
        icons = {
            JiraIssueType.BUG: "🐛",
            JiraIssueType.STORY: "📖",
            JiraIssueType.TASK: "✅",
            JiraIssueType.EPIC: "🎯",
            JiraIssueType.SUB_TASK: "📋",
            JiraIssueType.SUBTASK: "📋",
            JiraIssueType.IMPROVEMENT: "⬆️",
            JiraIssueType.NEW_FEATURE: "✨",
            JiraIssueType.TEST: "🧪",
        }
        return icons[self]

    @classmethod
    def get_icon(cls, issue_type_name: str) -> str:
        """
        Get icon for any issue type name (case-insensitive).

        Args:
            issue_type_name: Issue type name from Jira

        Returns:
            Icon emoji string
        """
        try:
            issue_type = cls(issue_type_name)
            return issue_type.icon
        except ValueError:
            # Try case-insensitive match
            for member in cls:
                if member.value.lower() == issue_type_name.lower():
                    return member.icon
            # Unknown issue type
            return "📄"


class JiraStatusCategory(StrEnum):
    """
    Jira status category keys.

    Status categories group statuses into broader states.
    """

    TO_DO = "new"
    IN_PROGRESS = "indeterminate"
    DONE = "done"

    @property
    def icon(self) -> str:
        """Get the icon for this status category."""
        icons = {
            JiraStatusCategory.TO_DO: "🟡",
            JiraStatusCategory.IN_PROGRESS: "🔵",
            JiraStatusCategory.DONE: "🟢",
        }
        return icons[self]

    @classmethod
    def get_icon(cls, category_key: str) -> str:
        """
        Get icon for any category key or name (case-insensitive).

        Handles both category keys and common names:
        - "new" / "to do" → Yellow
        - "indeterminate" / "in progress" → Blue
        - "done" → Green

        Args:
            category_key: Status category key or name

        Returns:
            Icon emoji string
        """
        category_lower = category_key.lower()

        # Name aliases
        name_to_key = {
            "to do": cls.TO_DO,
            "in progress": cls.IN_PROGRESS,
        }

        # Try name alias first
        if category_lower in name_to_key:
            return name_to_key[category_lower].icon

        # Try exact key match
        try:
            category = cls(category_lower)
            return category.icon
        except ValueError:
            # Unknown category
            return "⚫"
