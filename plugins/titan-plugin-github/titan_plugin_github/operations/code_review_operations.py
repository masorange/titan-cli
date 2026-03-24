# plugins/titan-plugin-github/titan_plugin_github/operations/code_review_operations.py
"""
Operations for AI-powered PR code review.

Pure business logic functions for loading project skills, building review
context, and constructing review payloads. All functions are UI-agnostic.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..models.view import UIPullRequest, UIReviewSuggestion

logger = logging.getLogger(__name__)


def load_all_project_skills() -> List[Dict]:
    """
    Load all project skills from .claude/skills/ without filtering.

    Returns:
        List of {"name": str, "description": str, "content": str} dicts
    """
    skills_dir = Path(".claude/skills")
    if not skills_dir.exists() or not skills_dir.is_dir():
        return []

    skills = []

    for skill_file in sorted(skills_dir.glob("*.md")):
        try:
            content = skill_file.read_text(encoding="utf-8")
        except OSError:
            continue

        # Extract description from frontmatter if present
        description = skill_file.stem
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if frontmatter_match:
            desc_match = re.search(r"description\s*:\s*(.+)", frontmatter_match.group(1))
            if desc_match:
                description = desc_match.group(1).strip()

        skills.append({
            "name": skill_file.stem,
            "description": description,
            "content": content,
        })

    return skills


def select_relevant_skills(
    all_skills: List[Dict],
    diff: str,
    ai_generator: Any,
) -> List[Dict]:
    """
    Use AI to select which skills are relevant for the given diff.

    Args:
        all_skills: All available skills (from load_all_project_skills)
        diff: Unified diff of the PR
        ai_generator: AI generator (ctx.ai)

    Returns:
        Filtered list of relevant skill dicts
    """
    if not all_skills or not ai_generator:
        return all_skills

    skills_summary = "\n".join(
        f"- {s['name']}: {s['description']}" for s in all_skills
    )
    diff_preview = diff[:8000]

    prompt = f"""Given this pull request diff, select which of the following project skills are relevant to apply during code review.

Available skills:
{skills_summary}

Diff (preview):
```diff
{diff_preview}
```

Respond with a JSON array of skill names that are relevant. Only include skills that provide useful guidelines for reviewing the changed code. If none are relevant, return [].

Example: ["kotlin", "architecture"]"""

    from titan_cli.ai.models import AIMessage
    try:
        response = ai_generator.generate(
            messages=[AIMessage(role="user", content=prompt)],
            max_tokens=200,
            temperature=0.1,
        )
        text = response.content.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        selected_names = json.loads(text)
        if not isinstance(selected_names, list):
            return all_skills

        selected = [s for s in all_skills if s["name"] in selected_names]
        return selected
    except Exception as e:
        logger.warning(f"Skill selection failed, using all skills: {e}")
        return all_skills


def build_review_context(
    pr: UIPullRequest,
    diff: str,
    changed_files: List[str],
    skills: List[Dict],
) -> str:
    """
    Build the full context string for the CodeReviewAgent.

    Args:
        pr: UIPullRequest model
        diff: Full unified diff of the PR
        changed_files: List of changed file paths
        skills: List of {"name", "content"} skill dicts

    Returns:
        Formatted context string for AI review
    """
    sections = []

    # PR metadata
    sections.append(f"""## Pull Request: #{pr.number} — {pr.title}

**Author**: {pr.author_name}
**Branches**: {pr.branch_info}
**Stats**: {pr.stats} across {pr.files_changed} file(s)
**Draft**: {"Yes" if pr.is_draft else "No"}

### Description
{pr.body or "(no description)"}""")

    # Changed files
    if changed_files:
        files_list = "\n".join(f"  - {f}" for f in changed_files)
        sections.append(f"## Changed Files\n{files_list}")

    # Project skills context
    if skills:
        skill_sections = []
        for skill in skills:
            skill_sections.append(f"### Skill: {skill['name']}\n{skill['content']}")
        sections.append("## Project Guidelines (Skills)\n\n" + "\n\n".join(skill_sections))
    else:
        sections.append(
            "## Project Guidelines\n\nNo project-specific skills found. "
            "Apply general best practices for code review."
        )

    # Diff
    max_diff_chars = 40_000
    diff_preview = diff[:max_diff_chars]
    if len(diff) > max_diff_chars:
        diff_preview += "\n\n... (diff truncated for length)"

    sections.append(f"## Pull Request Diff\n\n```diff\n{diff_preview}\n```")

    sections.append(
        "## Task\n\nReview the diff above against the project guidelines. "
        "Output a JSON array of review comments as specified in your system prompt."
    )

    return "\n\n".join(sections)


def extract_diff_for_file(full_diff: str, file_path: str) -> Optional[str]:
    """
    Extract the diff section for a specific file from a unified diff.

    Args:
        full_diff: Full unified diff string
        file_path: File path to extract diff for

    Returns:
        Diff section for the file, or None if not found
    """
    if not full_diff or not file_path:
        return None

    lines = full_diff.split("\n")
    result_lines: List[str] = []
    in_file = False

    for line in lines:
        # Detect start of a new file diff
        if line.startswith("diff --git "):
            if in_file:
                break  # We've passed the target file
            # Check if this is our target file
            if f"b/{file_path}" in line or line.endswith(file_path):
                in_file = True
                result_lines.append(line)
        elif in_file:
            result_lines.append(line)

    return "\n".join(result_lines) if result_lines else None


def compute_diff_stat(diff: str) -> Tuple[List[str], List[str]]:
    """
    Compute diff stat from a unified diff.

    Args:
        diff: Full unified diff string

    Returns:
        Tuple of (formatted_file_lines, formatted_summary_lines)
        Ready to be used with ctx.textual.show_diff_stat()
    """
    file_stats: Dict[str, tuple] = {}  # {file: (additions, deletions)}
    current_file = None

    for line in diff.split("\n"):
        # Match "diff --git" lines to track file
        if line.startswith("diff --git"):
            match = re.search(r"b/(.+)$", line)
            if match:
                current_file = match.group(1)
                file_stats[current_file] = (0, 0)

        # Count added lines (starting with +, but not +++ header)
        elif line.startswith("+") and not line.startswith("+++"):
            if current_file:
                adds, dels = file_stats[current_file]
                file_stats[current_file] = (adds + 1, dels)

        # Count deleted lines (starting with -, but not --- header)
        elif line.startswith("-") and not line.startswith("---"):
            if current_file:
                adds, dels = file_stats[current_file]
                file_stats[current_file] = (adds, dels + 1)

    # Format file lines
    formatted_files = []
    total_adds = 0
    total_dels = 0

    for file_path, (adds, dels) in sorted(file_stats.items()):
        total_adds += adds
        total_dels += dels
        # Format: "file.py | 5 ++---"
        bar = "[green]+" * adds + "[/green]" + "[red]-" * dels + "[/red]"
        line = f"{file_path} | {adds + dels:4} {bar}"
        formatted_files.append(line)

    # Format summary line
    num_files = len(file_stats)
    file_word = "file" if num_files == 1 else "files"
    summary = f"{num_files} {file_word} changed, " \
              f"{total_adds} insertions[green](+)[/green], " \
              f"{total_dels} deletions[red](-)[/red]"

    return formatted_files, [summary]


def extract_hunk_for_line(file_diff: str, target_line: Optional[int]) -> Optional[str]:
    """
    Extract the diff hunk (starting with @@) that contains the target line.

    Args:
        file_diff: Full file diff (starting with "diff --git ...")
        target_line: Line number to find

    Returns:
        The hunk string starting with @@, or None if not found
    """
    if not file_diff or not target_line:
        return None

    lines = file_diff.split("\n")
    hunks = []
    current_hunk: List[str] = []

    for line in lines:
        if line.startswith("@@"):
            if current_hunk:
                hunks.append("\n".join(current_hunk))
            current_hunk = [line]
        elif current_hunk:
            current_hunk.append(line)

    if current_hunk:
        hunks.append("\n".join(current_hunk))

    for hunk in hunks:
        hunk_lines = hunk.split("\n")
        header_match = re.search(r"\+(\d+),?(\d*)", hunk_lines[0])
        if not header_match:
            continue
        new_start = int(header_match.group(1))
        count_str = header_match.group(2)
        count = int(count_str) if count_str else 1
        new_end = new_start + count
        if new_start <= target_line <= new_end:
            return hunk

    # Fallback: return first hunk if no match found
    return hunks[0] if hunks else None


def build_review_payload(
    suggestions: List[UIReviewSuggestion],
    commit_id: str,
) -> Dict:
    """
    Build the GitHub API payload for creating a draft review.

    Args:
        suggestions: List of approved UIReviewSuggestion objects
        commit_id: Latest commit SHA for the PR

    Returns:
        Dict payload for create_draft_review
    """
    inline_comments = []
    general_comments: List[str] = []

    for s in suggestions:
        if s.line is not None:
            inline_comments.append({
                "path": s.file_path,
                "line": s.line,
                "body": s.body,
            })
        else:
            general_comments.append(f"**{s.file_path}**: {s.body}")

    payload: Dict = {
        "commit_id": commit_id,
        "event": "PENDING",
        "comments": inline_comments,
    }

    if general_comments:
        payload["body"] = "\n\n".join(general_comments)

    return payload
