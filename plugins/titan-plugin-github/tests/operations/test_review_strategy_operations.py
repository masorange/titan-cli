from titan_plugin_github.models.review_enums import ExclusionReason, PRSizeClass, ReviewStrategyType
from titan_plugin_github.models.review_models import ChangeManifest, ChangedFileEntry, PullRequestManifest
from titan_plugin_github.operations.review_strategy_operations import (
    build_deterministic_review_plan,
    classify_pr,
    score_review_candidates,
    select_review_strategy,
)


def make_manifest(files: list[ChangedFileEntry]) -> ChangeManifest:
    return ChangeManifest(
        pr=PullRequestManifest(
            number=1,
            title="Test PR",
            base="main",
            head="feat/test",
            author="alex",
            description="Body",
        ),
        files=files,
        total_additions=sum(file.additions for file in files),
        total_deletions=sum(file.deletions for file in files),
    )


def test_classify_pr_large_thresholds():
    manifest = make_manifest(
        [
            ChangedFileEntry(path=f"src/file_{idx}.py", status="modified", additions=40, deletions=10)
            for idx in range(25)
        ]
    )

    classification = classify_pr(manifest, comment_entries=12, comment_threads=4)

    assert classification.size_class == PRSizeClass.LARGE
    assert classification.comment_entries == 12
    assert classification.comment_threads == 4


def test_score_review_candidates_excludes_low_value_files():
    manifest = make_manifest(
        [
            ChangedFileEntry(path="docs/readme.md", status="modified", additions=5, deletions=0, is_docs=True),
            ChangedFileEntry(path="ios/Podfile.lock", status="modified", additions=10, deletions=1, is_lockfile=True),
            ChangedFileEntry(path="app/store/user_store.py", status="modified", additions=60, deletions=12),
        ]
    )

    candidates, excluded = score_review_candidates(manifest)

    assert [candidate.path for candidate in candidates] == ["app/store/user_store.py"]
    assert {item.reason for item in excluded} == {ExclusionReason.DOCS, ExclusionReason.LOCKFILE}


def test_deterministic_plan_respects_focus_limit(sample_ui_pr):
    manifest = make_manifest(
        [
            ChangedFileEntry(path=f"src/controller_{idx}.py", status="modified", additions=30, deletions=8)
            for idx in range(6)
        ]
    )
    candidates, excluded = score_review_candidates(manifest)
    strategy = select_review_strategy(classify_pr(manifest))

    plan = build_deterministic_review_plan(candidates, excluded, [], strategy)

    assert strategy.strategy == ReviewStrategyType.DIRECT_FINDINGS
    assert len(plan.focus_files) == strategy.max_focus_files
    assert len(plan.excluded_files) == len(excluded) + max(0, len(candidates) - strategy.max_focus_files)
