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
