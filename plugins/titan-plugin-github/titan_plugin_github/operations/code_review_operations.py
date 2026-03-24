# plugins/titan-plugin-github/titan_plugin_github/operations/code_review_operations.py
"""
Operations for AI-powered PR code review.

Pure business logic functions for loading project skills, building review
context, and constructing review payloads. All functions are UI-agnostic.
"""

import re
from pathlib import Path, PurePath
from typing import Dict, List, Optional, Tuple

from ..models.view import UIPullRequest, UIReviewSuggestion


def load_project_skills(changed_files: List[str]) -> List[Dict]:
    """
    Load project skills from .claude/skills/ that match changed files.

    Args:
        changed_files: List of file paths changed in the PR

    Returns:
        List of {"name": str, "content": str} dicts for matching skills
    """
    skills_dir = Path(".claude/skills")
    if not skills_dir.exists() or not skills_dir.is_dir():
        return []

    matching_skills = []

    for skill_file in sorted(skills_dir.glob("*.md")):
        try:
            content = skill_file.read_text(encoding="utf-8")
        except OSError:
            continue

        # Parse YAML frontmatter between --- delimiters
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        file_patterns: List[str] = []

        if frontmatter_match:
            frontmatter_text = frontmatter_match.group(1)
            # Extract file_patterns list from frontmatter
            patterns_match = re.search(
                r"file_patterns\s*:\s*\n((?:\s+-\s+.+\n?)+)",
                frontmatter_text
            )
            if patterns_match:
                pattern_lines = patterns_match.group(1).strip().split("\n")
                for line in pattern_lines:
                    stripped = line.strip().lstrip("- ").strip()
                    # Strip surrounding quotes (YAML quoted strings like "*Models.kt")
                    stripped = stripped.strip('"').strip("'")
                    if stripped:
                        file_patterns.append(stripped)

        # If no file_patterns in frontmatter, skill applies to all files
        if not file_patterns:
            matching_skills.append({
                "name": skill_file.stem,
                "content": content,
            })
            continue

        # Check if any changed file matches any pattern.
        # PurePath.match() matches from the right, so "network/*.kt" matches
        # "app/src/main/network/Foo.kt" correctly.
        matched = False
        for changed_file in changed_files:
            for pattern in file_patterns:
                try:
                    if PurePath(changed_file).match(pattern):
                        matched = True
                        break
                except (ValueError, TypeError):
                    continue
            if matched:
                break

        if matched:
            matching_skills.append({
                "name": skill_file.stem,
                "content": content,
            })

    return matching_skills


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
