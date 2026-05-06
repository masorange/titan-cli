# plugins/titan-plugin-github/titan_plugin_github/operations/code_review_operations.py
"""
Operations for AI-powered PR code review.

Pure business logic functions for loading project skills, building review
context, and inspecting diff content. All functions are UI-agnostic.
"""

import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from titan_cli.core.logging import get_logger
from ..managers.diff_context_manager import DiffContextManager
from ..models.view import UIFileChange

logger = get_logger(__name__)
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
