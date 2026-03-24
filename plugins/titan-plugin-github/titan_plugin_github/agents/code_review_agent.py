# plugins/titan-plugin-github/titan_plugin_github/agents/code_review_agent.py
"""
CodeReviewAgent - AI agent for reviewing pull requests.

Analyzes PR diffs and project skills to generate structured review comments.
"""

import json
import logging
from typing import List

from titan_cli.ai.agents.base import BaseAIAgent, AgentRequest
from ..models.view import UIReviewSuggestion

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an expert code reviewer. Your task is to review pull request diffs
and provide actionable, constructive feedback.

When reviewing code, focus on:
- Correctness: bugs, logic errors, edge cases
- Security: vulnerabilities, unsafe patterns
- Performance: inefficiencies, unnecessary complexity
- Maintainability: readability, naming, structure
- Project conventions: follow any project-specific skills/guidelines provided

Output your review as a JSON array of comment objects. Each comment must have:
- "file": the file path (string)
- "line": the line number in the diff (integer, or null if it's a general comment)
- "body": the review comment text (string, be concise and actionable)
- "severity": one of "critical", "improvement", or "suggestion"

Severity guide:
- "critical": bugs, security issues, broken logic that must be fixed
- "improvement": code quality issues that should be addressed
- "suggestion": minor style, naming, or optional improvements

If the code looks good, return an empty array [].

Respond with ONLY the JSON array, no other text.
"""


class CodeReviewAgent(BaseAIAgent):
    """
    AI agent for reviewing pull requests using project skills as context.

    Generates structured UIReviewSuggestion objects from PR diffs.
    """

    def get_system_prompt(self) -> str:
        """System prompt for code review expertise."""
        return _SYSTEM_PROMPT

    def review(self, context: str) -> List[UIReviewSuggestion]:
        """
        Generate review comments for a PR.

        Args:
            context: Formatted string with PR info, diff, and project skills

        Returns:
            List of UIReviewSuggestion objects
        """
        request = AgentRequest(
            context=context,
            max_tokens=4000,
            temperature=0.3,
            operation="code_review",
        )

        try:
            response = self.generate(request)
        except Exception as e:
            logger.error(f"AI code review failed: {e}")
            return []

        return self._parse_suggestions(response.content)

    def _parse_suggestions(self, content: str) -> List[UIReviewSuggestion]:
        """
        Parse AI JSON response into UIReviewSuggestion objects.

        Args:
            content: Raw AI response string

        Returns:
            List of UIReviewSuggestion objects (empty list on parse failure)
        """
        # Strip markdown code fences if present
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse AI review response as JSON: {content[:200]}")
            return []

        if not isinstance(data, list):
            logger.warning(f"AI review response is not a list: {type(data)}")
            return []

        suggestions = []
        valid_severities = {"critical", "improvement", "suggestion"}

        for item in data:
            if not isinstance(item, dict):
                continue

            file_path = item.get("file", "")
            if not file_path:
                continue

            severity = item.get("severity", "suggestion")
            if severity not in valid_severities:
                severity = "suggestion"

            line_raw = item.get("line")
            line = int(line_raw) if isinstance(line_raw, (int, float)) and line_raw else None

            body = item.get("body", "").strip()
            if not body:
                continue

            suggestions.append(UIReviewSuggestion(
                file_path=file_path,
                line=line,
                body=body,
                severity=severity,
            ))

        return suggestions
