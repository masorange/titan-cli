"""
Commit Operations

Pure business logic for commit message handling.
These functions can be used by any step and are easily testable.
"""

from typing import Optional, Tuple


def build_ai_commit_prompt(diff_text: str, files_list: list, max_diff_chars: int = 8000) -> str:
    """
    Build the AI prompt for generating a commit message.

    Args:
        diff_text: Full git diff output
        files_list: List of changed file paths
        max_diff_chars: Maximum characters to include from diff (default: 8000)

    Returns:
        Complete prompt string for AI

    Examples:
        >>> diff = "diff --git a/file.py\\n+new line"
        >>> files = ["file.py"]
        >>> prompt = build_ai_commit_prompt(diff, files, max_diff_chars=100)
        >>> "Changed Files" in prompt
        True
        >>> "file.py" in prompt
        True
    """
    # Build files summary
    files_summary = "\n".join([f"  - {f}" for f in files_list]) if files_list else "(checking diff)"

    # Limit diff size to avoid token overflow
    diff_preview = diff_text[:max_diff_chars] if len(diff_text) > max_diff_chars else diff_text
    truncated = len(diff_text) > max_diff_chars

    if truncated:
        diff_preview += "\n\n[... diff truncated due to size ...]"

    prompt = f"""Analyze these code changes and generate a conventional commit message.

## Changed Files ({len(files_list)} total)
{files_summary}

## Diff
```diff
{diff_preview}
```

## CRITICAL Instructions
Generate ONE single-line conventional commit message following this EXACT format:
- type: Description
- Types: feat, fix, refactor, docs, test, chore, style, perf
- Description: clear summary in imperative mood, starting with CAPITAL letter (be descriptive, concise, and at least 5 words long)
- NO line breaks, NO body, NO additional explanation

Examples (notice they start with capital letter and are all one line):
- feat: Add OAuth2 integration with Google provider
- fix: Resolve race condition in cache invalidation
- refactor: Simplify menu component and remove unused props
- refactor: Add support for nested workflow execution

Return ONLY the single-line commit message, absolutely nothing else."""

    return prompt


def normalize_commit_message(raw_message: str) -> str:
    """
    Normalize a commit message by removing quotes, extra whitespace, and taking first line.

    Args:
        raw_message: Raw commit message from AI or user input

    Returns:
        Normalized single-line commit message

    Examples:
        >>> normalize_commit_message('"feat: Add feature"')
        'feat: Add feature'
        >>> normalize_commit_message("'fix: Bug fix'")
        'fix: Bug fix'
        >>> normalize_commit_message("  feat: Feature  \\n\\nBody text")
        'feat: Feature'
        >>> normalize_commit_message('  "feat: Feature"  ')
        'feat: Feature'
    """
    # Strip whitespace
    message = raw_message.strip()

    # Take only first line
    message = message.split('\n')[0].strip()

    # Remove surrounding quotes
    message = message.strip('"').strip("'").strip()

    return message


def capitalize_commit_subject(commit_message: str) -> str:
    """
    Capitalize the subject part of a conventional commit message.

    Format: "type: Subject" → "type: Subject" (with capital S)

    Args:
        commit_message: Commit message in conventional format

    Returns:
        Commit message with capitalized subject

    Examples:
        >>> capitalize_commit_subject("feat: add new feature")
        'feat: Add new feature'
        >>> capitalize_commit_subject("fix: resolve bug")
        'fix: Resolve bug'
        >>> capitalize_commit_subject("no colon here")
        'no colon here'
        >>> capitalize_commit_subject("feat: Already Capitalized")
        'feat: Already Capitalized'
    """
    if ':' not in commit_message:
        return commit_message

    parts = commit_message.split(':', 1)
    if len(parts) != 2:
        return commit_message

    prefix = parts[0]  # type
    subject = parts[1].strip()  # description

    # Capitalize first letter of subject if it's lowercase
    if subject and subject[0].islower():
        subject = subject[0].upper() + subject[1:]

    return f"{prefix}: {subject}"


def validate_message_length(message: str, max_length: int = 72) -> Tuple[bool, Optional[int]]:
    """
    Validate commit message length.

    Args:
        message: Commit message to validate
        max_length: Maximum recommended length (default: 72)

    Returns:
        Tuple of (is_valid, actual_length) where:
        - is_valid: True if length <= max_length
        - actual_length: The actual message length

    Examples:
        >>> validate_message_length("Short message")
        (True, 13)
        >>> validate_message_length("a" * 80, max_length=72)
        (False, 80)
        >>> validate_message_length("Exactly 72 chars" + "a" * 56, max_length=72)
        (True, 72)
    """
    length = len(message)
    is_valid = length <= max_length
    return is_valid, length


def process_ai_commit_message(raw_ai_response: str) -> str:
    """
    Complete processing pipeline for AI-generated commit messages.

    Combines normalization and capitalization.

    Args:
        raw_ai_response: Raw response from AI

    Returns:
        Processed commit message ready to use

    Examples:
        >>> process_ai_commit_message('"feat: add new feature"')
        'feat: Add new feature'
        >>> process_ai_commit_message("  'fix: resolve bug'  \\n\\nExtra text")
        'fix: Resolve bug'
    """
    normalized = normalize_commit_message(raw_ai_response)
    capitalized = capitalize_commit_subject(normalized)
    return capitalized


__all__ = [
    "build_ai_commit_prompt",
    "normalize_commit_message",
    "capitalize_commit_subject",
    "validate_message_length",
    "process_ai_commit_message",
]
