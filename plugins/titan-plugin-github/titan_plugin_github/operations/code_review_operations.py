# plugins/titan-plugin-github/titan_plugin_github/operations/code_review_operations.py
"""
Operations for AI-powered PR code review.

Pure business logic functions for loading project skills, building review
context, and constructing review payloads. All functions are UI-agnostic.
"""

import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from titan_cli.core.logging import get_logger
from ..managers.diff_context_manager import DiffContextManager
from ..models.view import UIReviewSuggestion, UIFileChange

logger = get_logger(__name__)


def load_project_claude_md() -> Optional[str]:
    """
    Load the project's CLAUDE.md file if it exists.

    Returns:
        Content of CLAUDE.md, or None if not found
    """
    for candidate in (Path("CLAUDE.md"), Path(".claude/CLAUDE.md")):
        if candidate.exists() and candidate.is_file():
            try:
                return candidate.read_text(encoding="utf-8")
            except OSError:
                return None
    return None


class ProjectInstructionFile(StrEnum):
    CLAUDE = "CLAUDE.md"   # Claude Code (Anthropic)
    GEMINI = "GEMINI.md"   # Gemini CLI (Google)
    CODEX  = "AGENTS.md"   # Codex (OpenAI)


def load_project_instructions() -> Optional[str]:
    """
    Load the project's AI instructions file if it exists.

    Checks for known instruction files used by Claude Code, Gemini CLI,
    and OpenAI Codex, in that order.

    Returns:
        Content of the first found instructions file, or None
    """
    for candidate in ProjectInstructionFile:
        path = Path(candidate)
        if path.exists() and path.is_file():
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                continue
    return None


def load_all_project_skills() -> List[Dict]:
    """
    Load all project skills from .claude/skills/ without filtering.

    Returns:
        List of {"name": str, "description": str, "content": str} dicts
    """
    return _load_markdown_files(Path(".claude/skills"))


def load_project_docs() -> List[Dict]:
    """
    Load all project docs from .claude/docs/ without filtering.

    Excludes the private/ subdirectory.

    Returns:
        List of {"name": str, "description": str, "content": str} dicts
    """
    docs_dir = Path(".claude/docs")
    if not docs_dir.exists() or not docs_dir.is_dir():
        return []

    result = []
    for md_file in sorted(docs_dir.glob("*.md")):
        # Exclude files in private/ subdirectories (only top-level .md files)
        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError:
            continue

        description = md_file.stem
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if frontmatter_match:
            desc_match = re.search(r"description\s*:\s*(.+)", frontmatter_match.group(1))
            if desc_match:
                description = desc_match.group(1).strip()

        result.append({
            "name": md_file.stem,
            "description": description,
            "content": content,
        })

    return result


def _load_markdown_files(directory: Path) -> List[Dict]:
    """
    Load all .md files from a directory.

    Returns:
        List of {"name": str, "description": str, "content": str} dicts
    """
    if not directory.exists() or not directory.is_dir():
        return []

    result = []
    for md_file in sorted(directory.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError:
            continue

        description = md_file.stem
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if frontmatter_match:
            desc_match = re.search(r"description\s*:\s*(.+)", frontmatter_match.group(1))
            if desc_match:
                description = desc_match.group(1).strip()

        result.append({
            "name": md_file.stem,
            "description": description,
            "content": content,
        })

    return result


def select_relevant_skills(
    all_skills: List[Dict],
    diff: str,
    ai_generator: Any,
    all_docs: Optional[List[Dict]] = None,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Use AI to select which skills and docs are relevant for the given diff.

    Args:
        all_skills: All available skills (from load_all_project_skills)
        diff: Unified diff of the PR
        ai_generator: AI generator (ctx.ai)
        all_docs: All available docs (from load_project_docs), optional

    Returns:
        Tuple of (selected_skills, selected_docs)
    """
    all_docs = all_docs or []

    if not ai_generator or (not all_skills and not all_docs):
        return all_skills, all_docs

    sections = []

    if all_skills:
        skills_summary = "\n".join(
            f"- {s['name']}: {s['description']}" for s in all_skills
        )
        sections.append(f"Code guidelines:\n{skills_summary}")

    if all_docs:
        docs_summary = "\n".join(
            f"- {d['name']}: {d['description']}" for d in all_docs
        )
        sections.append(f"Architecture documentation:\n{docs_summary}")

    context_summary = "\n\n".join(sections)
    diff_preview = diff[:8000]

    prompt = f"""Given this pull request diff, select which project guidelines and documentation are relevant for code review.

Available project context:
{context_summary}

Diff (preview):
```diff
{diff_preview}
```

Respond with a JSON object with two arrays:
- "skills": names from "Code guidelines" relevant to the changed code
- "docs": names from "Architecture documentation" relevant to the changed code

Only include items that provide useful guidelines for reviewing these specific changes. If none are relevant, use empty arrays.

Example: {{"skills": ["store", "testing"], "docs": ["architecture-mvi"]}}"""

    from titan_cli.ai.models import AIMessage
    try:
        response = ai_generator.generate(
            messages=[AIMessage(role="user", content=prompt)],
            max_tokens=300,
            temperature=0.1,
        )
        text = response.content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        # Extract only the JSON object, ignoring any trailing text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            logger.warning(f"No JSON object found in skill selection response: {text[:200]}")
            return [], []
        text = text[start:end]

        data = json.loads(text)
        if not isinstance(data, dict):
            logger.warning(f"Skill/doc selection returned unexpected type: {type(data)}, response: {text[:200]}")
            return [], []

        selected_skill_names = data.get("skills", [])
        selected_doc_names = data.get("docs", [])

        logger.debug(f"AI selected skills: {selected_skill_names}, docs: {selected_doc_names}")

        selected_skills = [s for s in all_skills if s["name"] in selected_skill_names]
        selected_docs = [d for d in all_docs if d["name"] in selected_doc_names]

        return selected_skills, selected_docs
    except Exception as e:
        logger.warning(f"Skill/doc selection failed: {e}")
        return [], []


_SUMMARY_HEADING_KEYWORDS = {
    "summary", "overview", "introduction", "about", "description",
    "resumen", "introducción", "descripción",
}


def extract_doc_summary(content: str, max_chars: int = 2000) -> str:
    """
    Extract an introductory summary from a doc file for AI context.

    Strategy (in order):
    1. If a known summary-like heading (## Summary, ## Overview, etc.) exists,
       extract only that section.
    2. Otherwise, return the first max_chars characters of the document.

    This is robust to any doc structure regardless of authoring tool.
    """
    lines = content.split("\n")
    in_summary_section = False
    summary_lines: List[str] = []

    for line in lines:
        if line.startswith("## "):
            heading_text = line[3:].strip().lower().rstrip(":")
            if heading_text in _SUMMARY_HEADING_KEYWORDS:
                in_summary_section = True
                summary_lines.append(line)
                continue
            elif in_summary_section:
                break  # End of the summary section

        if in_summary_section:
            summary_lines.append(line)

    if summary_lines:
        result = "\n".join(summary_lines).strip()
        if len(result) > max_chars:
            result = result[:max_chars] + "\n... (truncated)"
        return result

    # Fallback: plain truncation — works for any structure
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "\n... (truncated)"


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
            if f" b/{file_path}" in line or line.endswith(file_path):
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
            match = re.search(r" b/(.+)$", line)
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
        bar = f"[green]{'+'*adds}[/green][red]{'-'*dels}[/red]"
        line = f"{file_path} | {adds + dels:4} {bar}"
        formatted_files.append(line)

    # Format summary line
    num_files = len(file_stats)
    file_word = "file" if num_files == 1 else "files"
    summary = f"{num_files} {file_word} changed, " \
              f"{total_adds} insertions[green](+)[/green], " \
              f"{total_dels} deletions[red](-)[/red]"

    return formatted_files, [summary]


MAX_FILES_FOR_REVIEW = 20


def select_files_for_review(
    files_with_stats: List[UIFileChange],
    ai_generator: Any,
) -> List[str]:
    """
    Use AI to select the most important files to review from a large PR.

    Passes full file stats (additions, deletions, status) so AI can make
    informed decisions. The AI decides how many files matter — no hardcoded limit.

    Args:
        files_with_stats: All changed files with stats as UIFileChange objects
        ai_generator: AI generator (ctx.ai)

    Returns:
        Selected file paths — number decided by AI based on importance
    """
    all_paths = [f.path for f in files_with_stats]

    if not ai_generator:
        return all_paths[:MAX_FILES_FOR_REVIEW]

    files_summary = "\n".join(
        f"  {f.status:8} +{f.additions:<4} -{f.deletions:<4}  {f.path}"
        for f in files_with_stats
    )

    prompt = f"""A pull request has {len(files_with_stats)} changed files.

Select the files that genuinely need code review for correctness, bugs, security, and business logic.
Return ONLY files that are worth reviewing. Skip trivial files like:
- Auto-generated code
- Resource/asset files (strings.xml, drawables, icons, translations)
- Lock files or build configs (package-lock.json, *.gradle, *.podspec)
- Test fixtures or snapshots
- Purely cosmetic changes (only whitespace/formatting)

Changed files (status | +additions | -deletions | path):
{files_summary}

Respond with a JSON array of file paths that need review. The number is up to you based on what actually matters.
Example: ["app/src/main/Foo.kt", "lib/Bar.kt"]"""

    from titan_cli.ai.models import AIMessage
    try:
        response = ai_generator.generate(
            messages=[AIMessage(role="user", content=prompt)],
            max_tokens=2000,
            temperature=0.1,
        )
        text = response.content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            return all_paths[:MAX_FILES_FOR_REVIEW]

        selected = json.loads(text[start:end])
        if not isinstance(selected, list):
            return all_paths[:MAX_FILES_FOR_REVIEW]

        valid = [f for f in selected if f in all_paths]
        return valid if valid else all_paths[:MAX_FILES_FOR_REVIEW]
    except Exception as e:
        logger.warning(f"File selection failed, using first {MAX_FILES_FOR_REVIEW} files: {e}")
        return all_paths[:MAX_FILES_FOR_REVIEW]


def extract_line_number_from_hunk(hunk: str) -> Optional[int]:
    """
    Find the first added line (+) in a diff hunk and return its correct line number.

    Args:
        hunk: Diff hunk string starting with @@

    Returns:
        Correct line number of the first added line in the new file, or None
    """
    if not hunk:
        return None
    manager = DiffContextManager.from_file_diff(hunk, "__hunk__")
    parsed_hunks = manager.get_hunks("__hunk__")
    if not parsed_hunks:
        return None
    first_hunk = parsed_hunks[0]
    current = first_hunk.new_line_start
    for line in first_hunk.content.split("\n")[1:]:
        if line.startswith("+") and not line.startswith("+++"):
            return current
        elif line.startswith(" "):
            current += 1
    return first_hunk.new_line_start


def extract_hunk_for_line(file_diff: str, target_line: Optional[int]) -> Optional[str]:
    """
    Extract the diff hunk (starting with @@) that contains the target line.

    Args:
        file_diff: File diff section (from extract_diff_for_file)
        target_line: Line number to find

    Returns:
        The hunk string starting with @@, or None if not found
    """
    if not file_diff or not target_line:
        return None
    manager = DiffContextManager.from_file_diff(file_diff, "__file__")
    hunk = manager.get_hunk_for_line("__file__", target_line)
    return hunk.content if hunk else None


def find_line_by_snippet(file_diff: str, snippet: str) -> Optional[int]:
    """
    Find the new-file line number of a code snippet within a file's diff.

    Args:
        file_diff: Diff section for a single file (from extract_diff_for_file)
        snippet: Exact code text to search for (trimmed match)

    Returns:
        New-file line number if found, or None
    """
    if not file_diff or not snippet:
        return None
    return DiffContextManager.from_file_diff(file_diff, "__file__").find_line_by_snippet("__file__", snippet)


def extract_valid_diff_lines(diff: str) -> Dict[str, set]:
    """
    Parse a unified diff and extract which line numbers of the new file are present.

    Only lines reachable on the RIGHT side (added or context lines) are valid
    targets for inline review comments.

    Args:
        diff: Full unified diff string

    Returns:
        Dict mapping file_path -> set of valid new-file line numbers
    """
    return {
        path: set(lines)
        for path, lines in DiffContextManager.from_diff(diff).get_all_valid_lines().items()
    }


def build_review_payload(
    suggestions: List[UIReviewSuggestion],
    commit_id: str,
    diff: str = "",
) -> Dict:
    """
    Build the GitHub API payload for creating a draft review.

    Validates inline comment line numbers against the actual diff to ensure
    GitHub accepts them. Comments on lines not present in the diff fall back
    to general comments.

    Args:
        suggestions: List of approved UIReviewSuggestion objects
        commit_id: Latest commit SHA for the PR
        diff: Full unified diff (used to validate line numbers)

    Returns:
        Dict payload for create_draft_review
    """

    valid_lines_by_file = extract_valid_diff_lines(diff) if diff else {}
    logger.info(f"Valid diff lines by file: { {f: sorted(list(lines)[:5]) for f, lines in valid_lines_by_file.items()} }")

    inline_comments = []
    general_comments: List[str] = []

    for s in suggestions:
        # Replies to existing threads use in_reply_to — no path/line needed
        if s.reply_to_comment_id is not None:
            inline_comments.append({
                "body": s.body,
                "in_reply_to": s.reply_to_comment_id,
            })
            logger.info(f"Reply comment to thread {s.reply_to_comment_id}")
            continue

        # Resolve line from snippet if available (more accurate than AI-reported line)
        resolved_line = s.line

        if s.snippet and diff:
            file_diff = extract_diff_for_file(diff, s.file_path)
            if file_diff:
                snippet_line = find_line_by_snippet(file_diff, s.snippet)
                if snippet_line is not None:
                    resolved_line = snippet_line

        if resolved_line is not None:
            file_valid_lines = valid_lines_by_file.get(s.file_path, set())

            if resolved_line in file_valid_lines:
                inline_comments.append({
                    "path": s.file_path,
                    "line": resolved_line,
                    "side": "RIGHT",
                    "body": s.body,
                })
                logger.info(f"Inline comment: {s.file_path}:{resolved_line}")
            else:
                logger.info(
                    f"Line {resolved_line} not in diff for {s.file_path} "
                    f"(valid: {sorted(file_valid_lines)[:20]}) → general comment"
                )
                general_comments.append(f"**{s.file_path}** (line {resolved_line}):\n{s.body}")
        else:
            general_comments.append(f"**{s.file_path}**: {s.body}")

    logger.info(f"Review payload: {len(inline_comments)} inline, {len(general_comments)} general")

    payload: Dict = {
        "commit_id": commit_id,
        "comments": inline_comments,
    }

    if general_comments:
        payload["body"] = "\n\n".join(general_comments)

    return payload
