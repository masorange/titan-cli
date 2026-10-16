from titan_plugin_github.models.review_enums import FileChangeStatus
from titan_plugin_github.models.view import UIFileChange
from titan_plugin_github.models.review_models import ExistingCommentIndexEntry, Finding
from titan_plugin_github.models.review_enums import FindingSeverity
from titan_plugin_github.models.validators import is_duplicate
from titan_plugin_github.models.view import UIComment, UICommentThread
from titan_plugin_github.operations.manifest_operations import (
    build_change_manifest,
    build_existing_comments_index,
    is_test_file,
)


def test_build_change_manifest_sets_generic_flags(sample_ui_pr):
    files = [
        UIFileChange(
            path="android/app/build.gradle.kts",
            additions=4,
            deletions=1,
            status=FileChangeStatus.MODIFIED,
            status_icon="~",
        ),
        UIFileChange(
            path="ios/Podfile.lock",
            additions=8,
            deletions=2,
            status=FileChangeStatus.MODIFIED,
            status_icon="~",
        ),
        UIFileChange(
            path="docs/architecture.md",
            additions=12,
            deletions=0,
            status=FileChangeStatus.MODIFIED,
            status_icon="~",
        ),
    ]

    manifest = build_change_manifest(sample_ui_pr, files)

    assert manifest.files[0].is_config is True
    assert manifest.files[1].is_lockfile is True
    assert manifest.files[2].is_docs is True


def test_is_test_file_covers_multi_language_conventions():
    test_paths = [
        "app/src/test/kotlin/com/foo/FooViewModelTest.kt",
        "app/src/androidTest/kotlin/com/foo/FooScreenTest.kt",
        "src/main/java/com/foo/FooServiceTests.java",
        "Sources/FooTests/FooTest.swift",
        "pkg/server/handler_test.go",
        "src/FooSpec.scala",
        "tests/test_api.py",
        "src/components/Button.test.tsx",
    ]
    for path in test_paths:
        assert is_test_file(path), path


def test_is_test_file_does_not_claim_production_lookalikes():
    production_paths = [
        "src/latest.py",
        "app/contest/views.py",
        "lib/attestation.py",
        "src/protest_handler.py",
        "app/src/main/kotlin/com/foo/Latest.kt",
        "src/detestable_module.py",
    ]
    for path in production_paths:
        assert not is_test_file(path), path


def test_build_change_manifest_uses_local_churn_for_zeroed_counters(sample_ui_pr):
    """GitHub reports 0/0 for files whose diff it cannot render; the local numstat
    counters must take over exactly there — never on files with real API counters
    and never on pure renames (0/0 IS their real churn)."""
    files = [
        UIFileChange(
            path="src/huge_generated_client.py",
            additions=0,
            deletions=0,
            status=FileChangeStatus.ADDED,
            status_icon="+",
        ),
        UIFileChange(
            path="src/normal.py",
            additions=10,
            deletions=2,
            status=FileChangeStatus.MODIFIED,
            status_icon="~",
        ),
        UIFileChange(
            path="src/renamed.py",
            additions=0,
            deletions=0,
            status=FileChangeStatus.RENAMED,
            status_icon="→",
        ),
    ]
    churn = {
        "src/huge_generated_client.py": (1500, 0),
        "src/normal.py": (11, 3),
        "src/renamed.py": (200, 0),
    }

    manifest = build_change_manifest(sample_ui_pr, files, churn_by_path=churn)

    by_path = {entry.path: entry for entry in manifest.files}
    assert by_path["src/huge_generated_client.py"].additions == 1500
    assert by_path["src/normal.py"].additions == 10  # API counters win when present
    assert by_path["src/renamed.py"].additions == 0  # pure rename untouched
    assert manifest.total_additions == 1500 + 10 + 0


def test_is_duplicate_matches_adjudicated_resolved_thread_when_titles_are_similar():
    finding = Finding(
        severity=FindingSeverity.IMPORTANT,
        category="functional_correctness",
        path="src/api.py",
        line=10,
        title="Serializer drops non-string analytics values",
        why="Why",
        evidence="bundle.getString(k)",
        suggested_comment="Comment",
    )
    existing = ExistingCommentIndexEntry(
        comment_id=1,
        thread_id="t3",
        is_resolved=True,
        path="src/api.py",
        line=10,
        category="functional_correctness",
        title="This change may lose non-string analytics values",
        author="reviewer",
        has_author_reply=True,
        last_reply_author="author",
        reply_count=1,
        is_adjudicated=True,
    )

    assert is_duplicate(finding, existing) is True


def test_is_duplicate_does_not_suppress_different_adjudicated_issue_same_category():
    finding = Finding(
        severity=FindingSeverity.IMPORTANT,
        category="performance",
        path="src/api.py",
        line=10,
        title="Repeated JSON parsing inside render loop",
        why="Why",
        evidence="parseJson() in loop",
        suggested_comment="Comment",
    )
    existing = ExistingCommentIndexEntry(
        comment_id=1,
        thread_id="t3",
        is_resolved=True,
        path="src/api.py",
        line=10,
        category="performance",
        title="Rename temporary variable for clarity",
        author="reviewer",
        has_author_reply=True,
        last_reply_author="author",
        reply_count=1,
        is_adjudicated=True,
    )

    assert is_duplicate(finding, existing) is False


def test_is_duplicate_returns_false_for_different_paths():
    finding = Finding(
        severity=FindingSeverity.IMPORTANT,
        category="functional_correctness",
        path="src/api.py",
        line=10,
        title="Serializer drops non-string analytics values",
        why="Why",
        evidence="bundle.getString(k)",
        suggested_comment="Comment",
    )
    existing = ExistingCommentIndexEntry(
        comment_id=1,
        thread_id="t3",
        is_resolved=True,
        path="src/different_api.py",
        line=10,
        category="functional_correctness",
        title="This change may lose non-string analytics values",
        author="reviewer",
        has_author_reply=True,
        last_reply_author="author",
        reply_count=1,
        is_adjudicated=True,
    )

    assert is_duplicate(finding, existing) is False


def test_is_duplicate_returns_false_for_different_lines():
    finding = Finding(
        severity=FindingSeverity.IMPORTANT,
        category="functional_correctness",
        path="src/api.py",
        line=10,
        title="Serializer drops non-string analytics values",
        why="Why",
        evidence="bundle.getString(k)",
        suggested_comment="Comment",
    )
    existing = ExistingCommentIndexEntry(
        comment_id=1,
        thread_id="t3",
        is_resolved=True,
        path="src/api.py",
        line=20,
        category="functional_correctness",
        title="This change may lose non-string analytics values",
        author="reviewer",
        has_author_reply=True,
        last_reply_author="author",
        reply_count=1,
        is_adjudicated=True,
    )

    assert is_duplicate(finding, existing) is False


def test_is_duplicate_returns_false_if_not_adjudicated_and_dissimilar():
    finding = Finding(
        severity=FindingSeverity.IMPORTANT,
        category="functional_correctness",
        path="src/api.py",
        line=10,
        title="Serializer drops non-string analytics values",
        why="Why",
        evidence="bundle.getString(k)",
        suggested_comment="Comment",
    )
    existing = ExistingCommentIndexEntry(
        comment_id=1,
        thread_id="t3",
        is_resolved=True,
        path="src/api.py",
        line=10,
        category="functional_correctness",
        title="Completely different title",
        author="reviewer",
        has_author_reply=True,
        last_reply_author="author",
        reply_count=1,
        is_adjudicated=False,
    )

    assert is_duplicate(finding, existing, title_similarity_threshold=0.9) is False


def _index_entry(**overrides):
    base = dict(comment_id=9, thread_id="t9", is_resolved=False, path="ui/DeviceDetailScreen.kt",
                line=116, category="error_handling", author="reviewer")
    base.update(overrides)
    base.setdefault("title", base.get("body", "")[:80])
    return ExistingCommentIndexEntry(**base)


def test_a_shared_category_near_a_comment_is_not_a_duplicate_by_itself():
    """Measured on ragnarok PR #3685: this real, new finding was dropped because a human
    comment five lines away was guessed `error_handling` for containing "handling"."""
    finding = Finding(
        severity=FindingSeverity.IMPORTANT, category="error_handling", path="ui/DeviceDetailScreen.kt",
        line=111, title='Checkout "Retry" button only dismisses the error, it never retries checkout',
        why="onCheckoutErrorRetryClick only resets hasCheckoutError; the checkout request is not issued again.",
        evidence="onCheckoutErrorRetryClick = { hasCheckoutError = false }", suggested_comment="c",
    )
    comment = _index_entry(body="Shouldn't this be handling the case when there's no `checkoutUrl`?")

    assert is_duplicate(finding, comment) is False


def test_a_nearby_comment_that_says_the_same_thing_is_a_duplicate():
    finding = Finding(
        severity=FindingSeverity.IMPORTANT, category="error_handling", path="ui/DeviceDetailScreen.kt",
        line=111, title="Retry button does not retry the checkout request",
        why="The retry handler only hides the error screen.", evidence="e", suggested_comment="c",
    )
    comment = _index_entry(body="The retry button here only hides the error, it should retry the checkout request.")

    assert is_duplicate(finding, comment) is True


def test_a_comment_on_the_very_same_line_needs_less_overlap_to_be_the_same_finding():
    """Ragnarok #3723 re-reported two findings already commented on the exact line they
    anchor to (overlaps 0.29 and 0.39), because the comments' guessed category differed."""
    finding = Finding(
        severity=FindingSeverity.IMPORTANT, category="correctness", path="ui/UpgradeViewModel.kt",
        line=187, title="Upgrade offers are sorted most expensive first, against the doc",
        why="The business doc says offers are sorted by netAmount ascending; the code sorts descending.",
        evidence="sortedByDescending { it.price.total.netAmount }", suggested_comment="c",
    )
    comment = _index_entry(
        path="ui/UpgradeViewModel.kt", line=187, category="maintainability",
        body="The business doc added in this PR and the previous implementation both sort offers "
        "by price ascending, but this sorts descending and the test asserts it.",
    )

    assert is_duplicate(finding, comment) is True
    # Five lines away the stricter rules still apply.
    assert is_duplicate(finding, comment.model_copy(update={"line": 182})) is False


def test_the_same_line_does_not_make_an_unrelated_comment_a_duplicate():
    """The #3685 pair, moved onto the same line: nothing in common, still two findings."""
    finding = Finding(
        severity=FindingSeverity.IMPORTANT, category="error_handling", path="ui/DeviceDetailScreen.kt",
        line=116, title='Checkout "Retry" button only dismisses the error, it never retries checkout',
        why="onCheckoutErrorRetryClick only resets hasCheckoutError; the checkout request is not issued again.",
        evidence="e", suggested_comment="c",
    )
    comment = _index_entry(body="Shouldn't this be handling the case when there's no `checkoutUrl`?")

    assert is_duplicate(finding, comment) is False


def _finding(path, line, title, why):
    return Finding(
        severity=FindingSeverity.IMPORTANT,
        category="review",
        path=path,
        line=line,
        title=title,
        why=why,
        evidence="",
        suggested_comment=why,
    )


def _comment(path, line, body, *, bot=False):
    return ExistingCommentIndexEntry(
        comment_id=1,
        thread_id="t",
        is_resolved=False,
        path=path,
        line=line,
        title=body[:80],
        body=body,
        author="scanner[bot]" if bot else "reviewer",
        is_bot=bot,
    )


# The next four are the real comments and findings of ragnarok PR #3735, where the same
# defects were posted twice because they sat a few lines apart or came from a scanner.


def test_the_same_defect_reported_at_its_declaration_and_at_its_comparison_is_one_defect():
    finding = _finding(
        "fastlane/Fastfile",
        124,
        "Type mismatch in version comparison",
        "previous_version_code (String) is compared with new_version_code (Integer), so it is always false.",
    )
    existing = _comment(
        "fastlane/Fastfile",
        132,
        "`previous_version_code` comes from `sh(...).strip` (String) while `new_version_code` "
        "is an Integer returned by the action, so `==` is always false.",
    )

    assert is_duplicate(finding, existing) is True


def test_a_finding_naming_the_same_identifier_a_few_lines_off_in_the_same_file_is_a_duplicate():
    finding = _finding(
        "app/build.gradle.kts",
        878,
        "Resource leak from unclosed input stream",
        "versionPropsFile.inputStream() is never closed; use .use{}.",
    )
    existing = _comment(
        "app/build.gradle.kts",
        873,
        "`versionProps.load(versionPropsFile.inputStream())` never closes the stream; use "
        "`.inputStream().use { versionProps.load(it) }`.",
    )

    assert is_duplicate(finding, existing) is True


def test_sharing_an_identifier_is_not_enough_when_the_two_are_about_different_things():
    finding = _finding(
        "plugin/template_operations.py",
        120,
        "apply_change drops the condition of a copied value",
        "The conditional branch is discarded when the key already exists.",
    )
    existing = _comment(
        "plugin/template_operations.py",
        110,
        "Rename apply_change to something shorter, the current name hides what it does.",
    )

    assert is_duplicate(finding, existing) is False


def test_a_finding_far_from_a_comment_stays_new_even_if_it_names_the_same_identifier():
    finding = _finding("a.py", 400, "version_file leaks", "version_file is never closed after reading.")
    existing = _comment("a.py", 20, "version_file is read without validation, version_file may escape.")

    assert is_duplicate(finding, existing) is False


def test_a_finding_on_the_very_line_a_scanner_flagged_is_the_scanners_finding():
    finding = _finding(
        "fastlane/actions/increment_version.rb",
        23,
        "Potential path traversal vulnerability",
        "version_file comes from params and is read without validation, so a path traversal is possible.",
    )
    scanner = _comment(
        "fastlane/actions/increment_version.rb",
        23,
        "SAST Finding Tainted File Access (CWE-22) This rule detects instances where user "
        "input is used to access files, which can lead to path traversal vulnerabilities. "
        "Path traversal vulnerabilities allow an attacker to access files outside the intended "
        "directory. When user input is used to construct file paths without proper validation "
        "and sanitization, an attacker can craft malicious input that traverses the file system.",
        bot=True,
    )

    assert is_duplicate(finding, scanner) is True


def test_a_scanner_comment_does_not_swallow_a_finding_on_another_line():
    finding = _finding(
        "app/build.gradle.kts",
        90,
        "Path traversal when reading the version file",
        "The path of the version file is read without validation.",
    )
    scanner = _comment("app/build.gradle.kts", 78, "Tainted File Access path traversal", bot=True)

    assert is_duplicate(finding, scanner) is False


def test_the_index_keeps_a_scanners_inline_comment_without_its_markup_and_drops_its_summaries():
    def comment(author, body, path=None, line=None):
        return UIComment(
            id=1, body=body, author_login=author, author_name=author,
            formatted_date="01/10/2026 10:00:00", path=path, line=line,
        )

    inline_bot = UICommentThread(
        thread_id="t1",
        main_comment=comment(
            "wiz[bot]",
            '<a><picture><img alt="Medium"></picture></a> **Tainted File Access** (CWE-22)',
            "a.rb",
            23,
        ),
        replies=[], is_resolved=False, is_outdated=False,
    )
    summary_bot = UICommentThread(
        thread_id="g1",
        main_comment=comment("danger[bot]", "<table><tr><td>1 Warning</td></tr></table>"),
        replies=[], is_resolved=False, is_outdated=False,
    )

    index = build_existing_comments_index([inline_bot], [summary_bot])

    assert [(entry.path, entry.line, entry.is_bot) for entry in index] == [("a.rb", 23, True)]
    assert "<" not in index[0].body
    assert "Tainted File Access" in index[0].body

