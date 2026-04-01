"""
Operations for building cheap PR context (no AI involved).

Pure functions that transform UI models into review manifest and comment index.
All functions are deterministic and testable without mocks.
"""

import re
from typing import Optional

from ..models.review_models import (
    ChangeManifest,
    ChangedFileEntry,
    ExistingCommentIndexEntry,
    PullRequestManifest,
)
from ..models.view import UICommentThread, UIFileChange, UIPullRequest


# Patterns that identify test files by path
_TEST_PATH_PATTERNS: list[str] = [
    r"(^|/)tests?/",
    r"(^|/)test_",
    r"_test\.py$",
    r"_spec\.py$",
    r"(^|/)spec/",
    r"\.test\.[jt]sx?$",
    r"\.spec\.[jt]sx?$",
]

_TEST_REGEXES = [re.compile(p) for p in _TEST_PATH_PATTERNS]


def is_test_file(path: str) -> bool:
    """
    Heuristic check whether a file path is a test file.

    Args:
        path: File path relative to repo root

    Returns:
        True if the path looks like a test file
    """
    return any(rx.search(path) for rx in _TEST_REGEXES)


def build_change_manifest(
    pr: UIPullRequest,
    files: list[UIFileChange],
) -> ChangeManifest:
    """
    Build a ChangeManifest from PR UI models.

    Converts UIFileChange objects to ChangedFileEntry, identifies test files,
    and aggregates totals. No AI, no network calls — purely deterministic.

    Args:
        pr: Pull request UI model (UIPullRequest)
        files: List of changed files with stats (UIFileChange)

    Returns:
        ChangeManifest ready to be stored in ctx.data["change_manifest"]
    """
    entries: list[ChangedFileEntry] = []
    for f in files:
        entries.append(
            ChangedFileEntry(
                path=f.path,
                status=f.status,
                additions=f.additions,
                deletions=f.deletions,
                is_test=is_test_file(f.path),
                size_lines=0,  # Not available from UIFileChange; Phase 3 can enrich if needed
            )
        )

    total_additions = sum(f.additions for f in files)
    total_deletions = sum(f.deletions for f in files)

    pr_manifest = PullRequestManifest(
        number=pr.number,
        title=pr.title,
        base=pr.base_ref,
        head=pr.head_ref,
        author=pr.author_name,
        description=pr.body or "",
    )

    return ChangeManifest(
        pr=pr_manifest,
        files=entries,
        total_additions=total_additions,
        total_deletions=total_deletions,
    )


def _infer_category(body: str) -> Optional[str]:
    """
    Rough keyword-based heuristic to infer a comment category.

    Args:
        body: Comment body text

    Returns:
        Category string, or None if no category can be inferred
    """
    lower = body.lower()
    if any(k in lower for k in ("test", "coverage", "mock", "assert")):
        return "test_coverage"
    if any(k in lower for k in ("except", "error", "exception", "raise", "catch", "handle")):
        return "error_handling"
    if any(k in lower for k in ("security", "inject", "xss", "sql", "auth", "token", "secret")):
        return "security"
    if any(k in lower for k in ("performance", "slow", "n+1", "cache", "latency", "timeout")):
        return "performance"
    if any(k in lower for k in ("type", "annotation", "hint", "typing")):
        return "documentation"
    if any(k in lower for k in ("api", "contract", "schema", "interface", "endpoint")):
        return "api_contract"
    if any(k in lower for k in ("concurren", "thread", "async", "lock", "race")):
        return "concurrency"
    if any(k in lower for k in ("logic", "bug", "incorrect", "wrong", "broken", "broken")):
        return "functional_correctness"
    return None


def build_existing_comments_index(
    review_threads: list[UICommentThread],
    general_comments: list[UICommentThread],
) -> list[ExistingCommentIndexEntry]:
    """
    Build a compact index of existing PR comments for deduplication and AI context.

    Processes both inline review threads and general PR-level comments into a flat,
    lightweight list. Each entry contains only what's needed for deduplication:
    file path, line, category (inferred), and a short title.

    Args:
        review_threads: Inline review threads (from get_pr_review_threads)
        general_comments: General PR comments (from get_pr_general_comments)

    Returns:
        List of ExistingCommentIndexEntry, one per comment (not per thread)
    """
    index: list[ExistingCommentIndexEntry] = []

    for thread in review_threads:
        mc = thread.main_comment
        entry = ExistingCommentIndexEntry(
            comment_id=mc.id,
            thread_id=thread.thread_id,
            is_resolved=thread.is_resolved,
            path=mc.path,
            line=mc.line,
            category=_infer_category(mc.body),
            title=mc.body[:50].strip(),
            author=mc.author_login,
        )
        index.append(entry)

        # Include replies too — they may add context that prevents duplicate suggestions
        for reply in thread.replies:
            index.append(
                ExistingCommentIndexEntry(
                    comment_id=reply.id,
                    thread_id=thread.thread_id,
                    is_resolved=thread.is_resolved,
                    path=reply.path or mc.path,
                    line=reply.line or mc.line,
                    category=_infer_category(reply.body),
                    title=reply.body[:50].strip(),
                    author=reply.author_login,
                )
            )

    for gc in general_comments:
        mc = gc.main_comment
        index.append(
            ExistingCommentIndexEntry(
                comment_id=mc.id,
                thread_id=gc.thread_id,
                is_resolved=gc.is_resolved,
                path=None,  # General comments have no file path
                line=None,
                category=_infer_category(mc.body),
                title=mc.body[:50].strip(),
                author=mc.author_login,
            )
        )

    return index
