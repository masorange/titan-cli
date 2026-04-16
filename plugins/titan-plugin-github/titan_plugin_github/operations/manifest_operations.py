"""Operations for building cheap PR context and compact comments context."""

import re
from pathlib import Path
from typing import Optional

from ..models.review_enums import CommentContextKind
from ..models.review_models import (
    ChangeManifest,
    ChangedFileEntry,
    CommentContextEntry,
    ExistingCommentIndexEntry,
    PullRequestManifest,
)
from ..models.view import UICommentThread, UIFileChange, UIPullRequest


_TEST_PATH_PATTERNS = [
    r"(^|/)tests?/",
    r"(^|/)test_",
    r"_test\.py$",
    r"_spec\.py$",
    r"(^|/)spec/",
    r"\.test\.[jt]sx?$",
    r"\.spec\.[jt]sx?$",
]
_DOC_PATH_PATTERNS = [r"(^|/)docs?/", r"\.md$", r"\.rst$", r"\.adoc$"]
_GENERATED_PATH_PATTERNS = [r"(^|/)dist/", r"(^|/)build/", r"(^|/)vendor/", r"(^|/)generated/"]
_CONFIG_SUFFIXES = {
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".json",
    ".gradle",
    ".kts",
    ".plist",
    ".pbxproj",
}
_LOCKFILE_NAMES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "pdm.lock",
    "cargo.lock",
    "composer.lock",
    "gemfile.lock",
    "podfile.lock",
    "packages.resolved",
    "package.resolved",
    "paket.lock",
    "pubspec.lock",
}

_TEST_REGEXES = [re.compile(p) for p in _TEST_PATH_PATTERNS]
_DOC_REGEXES = [re.compile(p) for p in _DOC_PATH_PATTERNS]
_GENERATED_REGEXES = [re.compile(p) for p in _GENERATED_PATH_PATTERNS]


def is_test_file(path: str) -> bool:
    return any(rx.search(path) for rx in _TEST_REGEXES)


def is_docs_file(path: str) -> bool:
    return any(rx.search(path) for rx in _DOC_REGEXES)


def is_generated_file(path: str) -> bool:
    return any(rx.search(path) for rx in _GENERATED_REGEXES)


def is_config_file(path: str) -> bool:
    p = Path(path)
    name = p.name.lower()
    return (
        p.suffix.lower() in _CONFIG_SUFFIXES
        or p.name.startswith(".")
        or name.startswith(("dockerfile", "makefile", "podfile", "fastfile"))
        or name.endswith((".gradle.kts", ".xcconfig"))
    )


def is_lockfile(path: str) -> bool:
    return Path(path).name.lower() in _LOCKFILE_NAMES


def is_rename_only(file_change: UIFileChange) -> bool:
    return file_change.status.value == "renamed" and file_change.additions == 0 and file_change.deletions == 0


def build_change_manifest(pr: UIPullRequest, files: list[UIFileChange]) -> ChangeManifest:
    entries: list[ChangedFileEntry] = []
    for f in files:
        entries.append(
            ChangedFileEntry(
                path=f.path,
                status=f.status,
                additions=f.additions,
                deletions=f.deletions,
                is_test=is_test_file(f.path),
                size_lines=0,
                is_docs=is_docs_file(f.path),
                is_generated=is_generated_file(f.path),
                is_config=is_config_file(f.path),
                is_lockfile=is_lockfile(f.path),
                is_rename_only=is_rename_only(f),
            )
        )

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
        total_additions=sum(f.additions for f in files),
        total_deletions=sum(f.deletions for f in files),
    )


def _infer_category(body: str) -> Optional[str]:
    lower = body.lower()
    if any(k in lower for k in ("test", "coverage", "mock", "assert")):
        return "test_coverage"
    if any(k in lower for k in ("except", "error", "exception", "raise", "catch", "handle")):
        return "error_handling"
    if any(k in lower for k in ("security", "inject", "xss", "sql", "auth", "token", "secret")):
        return "security"
    if any(k in lower for k in ("performance", "slow", "n+1", "cache", "latency", "timeout")):
        return "performance"
    if any(k in lower for k in ("api", "contract", "schema", "interface", "endpoint")):
        return "api_contract"
    if any(k in lower for k in ("concurren", "thread", "async", "lock", "race")):
        return "concurrency"
    if any(k in lower for k in ("logic", "bug", "incorrect", "wrong", "broken")):
        return "functional_correctness"
    if any(k in lower for k in ("validate", "validation", "sanitize", "nullable", "none")):
        return "data_validation"
    return None


def build_existing_comments_index(
    review_threads: list[UICommentThread],
    general_comments: list[UICommentThread],
) -> list[ExistingCommentIndexEntry]:
    index: list[ExistingCommentIndexEntry] = []

    for thread in review_threads:
        mc = thread.main_comment
        index.append(
            ExistingCommentIndexEntry(
                comment_id=mc.id,
                thread_id=thread.thread_id,
                is_resolved=thread.is_resolved,
                path=mc.path,
                line=mc.line,
                category=_infer_category(mc.body),
                title=mc.body[:80].strip(),
                author=mc.author_login,
            )
        )
        for reply in thread.replies:
            index.append(
                ExistingCommentIndexEntry(
                    comment_id=reply.id,
                    thread_id=thread.thread_id,
                    is_resolved=thread.is_resolved,
                    path=reply.path or mc.path,
                    line=reply.line or mc.line,
                    category=_infer_category(reply.body),
                    title=reply.body[:80].strip(),
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
                path=None,
                line=None,
                category=_infer_category(mc.body),
                title=mc.body[:80].strip(),
                author=mc.author_login,
            )
        )

    return index


def build_comment_review_context(
    review_threads: list[UICommentThread],
    general_comments: list[UICommentThread],
    max_entries: int = 12,
    max_chars: int = 2400,
) -> list[CommentContextEntry]:
    """Build prompt-friendly comment context with thread summaries when needed."""

    def make_thread_entry(thread: UICommentThread) -> CommentContextEntry:
        main = thread.main_comment
        if thread.replies:
            latest = thread.replies[-1]
            latest_state = latest.body.strip().replace("\n", " ")[:180]
            summary = (
                f"Initial: {main.body.strip().replace(chr(10), ' ')[:180]}. "
                f"Latest reply by @{latest.author_login}: {latest_state}"
            )
            kind = CommentContextKind.THREAD_SUMMARY
        else:
            summary = main.body.strip().replace("\n", " ")[:220]
            kind = CommentContextKind.COMMENT
        return CommentContextEntry(
            kind=kind,
            thread_id=thread.thread_id,
            path=main.path,
            line=main.line,
            category=_infer_category(main.body),
            title=main.body[:80].strip(),
            summary=summary,
            is_resolved=thread.is_resolved,
        )

    prioritized_threads = sorted(
        review_threads,
        key=lambda t: (
            t.is_resolved,
            t.is_general_comment,
            0 if t.main_comment.path else 1,
            -len(t.replies),
        ),
    )
    entries = [make_thread_entry(thread) for thread in prioritized_threads]

    for general in general_comments:
        main = general.main_comment
        entries.append(
            CommentContextEntry(
                kind=CommentContextKind.COMMENT,
                thread_id=general.thread_id,
                path=None,
                line=None,
                category=_infer_category(main.body),
                title=main.body[:80].strip(),
                summary=main.body.strip().replace("\n", " ")[:220],
                is_resolved=general.is_resolved,
            )
        )

    result: list[CommentContextEntry] = []
    used_chars = 0
    for entry in entries:
        if len(result) >= max_entries:
            break
        entry_size = len(entry.title) + len(entry.summary)
        if result and used_chars + entry_size > max_chars:
            break
        result.append(entry)
        used_chars += entry_size

    return result
