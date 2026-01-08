from pathlib import Path
from typing import Dict, Optional
from titan_cli.ai.agents.base import BaseAIAgent, AgentRequest, AIGenerator


class IssueGeneratorAgent(BaseAIAgent):
    def __init__(self, ai_client: AIGenerator):
        super().__init__(ai_client)
        self.categories = {
            "feature": {
                "template": "feature.md",
                "labels": ["feature", "enhancement"],
                "prefix": "feat"
            },
            "improvement": {
                "template": "improvement.md",
                "labels": ["enhancement", "improvement"],
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
"""

    def _categorize_issue(self, user_description: str) -> str:
        """
        Use AI to categorize the issue based on user description.
        Returns: category name (feature, bug, improvement, refactor, chore, documentation)
        """
        prompt = f"""
Analyze the following issue description and categorize it into ONE of these categories:
- feature: New functionality or capability
- improvement: Enhancement to existing functionality
- bug: Something is broken or not working as expected
- refactor: Code restructuring without changing behavior
- chore: Maintenance tasks (dependencies, configs, CI/CD)
- documentation: Documentation updates or additions

Issue description:
---
{user_description}
---

Respond with ONLY the category name (one word).
"""

        request = AgentRequest(context=prompt)
        response = self.generate(request)
        category = response.content.strip().lower()

        # Validate category
        if category not in self.categories:
            # Default to feature if unknown
            category = "feature"

        return category

    def _load_template(self, template_name: str) -> Optional[str]:
        """
        Load a template file from .github/ISSUE_TEMPLATE/
        Returns None if template doesn't exist or can't be read.
        """
        try:
            template_path = Path(".github/ISSUE_TEMPLATE") / template_name
            if template_path.exists() and template_path.is_file():
                return template_path.read_text(encoding="utf-8")
        except Exception:
            pass
        return None

    def generate_issue(self, user_description: str) -> Dict[str, any]:
        """
        Generate a complete issue with auto-categorization.

        Returns:
            dict with keys: title, body, category, labels, template_used
        """
        # Step 1: Categorize the issue
        category = self._categorize_issue(user_description)
        category_info = self.categories[category]

        # Step 2: Try to load the appropriate template
        template_content = self._load_template(category_info["template"])
        template_used = template_content is not None

        # Step 3: Generate issue using the template (if available)
        if template_content:
            prompt = f"""
Here is a GitHub issue template for a {category}:
---
{template_content}
---

Here is the user's description:
---
{user_description}
---

Generate a complete issue following the template structure. Replace all placeholders with actual content based on the user's description.
- Remove all HTML comments (<!-- -->)
- Keep all section headers (##)
- Fill in meaningful content for each section
- If a section doesn't apply or lacks information, write "N/A" or a brief note
- Preserve any code snippets exactly as provided in markdown code blocks

The final output should be in the format:
TITLE: {category_info["prefix"]}(scope): brief description
DESCRIPTION:
<complete markdown-formatted description following the template>
"""
        else:
            # No template found - generate based on category type
            sections_by_category = {
                "feature": ["Summary", "Description", "Objectives", "Proposed Solution", "Acceptance Criteria"],
                "improvement": ["Summary", "Current Behavior", "Expected Behavior", "Proposed Solution", "Acceptance Criteria"],
                "bug": ["Summary", "Current Behavior", "Expected Behavior", "Steps to Reproduce", "Code Snippets / Error Messages"],
                "refactor": ["Summary", "Current State", "Proposed Solution", "Objectives", "Acceptance Criteria"],
                "chore": ["Summary", "Description", "Tasks"],
                "documentation": ["Summary", "Description", "Objectives"]
            }

            sections = sections_by_category.get(category, ["Summary", "Description"])
            sections_text = "\n".join([f"## {section}\n[Content for {section}]" for section in sections])

            prompt = f"""
Generate a GitHub issue for a {category}.

User description:
---
{user_description}
---

The title should follow the conventional commit format: {category_info["prefix"]}(scope): brief description

The description should include these sections:
{sections_text}

Fill each section with appropriate content based on the user's description.
Preserve any code snippets exactly as provided in markdown code blocks.

The final output should be in the format:
TITLE: <conventional commit title>
DESCRIPTION:
<markdown-formatted description with the sections above>
"""

        request = AgentRequest(context=prompt)
        response = self.generate(request)

        # Parse response
        if "DESCRIPTION:" in response.content:
            parts = response.content.split("DESCRIPTION:", 1)
            title = parts[0].replace("TITLE:", "").strip()
            body = parts[1].strip()
        else:
            title = response.content.splitlines()[0] if response.content else "Issue"
            body = response.content

        return {
            "title": title,
            "body": body,
            "category": category,
            "labels": category_info["labels"],
            "template_used": template_used
        }
