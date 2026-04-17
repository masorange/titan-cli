"""Operations for resolving bounded review context from a focused review plan."""

from pathlib import Path
from typing import Optional

from titan_cli.core.logging import get_logger

from ..managers.diff_context_manager import DiffContextManager, get_or_create_diff_manager
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


def extract_hunks_only(
    diff: str,
    path: str,
    diff_manager: Optional[DiffContextManager] = None,
) -> list[str]:
    manager = diff_manager or DiffContextManager.from_diff(diff)
    return manager.get_hunk_texts(path)


def extract_expanded_hunks(
    diff: str,
    path: str,
    cwd: Optional[str] = None,
    diff_manager: Optional[DiffContextManager] = None,
) -> list[str]:
    file_content = read_file_content(path, cwd)
    if not file_content:
        return extract_hunks_only(diff, path, diff_manager=diff_manager)

    manager = diff_manager or DiffContextManager.from_diff(diff)
    return manager.build_expanded_hunks(path, file_content, extra_lines=10)


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
    diff_manager: Optional[DiffContextManager] = None,
) -> ReviewContextPackage:
    manager = diff_manager or get_or_create_diff_manager(diff)
    applicable_ids = set(plan.review_axes)
    checklist_applicable = [item for item in checklist if item.id in applicable_ids] or checklist[:2]
    related_files = resolve_context_requests(plan.extra_context_requests[:1], cwd)
    comment_context = comment_context[: strategy.max_comment_entries]
    content_budget = _content_budget(strategy)

    batches: list[FocusContextBatch] = []
    current_files: dict[str, FileContextEntry] = {}
    current_chars = _estimate_related_chars(related_files) + _estimate_comment_chars(comment_context)
    batch_index = 1
    carry_excluded: list[ExcludedFileEntry] = []

    for file_plan in plan.focus_files:
        entry = _resolve_file_context(file_plan, diff, strategy, cwd, manager)
        entry_chars = entry.approximate_chars or _estimate_entry_chars(entry)

        if current_files and strategy.batching_enabled and current_chars + entry_chars > content_budget:
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
                    prompt_budget_target_chars=strategy.max_prompt_chars,
                )
            )
            batch_index += 1
            current_files = {}
            current_chars = _estimate_related_chars(related_files) + _estimate_comment_chars(comment_context)
            carry_excluded = []

        if not strategy.batching_enabled and current_files and current_chars + entry_chars > content_budget:
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
                prompt_budget_target_chars=strategy.max_prompt_chars,
            )
        )

    return ReviewContextPackage(batches=batches)


def _resolve_file_context(
    file_plan: FileReviewPlan,
    diff: str,
    strategy: ReviewStrategy,
    cwd: Optional[str] = None,
    diff_manager: Optional[DiffContextManager] = None,
) -> FileContextEntry:
    manager = diff_manager or DiffContextManager.from_diff(diff)
    desired_mode = file_plan.read_mode
    hunk_headers = [hunk.header for hunk in manager.get_hunks(file_plan.path)[:5]]
    file_limits = _file_limits(strategy, file_plan.path)

    if desired_mode == FileReadMode.FULL_FILE:
        content = read_file_content(file_plan.path, cwd)
        if content and len(content) <= file_limits["max_file_chars"] and len(content.splitlines()) <= file_limits["max_file_lines"]:
            return FileContextEntry(
                path=file_plan.path,
                read_mode=FileReadMode.FULL_FILE,
                full_content=content,
                changed_hunk_headers=hunk_headers,
                approximate_chars=len(content),
            )
        desired_mode = FileReadMode.EXPANDED_HUNKS

    if desired_mode == FileReadMode.EXPANDED_HUNKS:
        file_content = read_file_content(file_plan.path, cwd)
        expanded = (
            manager.build_expanded_hunks(
                file_plan.path,
                file_content,
                extra_lines=file_limits["extra_lines"],
            )
            if file_content
            else manager.get_hunk_texts(file_plan.path)
        )
        expanded_chars = sum(len(hunk) for hunk in expanded)
        if expanded and expanded_chars <= file_limits["max_file_chars"]:
            return FileContextEntry(
                path=file_plan.path,
                read_mode=FileReadMode.EXPANDED_HUNKS,
                expanded_hunks=expanded,
                changed_hunk_headers=hunk_headers,
                approximate_chars=expanded_chars,
            )
        desired_mode = FileReadMode.HUNKS_ONLY

    if desired_mode == FileReadMode.HUNKS_ONLY:
        hunks = manager.get_hunk_texts(file_plan.path)
        hunks_chars = sum(len(hunk) for hunk in hunks)
        if hunks and hunks_chars <= file_limits["max_file_chars"]:
            return FileContextEntry(
                path=file_plan.path,
                read_mode=FileReadMode.HUNKS_ONLY,
                hunks=hunks,
                changed_hunk_headers=hunk_headers,
                approximate_chars=hunks_chars,
            )

    return FileContextEntry(
        path=file_plan.path,
        read_mode=FileReadMode.WORKTREE_REFERENCE,
        worktree_reference=True,
        review_hint=_build_worktree_hint(file_plan),
        changed_hunk_headers=hunk_headers,
        approximate_chars=min(800, 80 + sum(len(header) for header in hunk_headers)),
    )


def _estimate_entry_chars(entry: FileContextEntry) -> int:
    if entry.full_content:
        return len(entry.full_content)
    if entry.expanded_hunks:
        return sum(len(hunk) for hunk in entry.expanded_hunks)
    if entry.hunks:
        return sum(len(hunk) for hunk in entry.hunks)
    if entry.worktree_reference:
        return 80 + len(entry.review_hint) + sum(len(header) for header in entry.changed_hunk_headers)
    return 0


def _content_budget(strategy: ReviewStrategy) -> int:
    reserve = 5000 if strategy.size_class.value in {"large", "huge"} else 3500
    return max(2500, strategy.max_prompt_chars - reserve)


def _file_limits(strategy: ReviewStrategy, path: str) -> dict[str, int]:
    is_large = strategy.size_class.value in {"large", "huge"}
    is_central = _looks_like_central_file(path)
    return {
        "max_file_chars": 12000 if is_central and is_large else 8000 if is_large else 14000,
        "max_file_lines": 220 if is_central and is_large else 140 if is_large else 260,
        "extra_lines": 8 if is_central else 5 if is_large else 8,
    }


def _looks_like_central_file(path: str) -> bool:
    path_lower = path.lower()
    return any(
        token in path_lower
        for token in (
            "viewmodel",
            "manager",
            "service",
            "utils",
            "mapper",
            "serializer",
            "adapter",
            "converter",
            "parser",
            "model",
        )
    )


def _build_worktree_hint(file_plan: FileReviewPlan) -> str:
    reasons = "; ".join(file_plan.reasons[:2]) if file_plan.reasons else "central changed file"
    return (
        "Read this file from the worktree. Prioritize the changed regions first and validate: "
        f"{reasons}. Check especially for semantic mismatches, missing guarantees, state inconsistencies, "
        "and behavior changes that remain executable but no longer mean the same thing."
    )


def _estimate_related_chars(related_files: dict[str, str]) -> int:
    return sum(len(label) + len(content[:2000]) for label, content in related_files.items())


def _estimate_comment_chars(comment_context: list[CommentContextEntry]) -> int:
    return sum(len(entry.title) + len(entry.summary) for entry in comment_context)
