"""Operations for building cheap PR context and the index of existing comments."""

import re
from pathlib import Path
from typing import Optional

from ..models.review_models import (
    ChangeManifest,
    ChangedFileEntry,
    ExistingCommentIndexEntry,
    PullRequestManifest,
)
from ..models.view import UICommentThread, UIFileChange, UIPullRequest


_TEST_PATH_PATTERNS = [
    r"(^|/)tests?/",
    r"(^|/)[a-z]+Tests?/",
    r"(^|/)__tests__/",
    r"(^|/)test_",
    r"_(test|spec)\.(py|rb|rs|dart|exs?|go)$",
    r"(^|/)spec/",
    r"\.(test|spec)\.[cm]?[jt]sx?$",
    r"Tests?\.(kt|java|cs|swift|scala|php)$",
    r"Spec\.(kt|scala|groovy)$",
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

# Images, fonts and translatable text. What changed in them is the whole diff: a string
# reworded, a drawable recoloured. No code around them can hide a defect, so they are
# never worth a deep read -- and a project role such as `**/res/**` under UI must not be
# able to send them there.
_STATIC_RESOURCE_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff", ".heic", ".avif",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    ".strings", ".stringsdict", ".xcstrings",
    ".po", ".pot", ".arb", ".resx", ".xliff", ".xlf",
}
_STATIC_RESOURCE_PATH_PATTERNS = [
    r"(^|/)res/(drawable|mipmap)[^/]*/",
    r"(^|/)res/values[^/]*/(strings|plurals)\.xml$",
    r"\.xcassets/",
    r"(^|/)(locales?|i18n|l10n|translations)/.+\.(json|ya?ml|properties)$",
]

_TEST_REGEXES = [re.compile(p) for p in _TEST_PATH_PATTERNS]
_DOC_REGEXES = [re.compile(p) for p in _DOC_PATH_PATTERNS]
_GENERATED_REGEXES = [re.compile(p) for p in _GENERATED_PATH_PATTERNS]
_STATIC_RESOURCE_REGEXES = [re.compile(p) for p in _STATIC_RESOURCE_PATH_PATTERNS]


def is_test_file(path: str) -> bool:
    """Detect test files by the built-in conventions of the common languages."""
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


def is_static_resource(path: str) -> bool:
    """Image, font or translatable text: a file whose diff is all there is to judge."""
    if Path(path).suffix.lower() in _STATIC_RESOURCE_SUFFIXES:
        return True
    return any(rx.search(path) for rx in _STATIC_RESOURCE_REGEXES)


def is_rename_only(file_change: UIFileChange) -> bool:
    return file_change.status.value == "renamed" and file_change.additions == 0 and file_change.deletions == 0


def build_change_manifest(
    pr: UIPullRequest,
    files: list[UIFileChange],
    churn_by_path: Optional[dict[str, tuple[int, int]]] = None,
) -> ChangeManifest:
    """Build the typed manifest of a PR's changed files.

    ``churn_by_path`` maps path -> (additions, deletions) from a local git numstat.
    GitHub's files API reports 0/0 for files whose diff it cannot render (too
    large or binary); a zero entry here would score as "nothing changed", so the
    local counters take over exactly in that case and only in that case.
    """
    churn_by_path = churn_by_path or {}
    entries: list[ChangedFileEntry] = []
    for f in files:
        additions, deletions = f.additions, f.deletions
        # A pure rename also reports 0/0, but that IS the real churn — and the
        # numstat source uses --no-renames, which would report the new path as a
        # full-file addition. Never override renames.
        if additions == 0 and deletions == 0 and not is_rename_only(f) and f.path in churn_by_path:
            additions, deletions = churn_by_path[f.path]
        entries.append(
            ChangedFileEntry(
                path=f.path,
                previous_path=f.previous_path,
                status=f.status,
                additions=additions,
                deletions=deletions,
                is_test=is_test_file(f.path),
                size_lines=0,
                is_docs=is_docs_file(f.path),
                is_generated=is_generated_file(f.path),
                is_config=is_config_file(f.path),
                is_lockfile=is_lockfile(f.path),
                is_static_resource=is_static_resource(f.path),
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
        total_additions=sum(entry.additions for entry in entries),
        total_deletions=sum(entry.deletions for entry in entries),
    )


# Enough of a comment to tell what it is about; dedupe compares a finding against this.
_INDEXED_BODY_CHARS = 1500


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


def _looks_like_automated_comment(author_login: str, body: str) -> bool:
    lower_author = (author_login or "").lower()
    lower_body = body.lower()
    if any(token in lower_author for token in ("[bot]", "bot", "danger", "codecov", "sonar", "copilot")):
        return True
    if lower_body.startswith("<!--"):
        return True
    if any(token in lower_body for token in ("<table", "<picture", "<source", "<img", "</table>", "</picture>")):
        return True
    if any(
        token in lower_body
        for token in (
            "warnings:",
            "markdowns -->",
            "coverage report",
            "generated by danger",
            "wiz.io",
            "assets.wiz.io",
            "severity_tags",
            "security issues found",
            "vulnerability",
        )
    ):
        return True
    return False


def _plain_text(body: str) -> str:
    """A comment's text without its HTML (scanner comments are mostly markup)."""
    return " ".join(re.sub(r"<[^>]+>", " ", body or "").split())


def _has_author_reply(thread: UICommentThread) -> bool:
    main_author = (thread.main_comment.author_login or "").lower()
    return any((reply.author_login or "").lower() != main_author for reply in thread.replies)


def _last_reply_author(thread: UICommentThread) -> Optional[str]:
    if not thread.replies:
        return None
    return thread.replies[-1].author_login


def _is_adjudicated_thread(thread: UICommentThread) -> bool:
    return thread.is_resolved and _has_author_reply(thread)


def build_existing_comments_index(
    review_threads: list[UICommentThread],
    general_comments: list[UICommentThread],
) -> list[ExistingCommentIndexEntry]:
    index: list[ExistingCommentIndexEntry] = []

    for thread in review_threads:
        mc = thread.main_comment
        if _looks_like_automated_comment(mc.author_login, mc.body):
            # A scanner's comment on a line is indexed so a finding about the same line is
            # not posted twice; its summary comments (general, replies) are not.
            if mc.path and mc.line:
                text = _plain_text(mc.body)
                index.append(
                    ExistingCommentIndexEntry(
                        comment_id=mc.id,
                        thread_id=thread.thread_id,
                        is_resolved=thread.is_resolved,
                        path=mc.path,
                        line=mc.line,
                        title=text[:80],
                        body=text[:_INDEXED_BODY_CHARS],
                        author=mc.author_login,
                        is_bot=True,
                    )
                )
            continue
        index.append(
            ExistingCommentIndexEntry(
                comment_id=mc.id,
                thread_id=thread.thread_id,
                is_resolved=thread.is_resolved,
                path=mc.path,
                line=mc.line,
                category=_infer_category(mc.body),
                title=mc.body[:80].strip(),
                body=mc.body[:_INDEXED_BODY_CHARS],
                author=mc.author_login,
                has_author_reply=_has_author_reply(thread),
                last_reply_author=_last_reply_author(thread),
                reply_count=len(thread.replies),
                is_adjudicated=_is_adjudicated_thread(thread),
            )
        )
        for reply in thread.replies:
            if _looks_like_automated_comment(reply.author_login, reply.body):
                continue
            index.append(
                ExistingCommentIndexEntry(
                    comment_id=reply.id,
                    thread_id=thread.thread_id,
                    is_resolved=thread.is_resolved,
                    path=reply.path or mc.path,
                    line=reply.line or mc.line,
                    category=_infer_category(reply.body),
                    title=reply.body[:80].strip(),
                    body=reply.body[:_INDEXED_BODY_CHARS],
                    author=reply.author_login,
                    has_author_reply=_has_author_reply(thread),
                    last_reply_author=_last_reply_author(thread),
                    reply_count=len(thread.replies),
                    is_adjudicated=_is_adjudicated_thread(thread),
                )
            )

    for gc in general_comments:
        mc = gc.main_comment
        if _looks_like_automated_comment(mc.author_login, mc.body):
            continue
        index.append(
            ExistingCommentIndexEntry(
                comment_id=mc.id,
                thread_id=gc.thread_id,
                is_resolved=gc.is_resolved,
                path=None,
                line=None,
                category=_infer_category(mc.body),
                title=mc.body[:80].strip(),
                body=mc.body[:_INDEXED_BODY_CHARS],
                author=mc.author_login,
                has_author_reply=_has_author_reply(gc),
                last_reply_author=_last_reply_author(gc),
                reply_count=len(gc.replies),
                is_adjudicated=_is_adjudicated_thread(gc),
            )
        )

    return index
