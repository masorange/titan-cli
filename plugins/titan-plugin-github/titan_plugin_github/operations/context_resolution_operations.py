"""Operations for resolving bounded review context from a focused review plan."""

from pathlib import Path
from typing import Optional

from titan_cli.core.logging import get_logger

from ..managers.diff_context_manager import DiffContextManager
from ..models.review_enums import ContextRequestType, FileReadMode
from ..models.review_models import (
    ChangeManifest,
    CommentContextEntry,
    ContextRequest,
    ExcludedFileEntry,
    FileContextEntry,
    FileReviewPlan,
    FocusContextBatch,
    ReviewChecklistItem,
    ReviewContextPackage,
    ReviewPlan,
    ReviewStrategy,
)

logger = get_logger(__name__)


def extract_hunks_only(diff: str, path: str) -> list[str]:
    return DiffContextManager.from_diff(diff).get_hunk_texts(path)


def extract_expanded_hunks(diff: str, path: str, cwd: Optional[str] = None) -> list[str]:
    file_content = read_file_content(path, cwd)
    if not file_content:
        return extract_hunks_only(diff, path)

    return DiffContextManager.from_diff(diff).build_expanded_hunks(path, file_content, extra_lines=10)


def read_file_content(path: str, cwd: Optional[str] = None) -> Optional[str]:
    try:
        base = Path(cwd) if cwd else Path.cwd()
        file_path = base / path
        if file_path.exists() and file_path.is_file():
            return file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError) as e:
        logger.debug("Could not read %s: %s", path, e)
    return None


def _find_related_tests(path: str, cwd: Optional[str] = None) -> Optional[str]:
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
            return content
    return None


def _find_related_context(path: str, cwd: Optional[str] = None) -> Optional[str]:
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
            return content[:3000]
    return None


def resolve_context_requests(requests: list[ContextRequest], cwd: Optional[str] = None) -> dict[str, str]:
    result: dict[str, str] = {}
    for req in requests:
        key = f"{req.type}:{req.for_path}"
        if req.type == ContextRequestType.RELATED_TESTS:
            content = _find_related_tests(req.for_path, cwd)
        else:
            content = _find_related_context(req.for_path, cwd)
        if content:
            result[key] = content
    return result


def build_review_context_package(
    plan: ReviewPlan,
    diff: str,
    manifest: ChangeManifest,
    checklist: list[ReviewChecklistItem],
    comment_context: list[CommentContextEntry],
    strategy: ReviewStrategy,
    cwd: Optional[str] = None,
) -> ReviewContextPackage:
    applicable_ids = set(plan.review_axes)
    checklist_applicable = [item for item in checklist if item.id in applicable_ids] or checklist[:2]
    related_files = resolve_context_requests(plan.extra_context_requests, cwd)
    comment_context = comment_context[: strategy.max_comment_entries]

    batches: list[FocusContextBatch] = []
    current_files: dict[str, FileContextEntry] = {}
    current_chars = 0
    batch_index = 1
    carry_excluded: list[ExcludedFileEntry] = []

    for file_plan in plan.focus_files:
        entry = _resolve_file_context(file_plan, diff, cwd)
        entry_chars = _estimate_entry_chars(entry)

        if current_files and strategy.batching_enabled and current_chars + entry_chars > strategy.max_prompt_chars:
            batches.append(
                FocusContextBatch(
                    batch_id=f"batch_{batch_index}",
                    files_context=current_files,
                    comment_context=comment_context,
                    checklist_applicable=checklist_applicable,
                    related_files=related_files,
                    excluded_files=carry_excluded,
                    pr_manifest=manifest.pr,
                    approximate_chars=current_chars,
                )
            )
            batch_index += 1
            current_files = {}
            current_chars = 0
            carry_excluded = []

        if not strategy.batching_enabled and current_files and current_chars + entry_chars > strategy.max_prompt_chars:
            carry_excluded.append(
                ExcludedFileEntry(
                    path=file_plan.path,
                    reason="budget_trimmed",
                    detail="did not fit in direct context budget",
                )
            )
            continue

        current_files[file_plan.path] = entry
        current_chars += entry_chars

    if current_files:
        batches.append(
            FocusContextBatch(
                batch_id=f"batch_{batch_index}",
                files_context=current_files,
                comment_context=comment_context,
                checklist_applicable=checklist_applicable,
                related_files=related_files,
                excluded_files=carry_excluded,
                pr_manifest=manifest.pr,
                approximate_chars=current_chars,
            )
        )

    return ReviewContextPackage(batches=batches)


def _resolve_file_context(file_plan: FileReviewPlan, diff: str, cwd: Optional[str] = None) -> FileContextEntry:
    if file_plan.read_mode == FileReadMode.FULL_FILE:
        return FileContextEntry(path=file_plan.path, full_content=read_file_content(file_plan.path, cwd))
    if file_plan.read_mode == FileReadMode.EXPANDED_HUNKS:
        return FileContextEntry(path=file_plan.path, expanded_hunks=extract_expanded_hunks(diff, file_plan.path, cwd))
    return FileContextEntry(path=file_plan.path, hunks=extract_hunks_only(diff, file_plan.path))


def _estimate_entry_chars(entry: FileContextEntry) -> int:
    if entry.full_content:
        return len(entry.full_content)
    if entry.expanded_hunks:
        return sum(len(hunk) for hunk in entry.expanded_hunks)
    return sum(len(hunk) for hunk in entry.hunks)
