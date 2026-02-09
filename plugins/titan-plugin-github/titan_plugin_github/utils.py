# plugins/titan-plugin-github/titan_plugin_github/utils.py
"""Utility functions for GitHub plugin."""

import re
from dataclasses import dataclass


# Default limits for diff processing
DEFAULT_MAX_DIFF_SIZE = 8000  # Characters
DEFAULT_MAX_FILES_IN_DIFF = 50
DEFAULT_MAX_COMMITS_TO_ANALYZE = 15


# i18n/localization file patterns for detection
# Used to identify PRs that primarily contain translation/localization changes
I18N_FILE_PATTERNS = [
    # Mobile
    'strings.xml',  # Android
    'localizable.strings',  # iOS
    '.strings',     # iOS general
    '.stringsdict', # iOS pluralization
    '.arb',         # Flutter/Dart

    # JavaScript/TypeScript ecosystem
    '/locales/',    # General i18n
    '/i18n/',       # General i18n
    '/translations/', # General
    '/locale/',     # Common variants

    # Backend frameworks
    '.po',          # gettext (Python, PHP)
    '.pot',         # gettext template
    'messages.',    # Rails/i18n
    '/lang/',       # Laravel/PHP
    'locale.',      # Various frameworks
    '.properties',  # Java resource bundles
    '.resx',        # .NET resources

    # Config files (when in i18n context)
    'i18n.json',
    'i18n.yml',
    'i18n.yaml',
]


@dataclass
class PRSizeEstimation:
    """
    PR size estimation with character limits.

    Attributes:
        pr_size: Size category (small, medium, large, very large)
        max_chars: Maximum characters for PR description
        files_changed: Number of files changed
        diff_lines: Number of lines in diff
    """
    pr_size: str
    max_chars: int
    files_changed: int
    diff_lines: int


def is_i18n_change(diff: str) -> bool:
    """
    Detect if a diff primarily contains i18n/localization changes.

    Analyzes the diff content to identify patterns that indicate
    translation or localization file modifications.

    Args:
        diff: The git diff to analyze

    Returns:
        True if the diff appears to be primarily i18n/localization changes

    Examples:
        >>> diff = "diff --git a/locales/es.json b/locales/es.json"
        >>> is_i18n_change(diff)
        True
    """
    if not diff:
        return False
    return any(pattern in diff.lower() for pattern in I18N_FILE_PATTERNS)


def calculate_pr_size(diff: str) -> PRSizeEstimation:
    """
    Analyzes a git diff to estimate PR size and suggest character limits.

    This is the single source of truth for PR size calculation.
    Both PRAgent and workflow steps use this function.

    Args:
        diff: The full text of the git diff

    Returns:
        PRSizeEstimation with size category and character limits

    Examples:
        >>> diff = "diff --git a/file.py b/file.py\\n..."
        >>> estimation = calculate_pr_size(diff)
        >>> print(estimation.pr_size)
        'small'
    """
    diff_lines = len(diff.split('\n'))

    # Count files changed (count file headers in diff)
    file_pattern = r'^diff --git'
    files_changed = len(re.findall(file_pattern, diff, re.MULTILINE))

    # Dynamic character limit based on PR size
    # Increased limits to accommodate PR templates with images/GIFs
    if files_changed <= 3 and diff_lines < 100:
        # Small PR: bug fix, doc update, small feature
        max_chars = 1500
        pr_size = "small"
    elif files_changed <= 10 and diff_lines < 500:
        # Medium PR: feature, moderate refactor
        max_chars = 2500
        pr_size = "medium"
    elif files_changed <= 30 and diff_lines < 2000:
        # Large PR: architectural changes, new modules
        max_chars = 4000
        pr_size = "large"
    else:
        # Very large PR: major refactor, breaking changes
        max_chars = 6000
        pr_size = "very large"

    return PRSizeEstimation(
        pr_size=pr_size,
        max_chars=max_chars,
        files_changed=files_changed,
        diff_lines=diff_lines
    )


__all__ = [
    "calculate_pr_size",
    "PRSizeEstimation",
    "is_i18n_change",
    "I18N_FILE_PATTERNS",
]
