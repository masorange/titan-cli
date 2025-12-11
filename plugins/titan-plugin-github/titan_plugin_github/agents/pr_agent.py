# plugins/titan-plugin-github/titan_plugin_github/agents/pr_agent.py
"""
PRAgent - Intelligent orchestrator for git workflows.

This agent analyzes the complete context of a branch and automatically:
1. Determines if changes need to be committed
2. Generates appropriate commit messages
3. Creates PR title and description following templates
"""

import re
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from titan_cli.ai.agents.base import BaseAIAgent, AgentRequest
from .config_loader import load_agent_config
from ..utils import calculate_pr_size

# Set up logger
logger = logging.getLogger(__name__)


@dataclass
class PRAnalysis:
    """Complete analysis result from PRAgent."""

    # Commit analysis
    needs_commit: bool
    commit_message: Optional[str] = None
    staged_files: list[str] = None

    # PR analysis
    pr_title: Optional[str] = None
    pr_body: Optional[str] = None
    pr_size: Optional[str] = None

    # Metadata
    total_tokens_used: int = 0
    branch_commits: list[str] = None
    files_changed: int = 0
    lines_changed: int = 0



@dataclass
class BranchAnalysis:
    """The result of analyzing a branch's commits and diff."""
    commits: list[str]
    diff: str
    template: Optional[str]
    head_branch: str
    base_branch: str
    # PR Size estimation
    pr_size: str
    files_changed: int
    lines_changed: int
    max_chars: int


@dataclass
class PRContent:
    """The AI-generated content for a PR."""
    title: str
    body: str
    tokens_used: int


@dataclass
class PRAnalysis:
    """Complete analysis result from PRAgent."""

    # Commit analysis
    needs_commit: bool
    commit_message: Optional[str] = None
    staged_files: list[str] = None

    # PR analysis
    pr_title: Optional[str] = None
    pr_body: Optional[str] = None
    pr_size: Optional[str] = None

    # Metadata
    total_tokens_used: int = 0
    branch_commits: list[str] = None
    files_changed: int = 0
    lines_changed: int = 0


class PRAgent(BaseAIAgent):
    """
    Platform-level agent for intelligent git workflow automation.

    This agent is the highest-level orchestrator that:
    - Analyzes the full context of a branch
    - Uses specialized agents (PRAgent) for specific tasks
    - Makes intelligent decisions about what actions to take
    - Generates all necessary content (commits, PRs)

    Example:
        ```python
        # In a workflow step
        pr_agent = PRAgent(ctx.ai, ctx.git, ctx.github)

        analysis = pr_agent.analyze_and_plan(
            head_branch="feat/new-feature",
            base_branch="main"
        )

        if analysis.needs_commit:
            # Use analysis.commit_message for commit

        if analysis.pr_title:
            # Use analysis.pr_title and analysis.pr_body for PR
        ```
    """

    def __init__(
        self,
        ai_client,
        git_client,
        github_client=None
    ):
        """
        Initialize PRAgent.

        Args:
            ai_client: The AIClient instance (provides AI capabilities)
            git_client: Git client for repository operations
            github_client: Optional GitHub client for PR operations
        """
        super().__init__(ai_client)
        self.git = git_client
        self.github = github_client

        # Load configuration from TOML (once per agent instance)
        self.config = load_agent_config("pr_agent")

    def get_system_prompt(self) -> str:
        """System prompt for platform-level orchestration (from config)."""
        # Use commit system prompt from config (Pydantic provides defaults)
        return self.config.commit_system_prompt

    def analyze_branch(
        self,
        head_branch: str,
        base_branch: Optional[str] = None
    ) -> Optional[BranchAnalysis]:
        """
        Analyzes a branch by getting its commits and diff, but does not call AI.
        """
        base_branch = base_branch or self.git.main_branch
        try:
            commits = self.git.get_branch_commits(base_branch, head_branch)
            branch_diff = self.git.get_branch_diff(base_branch, head_branch)

            if not branch_diff or not commits:
                return None

            template = self._read_pr_template()
            estimation = calculate_pr_size(branch_diff)

            return BranchAnalysis(
                commits=commits,
                diff=branch_diff,
                template=template,
                head_branch=head_branch,
                base_branch=base_branch,
                pr_size=estimation.pr_size,
                files_changed=estimation.files_changed,
                lines_changed=estimation.diff_lines,
                max_chars=estimation.max_chars
            )
        except Exception as e:
            logger.error(f"Failed to analyze branch for PR: {e}")
            return None

    def generate_pr_content(
        self,
        analysis: BranchAnalysis
    ) -> Optional[PRContent]:
        """
        Generates PR title and body using AI from pre-analyzed branch data.
        """
        if not analysis:
            return None
        try:
            # This logic is extracted from _generate_pr_description
            prompt = self._build_pr_prompt(
                commits=analysis.commits,
                diff=analysis.diff,
                head_branch=analysis.head_branch,
                base_branch=analysis.base_branch,
                template=analysis.template,
                pr_size=analysis.pr_size,
                max_chars=analysis.max_chars
            )
            estimated_tokens = int(analysis.max_chars * 0.75) + 200
            max_tokens = min(estimated_tokens, 4000)
            request = AgentRequest(
                context=prompt,
                max_tokens=max_tokens,
                system_prompt=self.config.pr_system_prompt
            )
            response = self.generate(request)
            title, body = self._parse_pr_response(response.content, analysis.max_chars)
            return PRContent(
                title=title,
                body=body,
                tokens_used=response.tokens_used
            )
        except Exception as e:
            logger.error(f"Failed to generate PR description: {e}")
            return None

    def _generate_commit_message(self, diff: str) -> "CommitMessageResult":
        """
        Generate a commit message from a diff (using config).

        Args:
            diff: The git diff to analyze

        Returns:
            CommitMessageResult with message and tokens

        Raises:
            ValueError: If diff is empty or AI response is invalid
            Exception: If AI generation fails
        """
        if not diff or not diff.strip():
            raise ValueError("Cannot generate commit message from empty diff")

        # Truncate diff if too large (from config)
        max_diff = self.config.max_diff_size
        diff_preview = diff[:max_diff]
        if len(diff) > max_diff:
            diff_preview += "\n\n... (diff truncated)"

        prompt = f"""Analyze this diff and generate a conventional commit message.

```diff
{diff_preview}
```

Format your response EXACTLY like this:
COMMIT_MESSAGE: <conventional commit message>"""

        request = AgentRequest(
            context=prompt,
            max_tokens=200,
            system_prompt=self.config.commit_system_prompt  # Use specific commit prompt
        )

        try:
            response = self.generate(request)
        except Exception as e:
            logger.error(f"AI generation failed for commit message: {e}")
            raise

        # Parse response
        message = response.content.replace("COMMIT_MESSAGE:", "").strip()
        message = message.strip('"').strip("'")

        # Validate message
        if not message or len(message.strip()) < 3:
            raise ValueError("AI generated invalid or empty commit message")

        # Truncate if too long
        if len(message) > 72:
            message = message[:69] + "..."

        return CommitMessageResult(
            message=message,
            tokens_used=response.tokens_used
        )

    def _build_pr_prompt(
        self,
        commits: list[str],
        diff: str,
        head_branch: str,
        base_branch: str,
        template: Optional[str],
        pr_size: str,
        max_chars: int
    ) -> str:
        """Build the prompt for PR generation."""
        # Prepare commits text
        commits_text = "\n".join([f"  - {c}" for c in commits[:self.config.max_commits_to_analyze]])
        if len(commits) > self.config.max_commits_to_analyze:
            commits_text += f"\n  ... and {len(commits) - self.config.max_commits_to_analyze} more commits"

        # Limit diff size
        max_diff = self.config.max_diff_size
        diff_preview = diff[:max_diff] if diff else "No diff available"
        if len(diff) > max_diff:
            diff_preview += "\n\n... (diff truncated for brevity)"

        # Build prompt based on template availability
        if template:
            return f"""Analyze this branch and generate a professional pull request following the EXACT template structure.

## Branch Information
- Head branch: {head_branch}
- Base branch: {base_branch}
- Total commits: {len(commits)}

## Commits in Branch
{commits_text}

## Branch Diff Preview
```diff
{diff_preview}
```

## PR Template (MUST FOLLOW THIS STRUCTURE)
```markdown
{template}
```

## CRITICAL Instructions
1. **Title**: Follow conventional commits (type(scope): description), max 72 chars
   - Examples: "feat(auth): add OAuth2 integration", "fix(api): resolve race condition in cache"

2. **Description**: MUST follow the template structure above but keep it under {max_chars} characters total
   - Fill in the template sections (Summary, Type of Change, Changes Made, etc.)
   - Mark checkboxes appropriately with [x]
   - Adjust detail level based on PR size ({pr_size}):
     * Small PRs: Brief, 1-2 lines per section
     * Medium PRs: Moderate detail, 2-3 lines per section
     * Large PRs: Comprehensive, 3-5 lines per section with examples
     * Very Large PRs: Detailed architecture explanations, migration guides
   - Total description length MUST be ≤{max_chars} chars

Format your response EXACTLY like this:
TITLE: <conventional commit title>

DESCRIPTION:
<template-based description - MAX {max_chars} chars total>"""
        else:
            return f"""Analyze this branch and generate a professional pull request.

## Branch Information
- Head branch: {head_branch}
- Base branch: {base_branch}
- Total commits: {len(commits)}

## Commits in Branch
{commits_text}

## Branch Diff Preview
```diff
{diff_preview}
```

## Instructions (No template available - use standard format)
Generate a Pull Request appropriate for a {pr_size} PR:
1. **Title**: Follow conventional commits (type(scope): description), max 72 chars
   - Examples: "feat(auth): add OAuth2 integration", "fix(api): resolve race condition in cache"
2. **Description**: CRITICAL - Maximum {max_chars} characters. Detail level based on PR size:
   - Small ({pr_size}): Brief summary (1-2 sentences) + key changes (2-3 bullets)
   - Medium: What changed (2-3 sentences) + why (1-2 sentences) + key changes (4-5 bullets)
   - Large: Comprehensive overview + architecture changes + migration notes + testing strategy
   - Very Large: Full context + breaking changes + upgrade guide + examples

Format your response EXACTLY like this:
TITLE: <conventional commit title>

DESCRIPTION:
<description matching PR size - MAX {max_chars} chars>"""

    def _parse_pr_response(self, content: str, max_chars: int) -> tuple[str, str]:
        """
        Parse AI response to extract title and description.

        Returns:
            Tuple of (title, description)
        """
        if "TITLE:" not in content or "DESCRIPTION:" not in content:
            raise ValueError(
                f"AI response format incorrect. Expected 'TITLE:' and 'DESCRIPTION:' sections.\n"
                f"Got: {content[:200]}..."
            )

        # Extract title and description
        parts = content.split("DESCRIPTION:", 1)
        title = parts[0].replace("TITLE:", "").strip()
        description = parts[1].strip() if len(parts) > 1 else ""

        # Clean up title
        title = title.strip('"').strip("'")

        # Truncate title if too long
        if len(title) > 72:
            title = title[:69] + "..."

        # Truncate description if needed
        if len(description) > max_chars:
            description = description[:max_chars - 3] + "..."

        # Validate description
        if not description or len(description.strip()) < 10:
            raise ValueError("AI generated an empty or incomplete PR description")

        return title, description

    def _read_pr_template(self, template_path: str = ".github/pull_request_template.md") -> Optional[str]:
        """
        Read PR template if it exists.

        Args:
            template_path: Path to the template file

        Returns:
            Template content or None
        """
        path = Path(template_path)
        if not path.exists():
            return None

        try:
            with open(path, "r") as f:
                return f.read()
        except Exception:
            return None


@dataclass
class CommitMessageResult:
    """Result from commit message generation."""
    message: str
    tokens_used: int
