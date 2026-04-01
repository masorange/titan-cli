"""
Operations for resolving review context from the AI plan.

Pure functions that extract exact code from a diff or filesystem
according to FileReviewPlan decisions (hunks_only, expanded_hunks, full_file).
No UI, no side effects.

Diff parsing delegated to DiffContextManager.
"""

import logging
import re
from pathlib import Path
from typing import Optional

from ..managers.diff_context_manager import DiffContextManager
from ..models.review_enums import ContextRequestType, FileReadMode
from ..models.review_models import (
    ChangeManifest,
    ContextRequest,
    ExistingCommentIndexEntry,
    FileContextEntry,
    FileReviewPlan,
    ReviewChecklistItem,
    ReviewContextPackage,
    ReviewPlan,
)

logger = logging.getLogger(__name__)

def extract_hunks_only(diff: str, path: str) -> list[str]:
    """
    Extract the diff hunks for a file (hunks_only mode).

    The diff already has extended context (20 lines) from the fetch step,
    so hunks_only provides meaningful surrounding code without extra reads.

    Args:
        diff: Full unified diff
        path: File path

    Returns:
        List of hunk strings (each starts with @@)
    """
    return [h.content for h in DiffContextManager.from_diff(diff).get_hunks(path)]


def extract_expanded_hunks(diff: str, path: str, cwd: Optional[str] = None) -> list[str]:
    """
    Extract hunks plus additional surrounding lines from the actual file.

    For each hunk, reads the current file from disk and prepends extra lines
    of context beyond what the diff already provides.

    Args:
        diff: Full unified diff
        path: File path
        cwd: Working directory (project root) to read the file from

    Returns:
        List of expanded hunk strings; falls back to plain hunks if file unreadable
    """
    base_hunks = extract_hunks_only(diff, path)
    if not base_hunks:
        return []

    file_content = read_file_content(path, cwd)
    if not file_content:
        return base_hunks

    file_lines = file_content.split("\n")
    extra_lines = 10
    expanded: list[str] = []

    for hunk in base_hunks:
        hunk_lines = hunk.split("\n")
        header = hunk_lines[0]

        m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", header)
        if not m:
            expanded.append(hunk)
            continue

        start_line = int(m.group(1))
        line_count = int(m.group(2)) if m.group(2) else 1

        expand_start = max(0, start_line - extra_lines - 1)
        expand_end = min(len(file_lines), start_line + line_count + extra_lines)

        surrounding = "\n".join(file_lines[expand_start:expand_end])
        expanded_block = (
            f"{header}\n"
            f"# --- surrounding context (lines {expand_start + 1}–{expand_end}) ---\n"
            f"{surrounding}\n"
            f"# --- diff hunk ---\n"
            + "\n".join(hunk_lines[1:])
        )
        expanded.append(expanded_block)

    return expanded

def read_file_content(path: str, cwd: Optional[str] = None) -> Optional[str]:
    """
    Read a file from the working directory.

    Args:
        path: Relative file path
        cwd: Working directory (project root); defaults to process cwd if None

    Returns:
        File content as string, or None if not readable
    """
    try:
        base = Path(cwd) if cwd else Path.cwd()
        file_path = base / path
        if file_path.exists() and file_path.is_file():
            return file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError) as e:
        logger.debug(f"Could not read {path}: {e}")
    return None

def _find_related_tests(path: str, cwd: Optional[str] = None) -> Optional[str]:
    """
    Find and read the test file corresponding to a source file.

    Tries common test file naming conventions in order:
    - tests/test_<stem>.<ext> (alongside the file)
    - test_<stem>.<ext> (same directory)
    - <stem>_test.<ext> (same directory)
    - tests/test_<stem>.<ext> (from project root)

    Args:
        path: Source file path
        cwd: Working directory

    Returns:
        Content of the test file if found, or None
    """
    p = Path(path)
    stem = p.stem

    candidates = [
        p.parent / "tests" / f"test_{stem}{p.suffix}",
        p.parent / f"test_{stem}{p.suffix}",
        p.parent / f"{stem}_test{p.suffix}",
        Path("tests") / f"test_{stem}{p.suffix}",
        Path("tests") / p.parent / f"test_{stem}{p.suffix}",
    ]

    for candidate in candidates:
        content = read_file_content(str(candidate), cwd)
        if content:
            logger.debug(f"Found related test for {path}: {candidate}")
            return content

    return None


def _find_related_context(path: str, cwd: Optional[str] = None) -> Optional[str]:
    """
    Find and read a related context file (parent module, interface, etc).

    Tries in order: __init__.py, protocols.py, interfaces.py, base_<stem>.py.
    Truncates to 3000 chars to avoid bloating context.

    Args:
        path: Source file path
        cwd: Working directory

    Returns:
        Content of the related context file (truncated) if found, or None
    """
    p = Path(path)

    candidates = [
        p.parent / "__init__.py",
        p.parent / "protocols.py",
        p.parent / "interfaces.py",
        p.parent / f"base_{p.stem}{p.suffix}",
        p.parent / f"{p.stem}_base{p.suffix}",
    ]

    for candidate in candidates:
        if candidate == p:
            continue
        content = read_file_content(str(candidate), cwd)
        if content:
            logger.debug(f"Found related context for {path}: {candidate}")
            return content[:3000]

    return None


def resolve_context_requests(
    requests: list[ContextRequest],
    cwd: Optional[str] = None,
) -> dict[str, str]:
    """
    Resolve extra context requests from the ReviewPlan.

    Args:
        requests: List of ContextRequest from the AI plan
        cwd: Working directory (project root)

    Returns:
        Dict mapping "{type}:{for_path}" → file content
    """
    result: dict[str, str] = {}

    for req in requests:
        key = f"{req.type}:{req.for_path}"

        if req.type == ContextRequestType.RELATED_TESTS:
            content = _find_related_tests(req.for_path, cwd)
            if content:
                result[key] = content
            else:
                logger.debug(f"No related tests found for {req.for_path}")

        elif req.type == ContextRequestType.RELATED_CONTEXT:
            content = _find_related_context(req.for_path, cwd)
            if content:
                result[key] = content
            else:
                logger.debug(f"No related context found for {req.for_path}")

    return result

def _resolve_file_context(
    file_plan: FileReviewPlan,
    diff: str,
    cwd: Optional[str] = None,
) -> FileContextEntry:
    """
    Extract file content according to the read_mode in the plan.

    Args:
        file_plan: Plan for this specific file
        diff: Full unified diff
        cwd: Working directory

    Returns:
        FileContextEntry with the appropriate content populated
    """
    path = file_plan.path

    if file_plan.read_mode == FileReadMode.FULL_FILE:
        content = read_file_content(path, cwd)
        return FileContextEntry(path=path, full_content=content)

    if file_plan.read_mode == FileReadMode.EXPANDED_HUNKS:
        hunks = extract_expanded_hunks(diff, path, cwd)
        return FileContextEntry(path=path, expanded_hunks=hunks)

    # hunks_only (default)
    hunks = extract_hunks_only(diff, path)
    return FileContextEntry(path=path, hunks=hunks)


def build_review_context_package(
    plan: ReviewPlan,
    diff: str,
    manifest: ChangeManifest,
    checklist: list[ReviewChecklistItem],
    comments_index: list[ExistingCommentIndexEntry],
    cwd: Optional[str] = None,
) -> ReviewContextPackage:
    """
    Build the complete context package for the second AI call.

    Extracts exact file content according to each FileReviewPlan decision
    and resolves any extra context requests from the plan.

    Args:
        plan: Validated ReviewPlan from the first AI call
        diff: Full unified diff of the PR
        manifest: PR change manifest (for pr_manifest field)
        checklist: Full review checklist (filtered to applicable items)
        comments_index: Existing comments for deduplication context
        cwd: Working directory (project root)

    Returns:
        ReviewContextPackage ready for the second AI call
    """
    files_context: dict[str, FileContextEntry] = {}
    for file_plan in plan.file_plan:
        files_context[file_plan.path] = _resolve_file_context(file_plan, diff, cwd)

    applicable_ids = set(plan.applicable_checklist)
    checklist_applicable = [item for item in checklist if item.id in applicable_ids]

    related_files = resolve_context_requests(plan.extra_context_requests, cwd)

    return ReviewContextPackage(
        files_context=files_context,
        checklist_applicable=checklist_applicable,
        existing_comments_compact=comments_index,
        pr_manifest=manifest.pr,
        related_files=related_files,
    )
