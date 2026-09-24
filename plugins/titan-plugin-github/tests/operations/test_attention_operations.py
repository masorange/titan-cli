"""Tests for how much attention each changed file is worth.

The tiers answer "is the diff alone enough to judge this change?", not "is this file
important?" — so the assertions below are about precedence and explainability, not about
whether a given role deserves a deep read.
"""

from titan_plugin_github.models.review_enums import AttentionTier, FileChangeStatus
from titan_plugin_github.models.review_models import ChangedFileEntry
from titan_plugin_github.models.review_profile_models import ReviewProfile
from titan_plugin_github.operations.attention_operations import (
    resolve_file_attention,
    summarize_attention_plan,
)
from titan_plugin_github.review_profiles import DEFAULT_REVIEW_PROFILE


def _file(path: str, **flags) -> ChangedFileEntry:
    return ChangedFileEntry(path=path, status=FileChangeStatus.MODIFIED, **flags)


def _profile(**overrides) -> ReviewProfile:
    base = dict(
        file_roles={
            "business_logic": ["**/services/**"],
            "entrypoints_or_ui": ["**/screens/**"],
        },
        attention={
            "business_logic": AttentionTier.DEEP,
            "entrypoints_or_ui": AttentionTier.GLANCE,
            "tests": AttentionTier.GLANCE,
            "docs_or_generated": AttentionTier.SKIP,
        },
    )
    base.update(overrides)
    return ReviewProfile(**base)


class TestOverlappingRoles:
    """A path matching several roles gets the one asking for the MOST attention."""

    def test_the_deeper_role_wins_whatever_order_the_roles_are_listed_in(self):
        """ragnarok listed `**/ui/**` (glance) before `**/*ViewModel.kt` (business,
        deep); first-match sent LoginViewModel to the triage."""
        profile = _profile(
            file_roles={
                "entrypoints_or_ui": ["**/ui/**"],
                "business_logic": ["**/*ViewModel.kt"],
            }
        )

        plan = resolve_file_attention([_file("app/ui/login/LoginViewModel.kt")], profile)

        assert plan.files[0].tier == AttentionTier.DEEP
        assert plan.files[0].role == "business_logic"

    def test_list_order_only_breaks_a_tie(self):
        profile = _profile(
            file_roles={"business_logic": ["**/core/**"], "integration_or_adapter": ["**/core/**"]},
            attention={"business_logic": AttentionTier.DEEP, "integration_or_adapter": AttentionTier.DEEP},
        )

        plan = resolve_file_attention([_file("app/core/x.py")], profile)

        assert plan.files[0].role == "business_logic"

    def test_a_config_looking_name_does_not_outrank_a_deep_role(self):
        """`is_config` is a guess from the file name; a deep role the project wrote wins."""
        profile = _profile(file_roles={"business_logic": ["**/services/**"]})

        plan = resolve_file_attention([_file("app/services/settings.yaml", is_config=True)], profile)

        assert plan.files[0].tier == AttentionTier.DEEP

    def test_tests_stay_tests_even_under_a_deep_path(self):
        """Detected tests are a fact about the file, not a pattern guess."""
        plan = resolve_file_attention([_file("app/services/pay_test.py", is_test=True)], _profile())

        assert plan.files[0].role == "tests"


class TestDeletedFiles:

    def test_a_deleted_file_goes_to_the_triage_whatever_its_role(self):
        """Not deep (nothing to open) and not skipped: its diff is what the PR removes.
        Skipping them cost ragnarok PR #3720 the questions that found removed tracking."""
        deleted = ChangedFileEntry(path="app/services/pay.py", status=FileChangeStatus.DELETED)

        plan = resolve_file_attention([deleted], _profile())

        assert plan.files[0].tier == AttentionTier.GLANCE
        assert plan.files[0].reason == "deleted"

    def test_always_deep_does_not_send_a_deleted_file_to_the_deep_session(self):
        deleted = ChangedFileEntry(path="app/core/security/gate.py", status=FileChangeStatus.DELETED)

        plan = resolve_file_attention([deleted], _profile(always_deep=["**/core/security/**"]))

        assert plan.files[0].tier == AttentionTier.GLANCE


class TestRoleDrivesTheTier:

    def test_a_role_mapped_to_deep_gets_deep(self):
        plan = resolve_file_attention([_file("app/services/pay.py")], _profile())

        assert plan.files[0].tier == AttentionTier.DEEP
        assert plan.files[0].reason == "role:business_logic"

    def test_a_role_mapped_to_glance_gets_glance(self):
        plan = resolve_file_attention([_file("app/screens/home.py")], _profile())

        assert plan.files[0].tier == AttentionTier.GLANCE

    def test_docs_are_skipped_through_their_derived_role(self):
        plan = resolve_file_attention([_file("README.md", is_docs=True)], _profile())

        assert plan.files[0].tier == AttentionTier.SKIP
        assert plan.files[0].role == "docs_or_generated"

    def test_an_unconfigured_role_falls_back_to_glance_not_skip(self):
        """Covering a file cheaply is the safe default; skipping it silently is not."""
        plan = resolve_file_attention([_file("misc/thing.py")], _profile())

        assert plan.files[0].tier == AttentionTier.GLANCE
        assert plan.files[0].role == "other"
        assert plan.files[0].reason == "role_not_configured:other"

    def test_an_empty_attention_map_still_covers_everything(self):
        plan = resolve_file_attention([_file("app/services/pay.py")], _profile(attention={}))

        assert plan.files[0].tier == AttentionTier.GLANCE
        assert plan.count_for(AttentionTier.SKIP) == 0


class TestPrecedence:

    def test_always_deep_beats_the_roles_tier(self):
        plan = resolve_file_attention(
            [_file("app/screens/home.py")],
            _profile(always_deep=["**/screens/**"]),
        )

        assert plan.files[0].tier == AttentionTier.DEEP
        assert plan.files[0].reason == "always_deep"

    def test_always_deep_beats_a_skipped_role(self):
        """A two-line change in a declared boundary deserves a full read even if its
        role would normally be skipped."""
        plan = resolve_file_attention(
            [_file("docs/security.md", is_docs=True)],
            _profile(always_deep=["docs/security.md"]),
        )

        assert plan.files[0].tier == AttentionTier.DEEP

    def test_always_deep_beats_the_lockfile_skip(self):
        """A hatch that gets second-guessed is not a hatch."""
        plan = resolve_file_attention(
            [_file("poetry.lock", is_lockfile=True)],
            _profile(always_deep=["poetry.lock"]),
        )

        assert plan.files[0].tier == AttentionTier.DEEP

    def test_a_lockfile_is_skipped_without_being_configured(self):
        plan = resolve_file_attention([_file("poetry.lock", is_lockfile=True)], _profile())

        assert plan.files[0].tier == AttentionTier.SKIP
        assert plan.files[0].reason == "lockfile"

    def test_a_rename_only_change_is_skipped(self):
        """Moving a file does not change what it does."""
        plan = resolve_file_attention(
            [_file("app/services/pay.py", is_rename_only=True)], _profile()
        )

        assert plan.files[0].tier == AttentionTier.SKIP
        assert plan.files[0].reason == "rename_only"

    def test_always_deep_matches_case_insensitively_like_the_rest_of_the_profile(self):
        plan = resolve_file_attention(
            [_file("App/Services/Pay.py")], _profile(always_deep=["**/services/**"])
        )

        assert plan.files[0].tier == AttentionTier.DEEP


class TestPlanShape:

    def test_counts_include_tiers_that_came_out_empty(self):
        """A summary whose keys change shape between PRs is harder to compare."""
        plan = resolve_file_attention([_file("app/services/pay.py")], _profile())

        assert plan.counts == {"deep": 1, "glance": 0, "skip": 0}

    def test_reviewable_count_excludes_the_skipped(self):
        """The honest denominator: coverage against the PR's total file count flatters
        the review on any PR with generated output in it."""
        plan = resolve_file_attention(
            [
                _file("app/services/pay.py"),
                _file("app/screens/home.py"),
                _file("README.md", is_docs=True),
                _file("poetry.lock", is_lockfile=True),
            ],
            _profile(),
        )

        assert len(plan.files) == 4
        assert plan.reviewable_count == 2

    def test_paths_can_be_read_back_per_tier(self):
        plan = resolve_file_attention(
            [_file("app/services/pay.py"), _file("app/screens/home.py")], _profile()
        )

        assert plan.paths_for(AttentionTier.DEEP) == ["app/services/pay.py"]
        assert plan.paths_for(AttentionTier.GLANCE) == ["app/screens/home.py"]

    def test_no_files_is_not_an_error(self):
        plan = resolve_file_attention([], _profile())

        assert plan.files == []
        assert plan.reviewable_count == 0


class TestSummary:

    def test_skip_reasons_are_grouped_rather_than_listed_per_path(self):
        plan = resolve_file_attention(
            [
                _file("a.lock", is_lockfile=True),
                _file("b.lock", is_lockfile=True),
                _file("README.md", is_docs=True),
                _file("app/services/pay.py"),
            ],
            _profile(),
        )

        summary = summarize_attention_plan(plan)

        assert summary["files_total"] == 4
        assert summary["files_reviewable"] == 1
        assert summary["skip_reasons"] == {"lockfile": 2, "role:docs_or_generated": 1}

    def test_always_deep_files_are_named_because_they_are_a_project_decision(self):
        plan = resolve_file_attention(
            [_file("core/security/vault.py"), _file("app/screens/home.py")],
            _profile(always_deep=["**/core/security/**"]),
        )

        assert summarize_attention_plan(plan)["always_deep_files"] == ["core/security/vault.py"]


class TestShippedDefaults:
    """The profile Titan ships has to hold together on its own."""

    def test_every_role_the_default_profile_defines_has_a_tier(self):
        """A role with no tier silently falls back to glance, which would make the
        shipped configuration quieter than it looks."""
        for role in DEFAULT_REVIEW_PROFILE.file_roles:
            assert role in DEFAULT_REVIEW_PROFILE.attention, role

    def test_the_three_derived_roles_and_other_have_a_tier(self):
        for role in ("docs_or_generated", "tests", "config_or_contracts", "other"):
            assert role in DEFAULT_REVIEW_PROFILE.attention, role

    def test_nothing_is_deep_by_accident(self):
        deep_roles = {
            role for role, tier in DEFAULT_REVIEW_PROFILE.attention.items()
            if tier == AttentionTier.DEEP
        }

        # UI is deep on purpose: a screen or view model holds state and effects the diff
        # alone cannot show (ragnarok PR #3692 triaged its post-login flow from diffs).
        assert deep_roles == {
            "business_logic",
            "integration_or_adapter",
            "workflow_orchestration",
            "entrypoints_or_ui",
        }

    def test_only_generated_output_and_docs_are_skipped_by_default(self):
        skipped = {
            role for role, tier in DEFAULT_REVIEW_PROFILE.attention.items()
            if tier == AttentionTier.SKIP
        }

        assert skipped == {"docs_or_generated"}

    def test_always_deep_ships_empty_because_titan_cannot_know_a_projects_boundaries(self):
        assert DEFAULT_REVIEW_PROFILE.always_deep == []


# ============================================================================
# build_change_shape_lines — the whole-change context for the deep session
# ============================================================================


def test_change_shape_lines_cover_every_file_and_mark_who_reads_it():
    """The deep session's answer to "what is missing" comes from here: every changed
    file, its role and its tier, with no content at any PR size."""
    from titan_plugin_github.models.review_enums import FileChangeStatus
    from titan_plugin_github.models.review_models import ChangedFileEntry
    from titan_plugin_github.operations.attention_operations import (
        AttentionPlan,
        FileAttention,
        build_change_shape_lines,
    )

    plan = AttentionPlan(
        files=[
            FileAttention("core.py", AttentionTier.DEEP, "business_logic", "role:business_logic"),
            FileAttention("ui.py", AttentionTier.GLANCE, "entrypoints_or_ui", "role:entrypoints_or_ui"),
            FileAttention("out.lock", AttentionTier.SKIP, "config_or_contracts", "lockfile"),
        ]
    )
    files = [
        ChangedFileEntry(path="core.py", status=FileChangeStatus.MODIFIED, additions=40, deletions=3),
        ChangedFileEntry(path="ui.py", status=FileChangeStatus.MODIFIED, additions=5, deletions=1),
        ChangedFileEntry(path="out.lock", status=FileChangeStatus.MODIFIED, additions=900, deletions=900),
    ]

    lines = build_change_shape_lines(plan, files, {"core.py"})

    assert len(lines) == 3
    assert lines[0] == "core.py | role=business_logic | reviewed here | +40/-3"
    assert lines[1] == "ui.py | role=entrypoints_or_ui | glance | +5/-1"
    assert lines[2] == "out.lock | role=config_or_contracts | skip | +900/-900"


def test_change_shape_lines_tolerate_a_file_missing_from_the_manifest():
    """The tier plan and the churn census are built from different sources; a gap
    between them must not lose the file from the shape."""
    from titan_plugin_github.operations.attention_operations import (
        AttentionPlan,
        FileAttention,
        build_change_shape_lines,
    )

    plan = AttentionPlan(
        files=[FileAttention("core.py", AttentionTier.DEEP, "business_logic", "role:business_logic")]
    )

    lines = build_change_shape_lines(plan, [], set())

    assert lines == ["core.py | role=business_logic | deep | +0/-0"]


