# plugins/titan-plugin-jira/titan_plugin_jira/agents/prompts.py
"""
Centralized AI prompts for JiraAgent.

All prompts are defined here for easy reuse, maintenance, and future externalization.
Addresses PR #74 comment: "Prompt hardcoded" (Comment #9)
"""

from typing import Dict, Any


class JiraAgentPrompts:
    """
    Centralized prompt templates for all JiraAgent AI operations.

    Each prompt method returns a formatted string ready for AI consumption.
    This eliminates duplication and makes prompts easy to modify in one place.

    Future enhancement: Move to TOML + Jinja2 templates (see PROMPTS.md)
    """

    @staticmethod
    def requirements_extraction(
        issue_key: str,
        summary: str,
        issue_type: str,
        priority: str,
        description: str
    ) -> str:
        """
        Prompt for extracting technical requirements from JIRA issue.

        Returns JSON format with:
        - functional: List of functional requirements
        - non_functional: List of non-functional requirements
        - acceptance_criteria: List of acceptance criteria
        - technical_approach: Brief technical approach suggestion
        """
        return f"""Analyze this JIRA issue and extract technical requirements.

Issue: {issue_key} - {summary}
Type: {issue_type}
Priority: {priority}

Description:
{description}

Extract and categorize requirements. Respond in JSON format:

```json
{{
  "functional": ["requirement 1", "requirement 2"],
  "non_functional": ["requirement 1", "requirement 2"],
  "acceptance_criteria": ["criterion 1", "criterion 2"],
  "technical_approach": "brief technical approach suggestion"
}}
```

IMPORTANT: Return ONLY valid JSON. Do not include explanatory text outside the JSON block."""

    @staticmethod
    def risk_analysis(
        issue_key: str,
        summary: str,
        issue_type: str,
        priority: str,
        description: str
    ) -> str:
        """
        Prompt for analyzing risks and complexity of JIRA issue.

        Returns JSON format with:
        - risks: List of potential risks
        - edge_cases: List of edge cases to consider
        - complexity: Complexity level (low|medium|high|very high)
        - effort: Estimated effort (1-2 days|3-5 days|1-2 weeks|2+ weeks)
        """
        return f"""Analyze this JIRA issue for risks and complexity.

Issue: {issue_key} - {summary}
Type: {issue_type}
Priority: {priority}

Description:
{description}

Identify potential risks, edge cases, and estimate complexity. Respond in JSON format:

```json
{{
  "risks": ["risk 1", "risk 2"],
  "edge_cases": ["edge case 1", "edge case 2"],
  "complexity": "low|medium|high|very high",
  "effort": "1-2 days|3-5 days|1-2 weeks|2+ weeks"
}}
```

IMPORTANT: Return ONLY valid JSON. Do not include explanatory text outside the JSON block."""

    @staticmethod
    def dependency_detection(
        issue_key: str,
        summary: str,
        issue_type: str,
        description: str
    ) -> str:
        """
        Prompt for detecting technical dependencies.

        Returns text format with:
        DEPENDENCIES:
        - dependency 1
        - dependency 2
        """
        return f"""Analyze this JIRA issue and identify technical dependencies.

Issue: {issue_key} - {summary}
Type: {issue_type}

Description:
{description}

Identify external dependencies (APIs, libraries, services, other systems, etc.).
Format your response EXACTLY like this:

DEPENDENCIES:
- <dependency 1>
- <dependency 2>"""

    @staticmethod
    def subtask_suggestion(
        issue_key: str,
        summary: str,
        issue_type: str,
        priority: str,
        description: str,
        max_subtasks: int = 5
    ) -> str:
        """
        Prompt for suggesting subtasks for work breakdown.

        Returns text format with:
        SUBTASK_1:
        Summary: <summary>
        Description: <description>

        SUBTASK_2:
        ...
        """
        return f"""Analyze this JIRA issue and suggest subtasks for work breakdown.

Issue: {issue_key} - {summary}
Type: {issue_type}
Priority: {priority}

Description:
{description}

Suggest up to {max_subtasks} subtasks. Format your response EXACTLY like this:

SUBTASK_1:
Summary: <concise summary>
Description: <brief technical description>

SUBTASK_2:
Summary: <concise summary>
Description: <brief technical description>"""

    @staticmethod
    def comment_generation(
        issue_key: str,
        summary: str,
        issue_type: str,
        status: str,
        description: str,
        comment_context: str
    ) -> str:
        """
        Prompt for generating a helpful JIRA comment.

        Returns text format with:
        COMMENT:
        <comment text>
        """
        return f"""Generate a helpful comment for this JIRA issue.

Issue: {issue_key} - {summary}
Type: {issue_type}
Status: {status}

Description:
{description}

Context: {comment_context}

Generate a professional, helpful comment. Be specific and actionable.
Format your response EXACTLY like this:

COMMENT:
<comment text>"""

    @staticmethod
    def description_enhancement(
        issue_key: str,
        summary: str,
        issue_type: str,
        current_description: str,
        requirements: Dict[str, Any]
    ) -> str:
        """
        Prompt for enhancing JIRA issue description with structured format.

        Args:
            issue_key: Issue key
            summary: Issue summary
            issue_type: Issue type
            current_description: Current description
            requirements: Dict with functional, non_functional, acceptance_criteria

        Returns text with enhanced description using proper markdown formatting.
        """
        functional = requirements.get("functional", [])
        non_functional = requirements.get("non_functional", [])
        acceptance_criteria = requirements.get("acceptance_criteria", [])

        functional_text = "\n".join(f"- {req}" for req in functional) if functional else "- N/A"
        non_functional_text = "\n".join(f"- {req}" for req in non_functional) if non_functional else "- N/A"
        criteria_text = "\n".join(f"- {crit}" for crit in acceptance_criteria) if acceptance_criteria else "- N/A"

        return f"""Enhance this JIRA issue description with better structure and clarity.

Issue: {issue_key} - {summary}
Type: {issue_type}

Current Description:
{current_description}

Extracted Requirements:

**Functional Requirements:**
{functional_text}

**Non-Functional Requirements:**
{non_functional_text}

**Acceptance Criteria:**
{criteria_text}

Generate an enhanced description that:
1. Preserves the original intent and key details
2. Adds proper structure using markdown formatting
3. Integrates the extracted requirements naturally
4. Is clear, professional, and actionable

Format your response as a complete JIRA description (markdown format)."""
