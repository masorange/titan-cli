"""
Diff Context Manager

Central hub for all diff parsing, line resolution, and context extraction.
Replaces the scattered diff logic previously spread across comment_utils,
code_review_operations, context_resolution_operations, and thread_resolution_operations.

Usage:
    manager = DiffContextManager.from_diff(pr_diff)
    hunk = manager.get_hunk_for_line("src/foo.py", 42)
    ctx  = manager.build_comment_context(ui_comment)
"""

from __future__ import annotations

import re
from typing import Optional

from ..models.diff_models import (
    ParsedDiff,
    ParsedFileDiff,
    ParsedHunk,
    ResolvedCommentContext,
)
from ..models.view import UIComment

_HUNK_HEADER_RE = re.compile(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@(.*)")
_FILE_HEADER_RE = re.compile(r"^diff --git a/.+ b/(.+)$")


class DiffContextManager:
    """
    Parses a unified diff once and exposes high-level query methods.

    All parsing happens at construction time and results are cached internally.
    Use ``from_diff`` to create instances.
    """

    def __init__(self, parsed: ParsedDiff) -> None:
        self._parsed = parsed

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_diff(cls, diff: str) -> DiffContextManager:
        """
        Parse a unified diff string and return a ready-to-use manager.

        Args:
            diff: Full unified diff (e.g. from ``gh pr diff``)

        Returns:
            DiffContextManager with all hunks indexed
        """
        return cls(_parse_diff(diff))

    @classmethod
    def from_file_diff(cls, file_diff: str, path: str) -> DiffContextManager:
        """
        Parse a single-file diff section (with or without ``diff --git`` header).

        Use when only a per-file slice is available (e.g. from ``extract_diff_for_file``).
        The ``path`` argument is the key used to look up results via ``get_hunks(path)``.

        Args:
            file_diff: Diff section for a single file
            path: Logical path key for this diff (used in subsequent lookups)

        Returns:
            DiffContextManager with hunks indexed under ``path``
        """
        parsed_file = _parse_file_diff_section(path, file_diff)
        files = {path: parsed_file} if parsed_file else {}
        return cls(ParsedDiff(files=files, raw=file_diff))

    # ------------------------------------------------------------------
    # File / hunk lookups
    # ------------------------------------------------------------------

    def get_file(self, path: str) -> Optional[ParsedFileDiff]:
        """Return parsed file diff for ``path``, or None if not in diff."""
        return self._parsed.files.get(path)

    def get_hunks(self, path: str) -> list[ParsedHunk]:
        """Return all hunks for ``path``, empty list if file not in diff."""
        file_diff = self._parsed.files.get(path)
        return file_diff.hunks if file_diff else []

    def get_hunk_for_line(self, path: str, line: int) -> Optional[ParsedHunk]:
        """
        Return the hunk containing new-file ``line`` for ``path``.

        Falls back to the first hunk when no exact match is found.
        """
        hunks = self.get_hunks(path)
        if not hunks:
            return None
        for hunk in hunks:
            if hunk.contains_new_line(line):
                return hunk
        return hunks[0]

    def get_hunk_for_old_line(self, path: str, line: int) -> Optional[ParsedHunk]:
        """
        Return the hunk containing old-file ``line`` for ``path``.

        Used for outdated comments where only ``originalLine`` is available.
        Falls back to the last hunk.
        """
        hunks = self.get_hunks(path)
        if not hunks:
            return None
        for hunk in hunks:
            if hunk.contains_old_line(line):
                return hunk
        return hunks[-1]

    # ------------------------------------------------------------------
    # Valid review lines
    # ------------------------------------------------------------------

    def get_valid_review_lines(self, path: str) -> frozenset:
        """
        Return new-file line numbers valid for inline comments in ``path``.

        Only added ('+') and context (' ') lines are valid targets.
        """
        file_diff = self._parsed.files.get(path)
        return file_diff.valid_review_lines if file_diff else frozenset()

    def get_all_valid_lines(self) -> dict[str, frozenset]:
        """
        Return ``{path: frozenset[line]}`` for every file in the diff.

        Replaces ``extract_valid_diff_lines`` from code_review_operations.
        """
        return {path: fd.valid_review_lines for path, fd in self._parsed.files.items()}

    # ------------------------------------------------------------------
    # Snippet search
    # ------------------------------------------------------------------

    def find_line_by_snippet(self, path: str, snippet: str) -> Optional[int]:
        """
        Find the new-file line number of the first added/context line containing
        ``snippet`` in ``path``.

        Returns None if the snippet is not found.
        """
        if not snippet:
            return None
        snippet_stripped = snippet.strip()
        for hunk in self.get_hunks(path):
            lines = hunk.content.split("\n")
            current = hunk.new_line_start
            for line in lines[1:]:  # skip @@ header
                if line.startswith("+") and not line.startswith("+++"):
                    if snippet_stripped in line[1:].strip():
                        return current
                    current += 1
                elif line.startswith(" "):
                    if snippet_stripped in line[1:].strip():
                        return current
                    current += 1
        return None

    # ------------------------------------------------------------------
    # Context extraction for UI
    # ------------------------------------------------------------------

    def build_focused_diff(
        self,
        path: str,
        line: int,
        is_outdated: bool = False,
        before: int = 7,
        after: int = 3,
    ) -> str:
        """
        Return a trimmed diff fragment centred on ``line``.

        For outdated comments falls back to the last ``before + after`` lines.
        Replaces ``extract_diff_context`` + ``_rebuild_diff`` from comment_utils.
        """
        if is_outdated:
            hunk = self.get_hunk_for_old_line(path, line)
        else:
            hunk = self.get_hunk_for_line(path, line)

        if not hunk:
            return ""

        return _build_focused_diff_from_hunk(
            hunk.content, line, is_outdated, before=before, after=after
        )

    def extract_original_lines_for_suggestion(
        self,
        path: str,
        line: int,
        count: int = 1,
    ) -> Optional[str]:
        """
        Extract ``count`` consecutive lines starting at new-file ``line``
        from the diff for ``path``.

        Replaces ``_extract_lines_from_diff`` from comment_utils.
        """
        hunk = self.get_hunk_for_line(path, line)
        if not hunk:
            return None
        return _extract_lines_from_hunk(hunk.content, line, count)

    def build_comment_context(self, comment: UIComment) -> ResolvedCommentContext:
        """
        Build a ``ResolvedCommentContext`` for a UIComment.

        Resolves the focused diff and full hunk. ``is_outdated`` is True only when
        the comment has an ``original_line`` (from old file) but no ``position``
        (GitHub's marker for outdated comments).
        Falls back to the diffHunk stored on the comment itself when the file
        is not present in the diff.
        """
        is_outdated = comment.position is None and comment.original_line is not None
        effective_line = comment.original_line if is_outdated else comment.line

        focused = ""
        full_hunk: Optional[str] = None

        if comment.path and effective_line:
            focused = self.build_focused_diff(
                comment.path, effective_line, is_outdated=is_outdated
            )
            hunk = (
                self.get_hunk_for_old_line(comment.path, effective_line)
                if is_outdated
                else self.get_hunk_for_line(comment.path, effective_line)
            )
            full_hunk = hunk.content if hunk else None

        if not focused and comment.diff_hunk:
            # Fallback: use the diffHunk stored on the comment itself
            focused = _build_focused_diff_from_hunk(
                comment.diff_hunk, effective_line, is_outdated
            )
            full_hunk = full_hunk or comment.diff_hunk

        return ResolvedCommentContext(
            comment_id=comment.id,
            is_outdated=is_outdated,
            path=comment.path,
            line=effective_line,
            position=comment.position,
            focused_diff=focused,
            full_hunk=full_hunk,
            body=comment.body,
            author_name=comment.author_name,
            formatted_date=comment.formatted_date,
        )


# ------------------------------------------------------------------
# Internal parsing helpers
# ------------------------------------------------------------------

def _parse_file_diff_section(path: str, file_section: str) -> Optional[ParsedFileDiff]:
    """
    Parse a per-file diff section into a ``ParsedFileDiff``.

    Handles sections that may or may not include a ``diff --git`` header —
    only ``@@`` hunk lines are required.
    """
    hunks: list[ParsedHunk] = []
    current_hunk_lines: list[str] = []

    for line in file_section.split("\n"):
        if line.startswith("@@"):
            if current_hunk_lines:
                hunk = _parse_hunk(path, "\n".join(current_hunk_lines))
                if hunk:
                    hunks.append(hunk)
            current_hunk_lines = [line]
        elif current_hunk_lines:
            current_hunk_lines.append(line)

    if current_hunk_lines:
        hunk = _parse_hunk(path, "\n".join(current_hunk_lines))
        if hunk:
            hunks.append(hunk)

    return ParsedFileDiff(path=path, hunks=hunks) if hunks else None


def _parse_diff(raw: str) -> ParsedDiff:
    """Parse a full unified diff into structured ``ParsedDiff``."""
    files: dict[str, ParsedFileDiff] = {}
    current_path: Optional[str] = None
    current_hunk_lines: list[str] = []

    def _flush_hunk() -> None:
        if current_path and current_hunk_lines:
            hunk = _parse_hunk(current_path, "\n".join(current_hunk_lines))
            if hunk:
                files[current_path].hunks.append(hunk)

    for raw_line in raw.split("\n"):
        file_match = _FILE_HEADER_RE.match(raw_line)
        if file_match:
            _flush_hunk()
            current_hunk_lines = []
            current_path = file_match.group(1)
            if current_path not in files:
                files[current_path] = ParsedFileDiff(path=current_path, hunks=[])
            continue

        if raw_line.startswith("@@") and current_path:
            _flush_hunk()
            current_hunk_lines = [raw_line]
            continue

        if current_hunk_lines:
            current_hunk_lines.append(raw_line)

    _flush_hunk()
    return ParsedDiff(files=files, raw=raw)


def _parse_hunk(path: str, content: str) -> Optional[ParsedHunk]:
    """Parse a single hunk string into a ``ParsedHunk``. Returns None on malformed header."""
    lines = content.split("\n")
    if not lines:
        return None

    header_match = _HUNK_HEADER_RE.match(lines[0])
    if not header_match:
        return None

    old_start = int(header_match.group(1))
    old_count = int(header_match.group(2)) if header_match.group(2) else 1
    new_start = int(header_match.group(3))
    new_count = int(header_match.group(4)) if header_match.group(4) else 1

    valid_lines: set[int] = set()
    current = new_start

    for line in lines[1:]:
        if line.startswith("+") and not line.startswith("+++"):
            valid_lines.add(current)
            current += 1
        elif line.startswith(" "):
            valid_lines.add(current)
            current += 1
        # '-' lines: do not advance new-file counter

    return ParsedHunk(
        header=lines[0],
        content=content,
        path=path,
        old_line_start=old_start,
        old_line_count=old_count,
        new_line_start=new_start,
        new_line_count=new_count,
        valid_review_lines=frozenset(valid_lines),
    )


def _build_focused_diff_from_hunk(
    hunk_content: str,
    target_line: Optional[int],
    is_outdated: bool = False,
    before: int = 7,
    after: int = 3,
) -> str:
    """Trim a hunk to a window of ``before`` + target + ``after`` lines."""
    if not hunk_content:
        return ""

    lines = hunk_content.split("\n")
    header_match = _HUNK_HEADER_RE.match(lines[0])
    if not header_match:
        return hunk_content

    old_start = int(header_match.group(1))
    new_start = int(header_match.group(3))
    header_suffix = header_match.group(5)

    old_line = old_start
    new_line = new_start

    parsed: list[tuple] = []  # (old_num, new_num, raw_line, idx)
    for idx, raw in enumerate(lines[1:], start=1):
        if raw.startswith("+") and not raw.startswith("+++"):
            parsed.append((None, new_line, raw, idx))
            new_line += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            parsed.append((old_line, None, raw, idx))
            old_line += 1
        elif raw.startswith(" "):
            parsed.append((old_line, new_line, raw, idx))
            old_line += 1
            new_line += 1
        else:
            parsed.append((None, None, raw, idx))

    target_idx: Optional[int] = None
    if not is_outdated and target_line:
        for _, new_num, _, idx in parsed:
            if new_num == target_line:
                target_idx = idx
                break

    if target_idx is not None:
        min_idx = max(0, target_idx - before - 1)
        max_idx = min(len(parsed) - 1, target_idx + after - 1)
        extracted = parsed[min_idx : max_idx + 1]
    elif len(parsed) > before + after:
        extracted = parsed[-(before + after):]
    else:
        return hunk_content

    return _rebuild_diff(extracted, old_start, new_start, header_suffix, target_line)


def _rebuild_diff(
    extracted: list[tuple],
    old_start: int,
    new_start: int,
    header_suffix: str,
    target_line: Optional[int] = None,
) -> str:
    """Reconstruct a valid diff header + lines from extracted parsed lines."""
    extracted_new_start: Optional[int] = None
    extracted_old_start: Optional[int] = None

    for old_num, new_num, _, _ in extracted:
        if extracted_new_start is None and new_num is not None:
            extracted_new_start = new_num
        if extracted_old_start is None and old_num is not None:
            extracted_old_start = old_num
        if extracted_new_start is not None and extracted_old_start is not None:
            break

    if extracted_new_start is None:
        extracted_new_start = new_start
    if extracted_old_start is None:
        extracted_old_start = old_start

    old_count = sum(1 for _, _, raw, _ in extracted if raw.startswith("-") or raw.startswith(" "))
    new_count = sum(1 for _, _, raw, _ in extracted if raw.startswith("+") or raw.startswith(" "))

    header = (
        f"@@ -{extracted_old_start},{old_count}"
        f" +{extracted_new_start},{new_count} @@{header_suffix}"
    )

    result_lines = []
    for _, new_num, raw, _ in extracted:
        if target_line and new_num == target_line:
            result_lines.append(raw + "  ◄")
        else:
            result_lines.append(raw)

    return header + "\n" + "\n".join(result_lines)


def _extract_lines_from_hunk(
    hunk_content: str,
    target_line: int,
    count: int = 1,
) -> Optional[str]:
    """
    Extract ``count`` consecutive new-file lines starting at ``target_line``.

    Replaces ``_extract_lines_from_diff`` from comment_utils.
    """
    lines = hunk_content.split("\n")
    header_match = _HUNK_HEADER_RE.match(lines[0])
    if not header_match:
        return None

    current = int(header_match.group(3))
    extracted: list[str] = []

    for line in lines[1:]:
        if line.startswith("+") and not line.startswith("+++"):
            if current >= target_line and len(extracted) < count:
                extracted.append(line[1:])
            current += 1
        elif line.startswith(" "):
            if current >= target_line and len(extracted) < count:
                extracted.append(line[1:])
            current += 1
        if len(extracted) >= count:
            break

    return "\n".join(extracted) if extracted else None


def extract_lines_from_hunk(hunk_content: str, target_line: int, count: int = 1) -> Optional[str]:
    """
    Extract ``count`` consecutive new-file lines starting at ``target_line`` from a hunk string.

    Convenience wrapper for callers that only have a single hunk string (e.g. comment_utils),
    not a full diff. Delegates to the internal helper.
    """
    return _extract_lines_from_hunk(hunk_content, target_line, count)


def build_focused_diff_from_hunk(
    hunk_content: str,
    target_line: Optional[int],
    is_outdated: bool = False,
    before: int = 7,
    after: int = 3,
) -> str:
    """
    Trim a hunk string to a focused window around ``target_line``.

    Convenience wrapper for callers that only have a single hunk string (e.g. comment_utils
    and comment_view), not a full diff. Delegates to the internal helper.
    """
    return _build_focused_diff_from_hunk(hunk_content, target_line, is_outdated, before, after)


__all__ = ["DiffContextManager", "extract_lines_from_hunk", "build_focused_diff_from_hunk"]
