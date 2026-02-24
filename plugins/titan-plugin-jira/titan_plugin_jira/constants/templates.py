"""
Template constants for AI prompts and issue formatting.
"""

AI_PROMPT_TEMPLATE = """You are an assistant that helps create well-structured Jira issues.

**Issue Type:** {issue_type}
**User's brief description:**
{brief_description}

Your task is to generate:
1. A **concise title** (max 60 characters, clear and descriptive)
2. A **detailed description** with the following sections:
   - Expanded description (2-3 clear paragraphs)
   - Objective (1-2 sentences about what we want to achieve)
   - Acceptance Criteria (checkbox list, minimum 3, specific and testable)
   - Gherkin Tests (test scenarios in Given-When-Then format)
   - Technical Notes (optional, if applicable)
   - Dependencies (optional, if depends on other tasks/services)

Generate in this exact format:

TITLE:
[concise title here]

DESCRIPTION:
[expanded description in 2-3 paragraphs, NO numbering]

OBJECTIVE:
[objective in 1-2 sentences, NO numbering]

ACCEPTANCE_CRITERIA:
- [ ] Specific criterion 1
- [ ] Specific criterion 2
- [ ] Specific criterion 3

GHERKIN_TESTS:
Scenario: [scenario name]
  Given [initial context]
  When [user action]
  Then [expected result]

TECHNICAL_NOTES:
[technical notes or "N/A"]

DEPENDENCIES:
[dependencies or "N/A"]

IMPORTANT:
- Title must be brief (max 60 chars) and descriptive
- DO NOT number sections (no "1.", "2.", etc.)
- Be concise, specific, and professional
- Use technical but clear tone
- Acceptance criteria must be verifiable
- Gherkin tests should cover main cases
"""

FALLBACK_ISSUE_TEMPLATE = """## Description

{{ description }}

## Objective

{{ objective }}

## Acceptance Criteria

{{ acceptance_criteria }}
"""
