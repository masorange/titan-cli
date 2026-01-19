# plugins/titan-plugin-jira/titan_plugin_jira/agents/validators.py
"""
Input validation for JiraAgent.

Provides comprehensive validation for issue data before processing.
Addresses PR #74 comment: "Falta Validación de Issue Data"
"""

from typing import Optional, List, Tuple
from ..models import JiraTicket


class IssueValidationError(ValueError):
    """Raised when issue data validation fails."""
    pass


class IssueValidator:
    """
    Validates JIRA issue data before AI processing.

    Ensures that issues have sufficient data for meaningful analysis:
    - Non-empty description
    - Valid issue type
    - No malformed data
    - Reasonable length constraints
    """

    # Valid JIRA issue types
    VALID_ISSUE_TYPES = {
        "Story", "Task", "Bug", "Epic", "Sub-task",
        "Improvement", "New Feature", "Technical Debt",
        "Spike", "User Story"
    }

    # Length constraints
    MIN_DESCRIPTION_LENGTH = 10  # Characters
    MAX_DESCRIPTION_LENGTH = 100000  # 100k characters (safety limit)
    MAX_SUMMARY_LENGTH = 255  # Standard JIRA limit

    def __init__(
        self,
        strict: bool = False,
        min_description_length: int = MIN_DESCRIPTION_LENGTH
    ):
        """
        Initialize validator.

        Args:
            strict: If True, raise errors on validation failures.
                   If False, return validation results with warnings.
            min_description_length: Minimum required description length
        """
        self.strict = strict
        self.min_description_length = min_description_length

    def validate_issue(self, issue: JiraTicket) -> Tuple[bool, List[str]]:
        """
        Validate issue data for AI processing.

        Args:
            issue: The JIRA issue to validate

        Returns:
            Tuple of (is_valid, errors)
            - is_valid: True if issue passes all validations
            - errors: List of validation error messages

        Raises:
            IssueValidationError: If strict=True and validation fails
        """
        errors = []

        # 1. Validate issue key
        if not issue.key or not issue.key.strip():
            errors.append("Issue key is empty")
        elif not self._is_valid_key_format(issue.key):
            errors.append(f"Issue key '{issue.key}' has invalid format (expected: PROJECT-123)")

        # 2. Validate summary
        if not issue.summary or not issue.summary.strip():
            errors.append("Issue summary is empty")
        elif len(issue.summary) > self.MAX_SUMMARY_LENGTH:
            errors.append(
                f"Issue summary is too long ({len(issue.summary)} chars, "
                f"max {self.MAX_SUMMARY_LENGTH})"
            )

        # 3. Validate description (critical for AI analysis)
        desc_errors = self._validate_description(issue.description)
        errors.extend(desc_errors)

        # 4. Validate issue type
        if issue.issue_type:
            if issue.issue_type not in self.VALID_ISSUE_TYPES:
                errors.append(
                    f"Unknown issue type '{issue.issue_type}'. "
                    f"Expected one of: {', '.join(sorted(self.VALID_ISSUE_TYPES))}"
                )

        # 5. Check for suspicious/malformed data
        suspicious_errors = self._check_suspicious_data(issue)
        errors.extend(suspicious_errors)

        is_valid = len(errors) == 0

        if self.strict and not is_valid:
            raise IssueValidationError(
                f"Issue validation failed for {issue.key}:\n" +
                "\n".join(f"  - {error}" for error in errors)
            )

        return is_valid, errors

    def _validate_description(self, description: Optional[str]) -> List[str]:
        """Validate issue description."""
        errors = []

        if not description:
            errors.append("Issue description is empty or None")
            return errors

        description = description.strip()

        if len(description) == 0:
            errors.append("Issue description is empty (whitespace only)")
        elif len(description) < self.min_description_length:
            errors.append(
                f"Issue description is too short ({len(description)} chars, "
                f"minimum {self.min_description_length})"
            )
        elif len(description) > self.MAX_DESCRIPTION_LENGTH:
            errors.append(
                f"Issue description is too long ({len(description)} chars, "
                f"max {self.MAX_DESCRIPTION_LENGTH})"
            )

        return errors

    def _is_valid_key_format(self, key: str) -> bool:
        """
        Validate JIRA issue key format.

        Expected format: PROJECT-123 (letters, hyphen, numbers)
        """
        import re
        pattern = r'^[A-Z][A-Z0-9]+-\d+$'
        return bool(re.match(pattern, key))

    def _check_suspicious_data(self, issue: JiraTicket) -> List[str]:
        """
        Check for suspicious or malformed data.

        Common issues:
        - HTML/XML tags in plain text fields (indicates parsing error)
        - Null bytes or control characters
        - Excessive whitespace
        """
        errors = []

        # Check for HTML tags (suggests improper parsing)
        if issue.description and ('<html>' in issue.description.lower() or
                                   '<!doctype' in issue.description.lower()):
            errors.append(
                "Description contains HTML tags (possible parsing error)"
            )

        # Check for null bytes
        if issue.description and '\x00' in issue.description:
            errors.append("Description contains null bytes")

        # Check for excessive consecutive whitespace (> 10 newlines)
        if issue.description:
            max_consecutive_newlines = 10
            if '\n' * max_consecutive_newlines in issue.description:
                errors.append(
                    f"Description has excessive whitespace "
                    f"({max_consecutive_newlines}+ consecutive newlines)"
                )

        return errors

    def validate_for_requirements_extraction(
        self,
        issue: JiraTicket
    ) -> Tuple[bool, List[str]]:
        """
        Validate issue specifically for requirements extraction.

        More strict than general validation - requires meaningful description.

        Returns:
            Tuple of (is_valid, errors)
        """
        is_valid, errors = self.validate_issue(issue)

        # Additional requirement: description must have substance
        if issue.description:
            # Check for placeholder text
            placeholder_phrases = [
                "to be defined", "tbd", "todo", "placeholder",
                "add description here", "fill this in"
            ]
            desc_lower = issue.description.lower()

            for phrase in placeholder_phrases:
                if phrase in desc_lower and len(issue.description.strip()) < 100:
                    errors.append(
                        f"Description appears to be a placeholder (contains '{phrase}')"
                    )
                    is_valid = False
                    break

        return is_valid, errors

    def sanitize_description(self, description: str, max_length: int = 5000) -> str:
        """
        Sanitize and truncate description for AI processing.

        Args:
            description: Raw description text
            max_length: Maximum length to truncate to

        Returns:
            Sanitized description
        """
        if not description:
            return ""

        # Remove null bytes
        sanitized = description.replace('\x00', '')

        # Normalize excessive whitespace
        import re
        # Replace 5+ consecutive newlines with 3
        sanitized = re.sub(r'\n{5,}', '\n\n\n', sanitized)

        # Replace 10+ consecutive spaces with single space
        sanitized = re.sub(r' {10,}', ' ', sanitized)

        # Truncate if needed
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
            sanitized += "\n\n... (description truncated for processing)"

        return sanitized.strip()
