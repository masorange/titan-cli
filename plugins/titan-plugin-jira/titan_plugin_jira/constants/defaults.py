"""
Default values and constants for Jira plugin.
"""

from titan_plugin_jira.models.view import UIPriority
from titan_plugin_jira.models.enums import JiraPriority

# Default title when AI generation fails
DEFAULT_TITLE = "New Task"

# Standard Jira priorities (fallback when API fails)
DEFAULT_PRIORITIES = [
    UIPriority(id="1", name=JiraPriority.HIGHEST, icon="🔴", label="🔴 Highest"),
    UIPriority(id="2", name=JiraPriority.HIGH, icon="🟠", label="🟠 High"),
    UIPriority(id="3", name=JiraPriority.MEDIUM, icon="🟡", label="🟡 Medium"),
    UIPriority(id="4", name=JiraPriority.LOW, icon="🟢", label="🟢 Low"),
    UIPriority(id="5", name=JiraPriority.LOWEST, icon="⚪", label="⚪ Lowest"),
]
