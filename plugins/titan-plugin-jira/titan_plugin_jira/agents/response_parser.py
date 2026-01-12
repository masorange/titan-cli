# plugins/titan-plugin-jira/titan_plugin_jira/agents/response_parser.py
"""
Robust AI response parser for JiraAgent.

This module provides a generic, robust parsing strategy for AI responses:
1. Try JSON parsing first (most reliable)
2. Fall back to regex-based parsing if JSON fails
3. Provide sensible defaults if both fail
4. Validate all extracted data

Based on lessons learned from PR #91 (IssueGeneratorAgent).
"""

import json
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass


@dataclass
class ParseResult:
    """Result of parsing with metadata."""
    data: Dict[str, Any]
    method_used: str  # "json", "regex", or "fallback"
    success: bool
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class AIResponseParser:
    """
    Generic parser for AI responses with multiple fallback strategies.

    Parsing strategies (in order of preference):
    1. JSON - Most reliable, structured format
    2. Regex - Fallback for text-based responses
    3. Default - Sensible defaults if all else fails

    Example:
        parser = AIResponseParser()

        # Define schema
        schema = {
            "functional": (list, []),
            "non_functional": (list, []),
            "technical_approach": (str, None)
        }

        # Parse with JSON
        result = parser.parse_json(content, schema)

        # Or parse with regex patterns
        patterns = {
            "functional": r"FUNCTIONAL_REQUIREMENTS:\\s*\\n((?:- .+\\n?)+)",
            "non_functional": r"NON_FUNCTIONAL_REQUIREMENTS:\\s*\\n((?:- .+\\n?)+)"
        }
        result = parser.parse_regex(content, patterns, schema)
    """

    def __init__(self, strict: bool = False):
        """
        Initialize parser.

        Args:
            strict: If True, raise exceptions on parsing errors.
                   If False, log warnings and use defaults.
        """
        self.strict = strict

    def parse_json(
        self,
        content: str,
        schema: Dict[str, tuple],
        validate_fn: Optional[Callable] = None
    ) -> ParseResult:
        """
        Parse JSON response with schema validation.

        Args:
            content: Raw AI response content
            schema: Dict mapping field names to (type, default) tuples
                   Example: {"risks": (list, []), "complexity": (str, None)}
            validate_fn: Optional validation function(data) -> List[str] errors

        Returns:
            ParseResult with parsed data
        """
        try:
            # Try to find JSON block in content
            json_match = re.search(r'```json\s*\n(.+?)\n```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try parsing entire content as JSON
                json_str = content.strip()

            data = json.loads(json_str)

            # Validate and fill defaults
            result_data = {}
            errors = []

            for field, (expected_type, default) in schema.items():
                if field in data:
                    value = data[field]
                    # Type check
                    if not isinstance(value, expected_type):
                        errors.append(
                            f"Field '{field}' has wrong type: "
                            f"expected {expected_type.__name__}, got {type(value).__name__}"
                        )
                        result_data[field] = default
                    else:
                        result_data[field] = value
                else:
                    # Use default if field missing
                    result_data[field] = default
                    if default is None:
                        errors.append(f"Field '{field}' is missing")

            # Custom validation
            if validate_fn:
                validation_errors = validate_fn(result_data)
                errors.extend(validation_errors)

            # Collect errors but don't log (no logging strategy defined yet)

            return ParseResult(
                data=result_data,
                method_used="json",
                success=len(errors) == 0,
                errors=errors
            )

        except json.JSONDecodeError as e:
            # Return empty result, caller will try fallback
            return ParseResult(
                data={field: default for field, (_, default) in schema.items()},
                method_used="json",
                success=False,
                errors=[f"JSON decode error: {e}"]
            )

    def parse_regex(
        self,
        content: str,
        patterns: Dict[str, str],
        schema: Dict[str, tuple],
        list_separator: str = r"\n-\s*"
    ) -> ParseResult:
        """
        Parse text response using regex patterns.

        Args:
            content: Raw AI response content
            patterns: Dict mapping field names to regex patterns
            schema: Dict mapping field names to (type, default) tuples
            list_separator: Regex pattern for splitting list items

        Returns:
            ParseResult with parsed data
        """
        result_data = {}
        errors = []

        for field, (expected_type, default) in schema.items():
            if field not in patterns:
                # No pattern, use default
                result_data[field] = default
                continue

            pattern = patterns[field]
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)

            if not match:
                # Pattern didn't match, use default
                result_data[field] = default
                errors.append(f"Pattern for '{field}' not found in content")
                continue

            # Extract matched content
            matched_text = match.group(1).strip()

            # Convert to expected type
            if expected_type == list:
                # Split by list separator (e.g., "- item")
                items = re.split(list_separator, matched_text)
                items = [item.strip() for item in items if item.strip()]
                result_data[field] = items
            elif expected_type == str:
                result_data[field] = matched_text
            elif expected_type == int:
                try:
                    result_data[field] = int(matched_text)
                except ValueError:
                    result_data[field] = default
                    errors.append(f"Could not convert '{field}' to int: {matched_text}")
            else:
                # Unknown type, store as string
                result_data[field] = matched_text

        return ParseResult(
            data=result_data,
            method_used="regex",
            success=len(errors) == 0,
            errors=errors
        )

    def parse_with_fallback(
        self,
        content: str,
        schema: Dict[str, tuple],
        json_first: bool = True,
        regex_patterns: Optional[Dict[str, str]] = None,
        validate_fn: Optional[Callable] = None
    ) -> ParseResult:
        """
        Parse response with automatic fallback strategy.

        Args:
            content: Raw AI response
            schema: Field schema
            json_first: Try JSON before regex
            regex_patterns: Patterns for regex fallback
            validate_fn: Optional validation function

        Returns:
            ParseResult with parsed data using best available method
        """
        if json_first:
            # Try JSON first
            result = self.parse_json(content, schema, validate_fn)
            if result.success:
                return result

            # Fall back to regex
            if regex_patterns:
                result = self.parse_regex(content, regex_patterns, schema)
                if result.success or not result.errors:
                    return result
        else:
            # Try regex first (for legacy text-based responses)
            if regex_patterns:
                result = self.parse_regex(content, regex_patterns, schema)
                if result.success:
                    return result

            # Fall back to JSON
            result = self.parse_json(content, schema, validate_fn)
            if result.success:
                return result

        # Both failed, return defaults
        return ParseResult(
            data={field: default for field, (_, default) in schema.items()},
            method_used="fallback",
            success=False,
            errors=["All parsing strategies failed"]
        )


# ==================== SPECIFIC PARSERS FOR JIRA AGENT ====================

class JiraAgentParser:
    """
    Specialized parser for JiraAgent responses.

    Provides pre-configured parsers for all JiraAgent AI operations:
    - Requirements extraction
    - Risk analysis
    - Dependencies detection
    - Subtasks suggestion
    """

    def __init__(self, strict: bool = False):
        self.parser = AIResponseParser(strict=strict)

    def parse_requirements(self, content: str) -> Dict[str, Any]:
        """
        Parse requirements extraction response.

        Expected JSON format:
        {
            "functional": ["req1", "req2"],
            "non_functional": ["nfr1", "nfr2"],
            "acceptance_criteria": ["ac1", "ac2"],
            "technical_approach": "approach description"
        }

        Fallback regex patterns for text-based responses.
        """
        schema = {
            "functional": (list, []),
            "non_functional": (list, []),
            "acceptance_criteria": (list, []),
            "technical_approach": (str, None)
        }

        regex_patterns = {
            "functional": r'FUNCTIONAL_REQUIREMENTS:\s*\n((?:-\s*.+\n?)+)',
            "non_functional": r'NON_FUNCTIONAL_REQUIREMENTS:\s*\n((?:-\s*.+\n?)+)',
            "acceptance_criteria": r'ACCEPTANCE_CRITERIA:\s*\n((?:-\s*.+\n?)+)',
            "technical_approach": r'TECHNICAL_APPROACH:\s*\n(.+?)(?=\n[A-Z_]+:|$)'
        }

        result = self.parser.parse_with_fallback(
            content,
            schema,
            json_first=True,
            regex_patterns=regex_patterns
        )

        return result.data

    def parse_risks(self, content: str) -> Dict[str, Any]:
        """
        Parse risk analysis response.

        Expected JSON format:
        {
            "risks": ["risk1", "risk2"],
            "edge_cases": ["case1", "case2"],
            "complexity": "Medium",
            "effort": "3-5 days"
        }
        """
        schema = {
            "risks": (list, []),
            "edge_cases": (list, []),
            "complexity": (str, None),
            "effort": (str, None)
        }

        regex_patterns = {
            "risks": r'RISKS:\s*\n((?:-\s*.+\n?)+)',
            "edge_cases": r'EDGE_CASES:\s*\n((?:-\s*.+\n?)+)',
            "complexity": r'COMPLEXITY:\s*(.+)',
            "effort": r'EFFORT_ESTIMATE:\s*(.+)'
        }

        result = self.parser.parse_with_fallback(
            content,
            schema,
            json_first=True,
            regex_patterns=regex_patterns
        )

        return result.data

    def parse_dependencies(self, content: str) -> Dict[str, Any]:
        """
        Parse dependencies detection response.

        Expected JSON format:
        {
            "dependencies": ["dep1", "dep2"]
        }
        """
        schema = {
            "dependencies": (list, [])
        }

        regex_patterns = {
            "dependencies": r'DEPENDENCIES:\s*\n((?:-\s*.+\n?)+)'
        }

        result = self.parser.parse_with_fallback(
            content,
            schema,
            json_first=True,
            regex_patterns=regex_patterns
        )

        return result.data

    def parse_subtasks(self, content: str) -> Dict[str, Any]:
        """
        Parse subtasks suggestion response.

        Expected JSON format:
        {
            "subtasks": [
                {"summary": "Task 1", "description": "Desc 1"},
                {"summary": "Task 2", "description": "Desc 2"}
            ]
        }
        """
        schema = {
            "subtasks": (list, [])
        }

        # Try JSON first
        result = self.parser.parse_json(content, schema)

        if not result.success:
            # Fallback: manual regex parsing for text-based subtasks
            subtasks = self._parse_subtasks_regex(content)
            return {"subtasks": subtasks}

        # Validate subtask structure
        valid_subtasks = []
        for subtask in result.data.get("subtasks", []):
            if isinstance(subtask, dict) and "summary" in subtask:
                valid_subtasks.append({
                    "summary": subtask.get("summary", ""),
                    "description": subtask.get("description", "")
                })

        return {"subtasks": valid_subtasks}

    def _parse_subtasks_regex(self, content: str) -> List[Dict[str, str]]:
        """Fallback regex parser for subtasks in text format."""
        subtasks = []
        current_subtask = None

        for line in content.split("\n"):
            line = line.strip()

            if line.startswith("SUBTASK_"):
                if current_subtask:
                    subtasks.append(current_subtask)
                current_subtask = {"summary": "", "description": ""}
            elif current_subtask:
                if line.startswith("Summary:"):
                    current_subtask["summary"] = line.split(":", 1)[1].strip()
                elif line.startswith("Description:"):
                    current_subtask["description"] = line.split(":", 1)[1].strip()

        if current_subtask:
            subtasks.append(current_subtask)

        return subtasks
