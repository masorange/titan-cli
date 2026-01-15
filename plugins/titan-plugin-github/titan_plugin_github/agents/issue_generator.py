from pathlib import Path
from typing import Dict, Optional, Tuple
import re
import json
from dataclasses import dataclass
from titan_cli.ai.agents.base import BaseAIAgent, AgentRequest, AIGenerator


@dataclass
class IssueSizeEstimation:
    """
    Issue size estimation with token limits.

    Attributes:
        complexity: Size category (simple, moderate, complex, very_complex)
        max_tokens: Maximum tokens for issue description generation
        description_length: Length of user's description
    """
    complexity: str
    max_tokens: int
    description_length: int


class IssueGeneratorAgent(BaseAIAgent):
    def __init__(self, ai_client: AIGenerator, template_dir: Optional[Path] = None):
        super().__init__(ai_client)
        self.template_dir = template_dir or Path(".github/ISSUE_TEMPLATE")
        self.max_tokens = 8192  # Add token limit configuration
        self.categories = {
            "feature": {
                "template": "feature.md",
                "labels": ["feature"],
                "prefix": "feat"
            },
            "improvement": {
                "template": "improvement.md",
                "labels": ["improvement"],
                "prefix": "improve"
            },
            "bug": {
                "template": "bug.md",
                "labels": ["bug"],
                "prefix": "fix"
            },
            "refactor": {
                "template": "refactor.md",
                "labels": ["refactor", "technical-debt"],
                "prefix": "refactor"
            },
            "chore": {
                "template": "chore.md",
                "labels": ["chore", "maintenance"],
                "prefix": "chore"
            },
            "documentation": {
                "template": "documentation.md",
                "labels": ["documentation"],
                "prefix": "docs"
            }
        }

    def get_system_prompt(self) -> str:
        return """You are an expert at creating highly professional, descriptive, and useful GitHub issues.
Your task is to:
1. Analyze the user's description and categorize it
2. Generate an issue title and detailed description following the appropriate template (if available)
3. Ensure the title follows the Conventional Commits specification (e.g., "feat(scope): brief description")
4. Use English for all content
5. Prioritize clarity, conciseness, and actionable detail
6. Preserve any code snippets exactly as provided, formatted in markdown code blocks
7. Always return your response as valid JSON format for reliable parsing
"""

    def _load_template(self, template_name: str) -> Optional[str]:
        """
        Load a template file from the template directory.
        Returns None if template doesn't exist or can't be read.
        """
        try:
            template_path = self.template_dir / template_name
            if template_path.exists() and template_path.is_file():
                return template_path.read_text(encoding="utf-8")
        except (IOError, FileNotFoundError, PermissionError, OSError):
            pass
        return None

    def _load_all_templates(self) -> Dict[str, Optional[str]]:
        """
        Load all available templates.
        Returns a dict mapping category name to template content.
        """
        templates = {}
        for category, info in self.categories.items():
            template_content = self._load_template(info["template"])
            templates[category] = template_content
        return templates

    def _estimate_issue_complexity(self, description: str) -> IssueSizeEstimation:
        """
        Estimate issue complexity based on description length and content.

        Args:
            description: User's issue description

        Returns:
            IssueSizeEstimation with complexity and token limits
        """
        desc_length = len(description)
        # Count newlines as indicator of detail
        lines = description.count('\n') + 1
        # Count code blocks as indicator of technical complexity
        code_blocks = description.count('```')

        # Determine complexity and set appropriate token limits
        if desc_length < 200 and lines <= 3 and code_blocks == 0:
            # Simple issue: brief request, quick fix
            complexity = "simple"
            max_tokens = 3000  # Increased to ensure complete JSON
        elif desc_length < 500 and lines <= 10:
            # Moderate issue: standard feature or bug with some detail
            complexity = "moderate"
            max_tokens = 4000  # Increased to ensure complete JSON
        elif desc_length < 1000 and lines <= 25:
            # Complex issue: detailed requirements, multiple aspects
            complexity = "complex"
            max_tokens = 6000  # Increased to ensure complete JSON
        else:
            # Very complex: comprehensive spec, architectural changes
            complexity = "very_complex"
            max_tokens = 8000  # Increased to ensure complete JSON

        return IssueSizeEstimation(
            complexity=complexity,
            max_tokens=max_tokens,
            description_length=desc_length
        )

    def _parse_ai_response(self, content: str) -> Tuple[str, str, str]:
        """
        Parse AI response to extract category, title, and body.
        Tries JSON parsing first, falls back to regex for robustness.
        Handles incomplete JSON by attempting to fix it.

        Returns:
            Tuple of (category, title, body)
        """
        # Try JSON parsing first (more robust, avoids conflicts with user text)
        try:
            # Remove ONLY the outer markdown code block wrapper (```json ... ```)
            # but preserve code blocks inside the JSON body content
            cleaned_content = content.strip()

            # Remove opening ```json or ``` if present at the start
            if cleaned_content.startswith('```json'):
                cleaned_content = cleaned_content[7:].lstrip()
            elif cleaned_content.startswith('```'):
                cleaned_content = cleaned_content[3:].lstrip()

            # Remove closing ``` if present at the end
            if cleaned_content.endswith('```'):
                cleaned_content = cleaned_content[:-3].rstrip()

            # Try to find JSON in the content (handle incomplete JSON)
            json_match = re.search(r'\{[\s\S]*\}', cleaned_content)

            # If no complete JSON found, try to fix incomplete JSON
            if not json_match and cleaned_content.strip().startswith('{'):
                # JSON might be incomplete (missing closing quote and brace)
                json_str = cleaned_content.strip()
                # Try to close the JSON properly
                if not json_str.endswith('}'):
                    # Close any unclosed string first
                    if json_str.count('"') % 2 != 0:
                        json_str = json_str + '"'
                    # Then close the JSON object
                    json_str = json_str + '\n}'
            elif json_match:
                json_str = json_match.group(0)
            else:
                json_str = None

            if json_str:
                data = json.loads(json_str)

                category = data.get("category", "feature").lower()
                title = data.get("title", "New issue")
                body = data.get("body", "")

                # Validate category
                if category not in self.categories:
                    category = "feature"

                return category, title, body
        except (json.JSONDecodeError, AttributeError):
            # JSON parsing failed, fall back to regex
            pass

        # Fallback: regex parsing for backwards compatibility
        # Extract category
        category_match = re.search(r'CATEGORY:\s*(\w+)', content, re.IGNORECASE)
        category = category_match.group(1).strip().lower() if category_match else "feature"

        # Validate category
        if category not in self.categories:
            category = "feature"

        # Extract title
        title_match = re.search(r'TITLE:\s*(.+?)(?=\n|DESCRIPTION:|$)', content, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else "New issue"

        # Extract description/body
        desc_match = re.search(r'DESCRIPTION:\s*(.+)', content, re.IGNORECASE | re.DOTALL)
        body = desc_match.group(1).strip() if desc_match else content

        return category, title, body

    def generate_issue(self, user_description: str) -> Dict[str, any]:
        """
        Generate a complete issue with auto-categorization in a single AI call.

        Returns:
            dict with keys: title, body, category, labels, template_used, tokens_used, complexity
        """
        # Estimate issue complexity to determine appropriate token allocation
        estimation = self._estimate_issue_complexity(user_description)

        # Load all available templates
        all_templates = self._load_all_templates()

        # Build prompt that includes all templates and asks AI to categorize + generate
        templates_section = self._format_templates_for_prompt(all_templates)

        prompt = f"""
Analyze the following issue description and:
1. Categorize it into ONE category: feature, improvement, bug, refactor, chore, or documentation
2. Generate a complete GitHub issue following the appropriate template

User description:
---
{user_description}
---

{templates_section}

Instructions:
- Choose the most appropriate category based on the description
- Follow the template structure for that category (if available)
- Remove all HTML comments (<!-- -->)
- Keep only section headers (##) that have meaningful content
- IMPORTANT: Completely omit optional sections (marked with "Optional") if they don't apply or have no meaningful content
- Never include a section header followed by just a language identifier (e.g., "python", "yaml") without actual code
- Fill in meaningful content for each section you include
- Preserve any code snippets exactly as provided in markdown code blocks
- Use the correct conventional commit prefix for the title
- Adjust detail level based on issue complexity ({estimation.complexity}):
  * Simple: Brief, direct descriptions (1-2 sentences per section)
  * Moderate: Standard detail (2-3 sentences per section)
  * Complex: Comprehensive detail with examples
  * Very Complex: Full context, edge cases, and implementation notes

Output format (REQUIRED - JSON):
{{
  "category": "<category>",
  "title": "<prefix>(scope): brief description",
  "body": "<complete markdown-formatted description>"
}}
"""

        # Single AI call for categorization + generation with appropriate token limit
        request = AgentRequest(
            context=prompt,
            max_tokens=estimation.max_tokens
        )
        response = self.generate(request)

        # Temporary debug logging
        import time
        timestamp = time.time()
        with open("/tmp/issue_ai_response.log", "a") as f:
            f.write(f"\n\n[{timestamp}] ===== AI RESPONSE =====\n")
            f.write(f"Content length: {len(response.content)}\n")
            f.write(f"Full content:\n{response.content}\n")

        # Parse response using robust regex parsing
        category, title, body = self._parse_ai_response(response.content)

        # Log parsed body
        with open("/tmp/issue_ai_response.log", "a") as f:
            f.write(f"\n[{timestamp}] ===== PARSED BODY =====\n")
            f.write(f"Body length: {len(body)}\n")
            f.write(f"Body content:\n{body}\n")

        category_info = self.categories[category]
        template_used = all_templates.get(category) is not None

        return {
            "title": title,
            "body": body,
            "category": category,
            "labels": category_info["labels"],
            "template_used": template_used,
            "tokens_used": response.tokens_used,
            "complexity": estimation.complexity
        }

    def _format_templates_for_prompt(self, templates: Dict[str, Optional[str]]) -> str:
        """
        Format all templates into a string for the AI prompt.
        """
        if not any(templates.values()):
            return "No templates available. Generate structured content based on category best practices."

        formatted = "Available templates:\n\n"
        for category, template_content in templates.items():
            if template_content:
                category_info = self.categories[category]
                formatted += f"### {category.upper()} (prefix: {category_info['prefix']})\n"
                formatted += f"```\n{template_content}\n```\n\n"
            else:
                formatted += f"### {category.upper()} (no template available)\n\n"

        return formatted
