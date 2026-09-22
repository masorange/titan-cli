from titan_plugin_github.models.review_enums import ChecklistCategory, ExclusionReason, PRSizeClass
from titan_plugin_github.models.review_models import ReviewChecklistItem
from titan_plugin_github.models.review_models import ChangeManifest, ChangedFileEntry, PullRequestManifest
from titan_plugin_github.models.review_profile_models import (
    CandidateExclusions,
    CandidateScoringRule,
    ReviewAxisRule,
    ReviewProfile,
)
from titan_plugin_github.operations.review_strategy_operations import (
    build_deterministic_review_plan,
    classify_pr,
    deep_call_timeout_seconds,
    score_review_candidates,
    review_budget,
    summarize_candidate_clusters,
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
    assert classification.role_count >= 1
    assert classification.complexity_score >= 1


def test_classify_pr_repetitive_migration_downgrades_from_huge():
    files = [
        ChangedFileEntry(
            path=f"app/src/main/kotlin/com/foo/ui/screens/Screen{idx}.kt",
            status="modified",
            additions=4,
            deletions=3,
        )
        for idx in range(42)
    ]
    files.append(
        ChangedFileEntry(
            path="app/src/main/kotlin/com/foo/utils/CustomTabsUtils.kt",
            status="modified",
            additions=30,
            deletions=10,
        )
    )
    manifest = make_manifest(files)

    classification = classify_pr(manifest)

    assert classification.size_class == PRSizeClass.LARGE
    assert classification.is_repetitive_migration is True
    assert classification.repeated_callsite_files >= 40


def test_classify_pr_concentrated_feature_is_large_not_huge():
    manifest = make_manifest(
        [
            ChangedFileEntry(path="titan_plugin_ragnarok/android/operations/strings_operations.py", status="added", additions=463, deletions=0),
            ChangedFileEntry(path="titan_plugin_ragnarok/android/steps/strings/execute_strings_import_step.py", status="added", additions=339, deletions=0),
            ChangedFileEntry(path="titan_plugin_ragnarok/android/steps/strings/confirm_strings_commit_step.py", status="added", additions=202, deletions=0),
            ChangedFileEntry(path="titan_plugin_ragnarok/android/steps/strings/prompt_strings_keys_step.py", status="added", additions=164, deletions=0),
            ChangedFileEntry(path="titan_plugin_ragnarok/workflows/android/import-strings.yaml", status="added", additions=81, deletions=0, is_config=True),
            ChangedFileEntry(path="tests/operations/test_strings_operations.py", status="added", additions=693, deletions=0, is_test=True),
            ChangedFileEntry(path="tests/android/steps/strings/test_execute_strings_import_step.py", status="added", additions=210, deletions=0, is_test=True),
            ChangedFileEntry(path="tests/android/steps/strings/test_confirm_strings_commit_step.py", status="added", additions=141, deletions=0, is_test=True),
            ChangedFileEntry(path="tests/android/steps/strings/test_prompt_strings_keys_step.py", status="added", additions=116, deletions=0, is_test=True),
            ChangedFileEntry(path="tests/android/steps/strings/test_helpers.py", status="added", additions=42, deletions=0, is_test=True),
            ChangedFileEntry(path="tests/android/steps/strings/__init__.py", status="added", additions=2, deletions=0, is_test=True),
            ChangedFileEntry(path="titan_plugin_ragnarok/android/steps/strings/__init__.py", status="added", additions=4, deletions=0),
            ChangedFileEntry(path="titan_plugin_ragnarok/step_registry/android.py", status="modified", additions=12, deletions=0),
        ]
    )

    classification = classify_pr(manifest, comment_entries=23, comment_threads=22)

    assert classification.size_class == PRSizeClass.LARGE
    assert "workflow_orchestration" in classification.roles
    assert "tests" in classification.roles
    assert classification.active_review is True


def test_classify_pr_huge_multirole_stays_huge():
    files = [
        ChangedFileEntry(path=f"src/config/settings_{idx}.yaml", status="modified", additions=70, deletions=30, is_config=True)
        for idx in range(10)
    ]
    files += [
        ChangedFileEntry(path=f"src/services/service_{idx}.py", status="modified", additions=120, deletions=70)
        for idx in range(12)
    ]
    files += [
        ChangedFileEntry(path=f"src/ui/screens/screen_{idx}.tsx", status="modified", additions=90, deletions=50)
        for idx in range(10)
    ]
    files += [
        ChangedFileEntry(path=f"tests/test_feature_{idx}.py", status="modified", additions=60, deletions=20, is_test=True)
        for idx in range(8)
    ]
    manifest = make_manifest(files)

    classification = classify_pr(manifest, comment_entries=8, comment_threads=6)

    assert classification.size_class == PRSizeClass.HUGE
    assert classification.role_count >= 4


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


def test_deterministic_plan_respects_the_deep_session_budget(sample_ui_pr):
    """The focus limit is now one number for every PR.

    It used to come from a five-tier table keyed on a size label, whose last rung meant
    a 108-file PR and a 500-file PR both got 12 files reviewed.
    """
    manifest = make_manifest(
        [
            ChangedFileEntry(path=f"src/controller_{idx}.py", status="modified", additions=30, deletions=8)
            for idx in range(20)
        ]
    )
    candidates, excluded = score_review_candidates(manifest)
    budget = review_budget()

    plan = build_deterministic_review_plan(candidates, excluded, [], budget)

    assert len(candidates) > budget.max_deep_sessions
    assert len(plan.focus_files) == budget.max_deep_sessions
    assert len(plan.excluded_files) == len(excluded) + len(candidates) - budget.max_deep_sessions


def test_summarize_candidate_clusters_detects_repeated_callsites():
    files = [
        ChangedFileEntry(
            path="app/src/main/kotlin/com/foo/utils/CustomTabsUtils.kt",
            status="modified",
            additions=50,
            deletions=4,
        )
    ]
    files.extend(
        ChangedFileEntry(
            path=f"app/src/main/kotlin/com/foo/ui/screens/Screen{idx}.kt",
            status="modified",
            additions=4,
            deletions=2,
        )
        for idx in range(5)
    )
    manifest = make_manifest(files)

    candidates, _ = score_review_candidates(manifest)
    clusters = summarize_candidate_clusters(candidates)

    assert any(cluster["group"] == "repeated_callsite" for cluster in clusters)


def test_score_review_candidates_prioritizes_semantic_mapping_surfaces():
    manifest = make_manifest(
        [
            ChangedFileEntry(path="src/RecordedEventMapper.kt", status="modified", additions=12, deletions=4),
            ChangedFileEntry(path="src/FooScreen.kt", status="modified", additions=12, deletions=4),
        ]
    )

    candidates, _ = score_review_candidates(manifest)

    assert candidates[0].path == "src/RecordedEventMapper.kt"
    assert "semantic mapping surface" in candidates[0].reasons


def test_deterministic_plan_can_select_semantic_axes():
    manifest = make_manifest(
        [ChangedFileEntry(path="src/RecordedAnalyticsEvent.kt", status="modified", additions=18, deletions=3)]
    )
    candidates, excluded = score_review_candidates(manifest)
    budget = review_budget()
    checklist = [
        ReviewChecklistItem(
            id=ChecklistCategory.FUNCTIONAL_CORRECTNESS,
            name="Functional Correctness",
            description="desc",
        ),
        ReviewChecklistItem(
            id=ChecklistCategory.ERROR_HANDLING,
            name="Error Handling",
            description="desc",
        ),
        ReviewChecklistItem(
            id=ChecklistCategory.SEMANTIC_CORRECTNESS,
            name="Semantic Correctness",
            description="desc",
        ),
    ]

    plan = build_deterministic_review_plan(candidates, excluded, checklist, budget)

    assert ChecklistCategory.SEMANTIC_CORRECTNESS in plan.review_axes


def test_score_review_candidates_uses_custom_profile_thresholds_and_rules():
    manifest = make_manifest(
        [
            ChangedFileEntry(path="tests/test_api.py", status="modified", additions=6, deletions=0, is_test=True),
            ChangedFileEntry(path="src/auth/session.py", status="modified", additions=12, deletions=2),
        ]
    )
    profile = ReviewProfile(
        version=1,
        change_patterns={},
        file_roles={},
        candidate_scoring=[],
        candidate_exclusions=CandidateExclusions(low_signal_test_max_changes=5, low_signal_config_max_changes=10),
        review_axes={},
    )

    candidates, excluded = score_review_candidates(manifest, review_profile=profile)
    auth_candidate = next(candidate for candidate in candidates if candidate.path == "src/auth/session.py")

    assert {candidate.path for candidate in candidates} == {"src/auth/session.py", "tests/test_api.py"}
    assert excluded == []
    assert "security or access-sensitive area" not in auth_candidate.reasons


def test_score_review_candidates_does_not_apply_path_rules_to_tests():
    """A test file whose name matches a production scoring rule (e.g. *util*) must not
    inherit that rule's criticality — it scores on its own change size plus the test bonus."""
    manifest = make_manifest(
        [
            ChangedFileEntry(path="src/utils/EntertainmentUtils.kt", status="modified", additions=90, deletions=10),
            ChangedFileEntry(
                path="tests/utils/EntertainmentUtilsTest.kt",
                status="modified",
                additions=90,
                deletions=10,
                is_test=True,
            ),
        ]
    )
    profile = ReviewProfile(
        version=1,
        change_patterns={},
        file_roles={},
        candidate_scoring=[
            CandidateScoringRule(
                name="shared_helper",
                patterns=["**/*utils*"],
                score_delta=5,
                reason="shared helper or policy surface",
            )
        ],
        candidate_exclusions=CandidateExclusions(),
        review_axes={},
    )

    candidates, _ = score_review_candidates(manifest, review_profile=profile)
    prod = next(candidate for candidate in candidates if candidate.path == "src/utils/EntertainmentUtils.kt")
    test = next(candidate for candidate in candidates if candidate.path == "tests/utils/EntertainmentUtilsTest.kt")

    assert "shared helper or policy surface" in prod.reasons
    assert "shared helper or policy surface" not in test.reasons
    assert "test file with meaningful changes" in test.reasons
    assert prod.score > test.score


def test_score_review_candidates_keeps_reviewable_documentation_paths():
    manifest = make_manifest(
        [
            ChangedFileEntry(
                path=".claude/skills/titan-workflow-architecture/SKILL.md",
                status="modified",
                additions=0,
                deletions=95,
                is_docs=True,
            )
        ]
    )
    profile = ReviewProfile(
        version=1,
        change_patterns={},
        file_roles={},
        candidate_scoring=[],
        candidate_exclusions=CandidateExclusions(),
        review_axes={
            ChecklistCategory.DOCUMENTATION: ReviewAxisRule(
                patterns=[".claude/**", "AGENTS.md"]
            )
        },
    )

    candidates, excluded = score_review_candidates(manifest, review_profile=profile)

    assert [candidate.path for candidate in candidates] == [
        ".claude/skills/titan-workflow-architecture/SKILL.md"
    ]
    assert excluded == []


def test_classify_pr_uses_custom_change_patterns():
    manifest = make_manifest(
        [
            ChangedFileEntry(path=f"src/widgets/view_{idx}.py", status="modified", additions=3, deletions=2)
            for idx in range(12)
        ]
    )
    profile = ReviewProfile(
        version=1,
        change_patterns={"repeated_callsite": ["**/widgets/**"]},
        file_roles={},
        candidate_scoring=[],
        candidate_exclusions=CandidateExclusions(),
        review_axes={},
    )

    classification = classify_pr(manifest, review_profile=profile)

    assert classification.repeated_callsite_files == 12
    assert classification.is_repetitive_migration is True


def test_deterministic_plan_uses_profile_review_axes():
    candidates, excluded = score_review_candidates(
        make_manifest([ChangedFileEntry(path="src/auth/session.py", status="modified", additions=18, deletions=3)])
    )
    budget = review_budget()
    checklist = [
        ReviewChecklistItem(
            id=ChecklistCategory.FUNCTIONAL_CORRECTNESS,
            name="Functional Correctness",
            description="desc",
        ),
        ReviewChecklistItem(
            id=ChecklistCategory.ERROR_HANDLING,
            name="Error Handling",
            description="desc",
        ),
        ReviewChecklistItem(
            id=ChecklistCategory.SECURITY,
            name="Security",
            description="desc",
        ),
    ]
    profile = ReviewProfile(
        version=1,
        change_patterns={},
        file_roles={},
        candidate_scoring=[],
        candidate_exclusions=CandidateExclusions(),
        review_axes={
            ChecklistCategory.FUNCTIONAL_CORRECTNESS: ReviewAxisRule(always_include=True),
            ChecklistCategory.ERROR_HANDLING: ReviewAxisRule(always_include=True),
            ChecklistCategory.SECURITY: ReviewAxisRule(patterns=["**/auth/**"]),
        },
    )

    plan = build_deterministic_review_plan(candidates, excluded, checklist, budget, review_profile=profile)

    assert ChecklistCategory.SECURITY in plan.review_axes


def test_classify_pr_comment_threads_do_not_change_size_class():
    """review-quality-010: review activity must not inflate the size class — a review's
    own published comments would otherwise push the same unchanged PR into a bigger
    class on the next run, changing focus/budget between passes."""
    manifest = make_manifest(
        [
            ChangedFileEntry(path=f"src/file_{idx}.py", status="modified", additions=40, deletions=10)
            for idx in range(10)
        ]
    )

    quiet = classify_pr(manifest, comment_entries=0, comment_threads=0)
    noisy = classify_pr(manifest, comment_entries=40, comment_threads=25)

    assert noisy.size_class == quiet.size_class
    assert noisy.complexity_score == quiet.complexity_score
    # The activity signal is still captured — just not as size.
    assert noisy.active_review is True
    assert quiet.active_review is False


# ============================================================================
# Deep-call timeout derivation
# ============================================================================


def test_deep_call_timeout_matches_the_old_flat_value_for_one_file():
    """A single-file call must not come out with a shorter deadline than the flat 300 s
    it replaces — the base alone reproduces it."""
    budget = review_budget()

    assert deep_call_timeout_seconds(budget, 1) == 300
    # Zero files is not a real batch, but it must not produce a negative allowance.
    assert deep_call_timeout_seconds(budget, 0) == 300


def test_deep_call_timeout_grows_with_the_files_it_was_handed():
    """The measured shape that broke the flat timeout: ten files in one session took
    251 s at medium effort and 363 s at high, against a 300 s deadline."""
    budget = review_budget()

    ten_files = deep_call_timeout_seconds(budget, 10)

    assert ten_files > 363
    assert ten_files == budget.deep_timeout_base_seconds + 9 * budget.deep_timeout_per_file_seconds


def test_deep_call_timeout_is_capped():
    """A hung CLI cannot hold a review open indefinitely, however many files it got."""
    budget = review_budget()

    assert deep_call_timeout_seconds(budget, 500) == budget.deep_timeout_max_seconds


# ============================================================================
# The deterministic plan: the DEEP tier is the selection
# ============================================================================


def _candidate(path: str, score: int):
    from titan_plugin_github.models.review_enums import FileReadMode, FileReviewPriority
    from titan_plugin_github.models.review_models import ScoredReviewCandidate

    return ScoredReviewCandidate(
        path=path,
        score=score,
        priority=FileReviewPriority.HIGH,
        suggested_read_mode=FileReadMode.EXPANDED_HUNKS,
    )


def _attention(tiers: dict):
    from titan_plugin_github.models.review_enums import AttentionTier
    from titan_plugin_github.operations.attention_operations import AttentionPlan, FileAttention

    return AttentionPlan(
        files=[
            FileAttention(path, AttentionTier(tier), "business_logic", f"role:{tier}")
            for path, tier in tiers.items()
        ]
    )


def test_the_deep_tier_is_the_selection_not_the_top_scores():
    """Every deep file is read, and only deep files are.

    This replaced an AI planning call. On run 4fd7f345 that call spent 92,463 input
    tokens and 38.8 s choosing files, and chose 7 of the 9 the attention plan had already
    marked deep — spending two of its slots on test files tiered `glance`, so
    `titan_cli/core/oauth/__init__.py` and `exceptions.py` went unreviewed."""
    from titan_plugin_github.operations.review_strategy_operations import (
        build_deterministic_review_plan,
    )

    candidates = [
        _candidate("core.py", 9),
        _candidate("test_core.py", 8),
        _candidate("tiny.py", 1),
    ]
    plan = build_deterministic_review_plan(
        candidates,
        [],
        [],
        review_budget(),
        attention_plan=_attention({"core.py": "deep", "test_core.py": "glance", "tiny.py": "deep"}),
    )

    # tiny.py scores last but is deep, so it is read; test_core.py outscores it and is not.
    assert [f.path for f in plan.focus_files] == ["core.py", "tiny.py"]
    excluded = {entry.path: entry.detail for entry in plan.excluded_files}
    assert "test_core.py" in excluded
    assert "glance" in excluded["test_core.py"]


def test_a_deep_tier_larger_than_the_session_budget_is_capped_and_said_out_loud():
    """max_deep_sessions stops being a selection rule and becomes the overflow guard it
    was always described as — and the files it drops are named, not silent."""
    from titan_plugin_github.models.review_enums import ExclusionReason
    from titan_plugin_github.operations.review_strategy_operations import (
        build_deterministic_review_plan,
    )

    budget = review_budget().model_copy(update={"max_deep_sessions": 2})
    candidates = [_candidate(f"f{i}.py", 10 - i) for i in range(4)]
    plan = build_deterministic_review_plan(
        candidates,
        [],
        [],
        budget,
        attention_plan=_attention({f"f{i}.py": "deep" for i in range(4)}),
    )

    assert [f.path for f in plan.focus_files] == ["f0.py", "f1.py"]
    overflow = [
        entry
        for entry in plan.excluded_files
        if entry.reason == ExclusionReason.BUDGET_TRIMMED and "session limit" in entry.detail
    ]
    assert sorted(entry.path for entry in overflow) == ["f2.py", "f3.py"]


def test_without_an_attention_plan_the_score_order_cut_still_applies():
    """A step run standalone has no tiers to go on, so it keeps the old behaviour rather
    than reviewing nothing."""
    from titan_plugin_github.operations.review_strategy_operations import (
        build_deterministic_review_plan,
    )

    budget = review_budget().model_copy(update={"max_deep_sessions": 2})
    candidates = [_candidate(f"f{i}.py", 10 - i) for i in range(4)]

    plan = build_deterministic_review_plan(candidates, [], [], budget)

    assert [f.path for f in plan.focus_files] == ["f0.py", "f1.py"]
