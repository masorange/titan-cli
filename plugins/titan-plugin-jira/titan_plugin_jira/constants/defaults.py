"""
Default values and constants for Jira plugin.
"""

from titan_plugin_jira.models.view import UIPriority

# Default title when AI generation fails
DEFAULT_TITLE = "New Task"

# Standard Jira priorities (fallback when API fails)
DEFAULT_PRIORITIES = [
    UIPriority(id="1", name="Highest", icon="🔴", label="🔴 Highest"),
    UIPriority(id="2", name="High", icon="🟠", label="🟠 High"),
    UIPriority(id="3", name="Medium", icon="🟡", label="🟡 Medium"),
    UIPriority(id="4", name="Low", icon="🟢", label="🟢 Low"),
    UIPriority(id="5", name="Lowest", icon="⚪", label="⚪ Lowest"),
]
