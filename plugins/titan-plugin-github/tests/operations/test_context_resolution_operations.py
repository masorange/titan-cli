from titan_plugin_github.models.review_enums import (
    ChecklistCategory,
    FileReadMode,
    FileReviewPriority,
    PRSizeClass,
    ReviewStrategyType,
)
from titan_plugin_github.models.review_models import (
    ChangeManifest,
    FileContextEntry,
    FileReviewPlan,
    PullRequestManifest,
    ReviewChecklistItem,
    ReviewPlan,
    ReviewStrategy,
)
from titan_plugin_github.operations import context_resolution_operations


def test_build_review_context_package_uses_prompt_budget_manager(monkeypatch):
    called = {"budget": 0}

    class _FakePromptBudgetManager:
        def content_budget_for_strategy(self, strategy):
            called["budget"] += 1
            assert strategy.max_prompt_chars == 22000
            return 50000

    monkeypatch.setattr(context_resolution_operations, "PromptBudgetManager", _FakePromptBudgetManager)
    monkeypatch.setattr(context_resolution_operations, "resolve_context_requests", lambda _requests, _cwd=None: {})
    monkeypatch.setattr(
        context_resolution_operations,
        "_resolve_file_context",
        lambda _file_plan, _diff, _strategy, _cwd, _manager: FileContextEntry(path="src/foo.py", approximate_chars=100),
    )

    package = context_resolution_operations.build_review_context_package(
        plan=ReviewPlan(
            focus_files=[
                FileReviewPlan(
                    path="src/foo.py",
                    priority=FileReviewPriority.HIGH,
                    read_mode=FileReadMode.HUNKS_ONLY,
                )
            ],
            review_axes=[ChecklistCategory.FUNCTIONAL_CORRECTNESS],
        ),
        diff="diff --git a/src/foo.py b/src/foo.py\n@@ -1 +1 @@\n+print('x')\n",
        manifest=ChangeManifest(
            pr=PullRequestManifest(
                number=1,
                title="Test",
                base="main",
                head="feature/test",
                author="alex",
                description="desc",
            ),
            files=[],
            total_additions=1,
            total_deletions=0,
        ),
        checklist=[
            ReviewChecklistItem(
                id=ChecklistCategory.FUNCTIONAL_CORRECTNESS,
                name="Functional",
                description="desc",
            )
        ],
        comment_context=[],
        strategy=ReviewStrategy(
            strategy=ReviewStrategyType.DIRECT_FINDINGS,
            size_class=PRSizeClass.SMALL,
            max_focus_files=4,
            max_prompt_chars=22000,
            max_comment_entries=8,
        ),
        cwd=None,
    )

    assert called["budget"] == 1
    assert len(package.batches) == 1
