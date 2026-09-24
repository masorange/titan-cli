"""Tests for merging a project's review configuration onto Titan's.

The bug this replaced: a project `profile.yaml` was validated ON ITS OWN, and every
field of `ReviewProfile` defaults to empty — so a file defining a single rule left the
review with no `file_roles` and no `review_axes`. Every
file then classified as "other" and the axes fell back to two emergency values. A team
tuning its review silently got a degraded one.

The rule that fixes it without creating a different confusion: **the unit of merge is
the named entry, never the pattern list.** You own a key completely or you leave it
alone, so "Titan's 20 test globs plus the team's 3 equals 23 nobody wrote" is not a
reachable state.
"""

from titan_plugin_github.operations.review_config_merge_operations import (
    merge_review_checklist_items,
    merge_review_profile_data,
)


def _base() -> dict:
    return {
        "version": 1,
        "file_roles": {"tests": ["**/tests/**", "**/spec/**"], "business_logic": ["**/services/**"]},
        "attention": {"business_logic": "deep", "tests": "glance"},
        "review_axes": {
            "functional_correctness": {"always_include": True, "patterns": []},
            "security": {"always_include": False, "patterns": ["**/*auth*"]},
        },
        "max_context_docs": 8,
    }


class TestTheBugThisFixes:

    def test_a_one_rule_project_file_no_longer_wipes_everything_else(self):
        """The exact shape that broke it: a file that only tunes one axis."""
        merged, report = merge_review_profile_data(
            _base(), {"review_axes": {"security": {"patterns": ["**/x/**"]}}}
        )

        assert merged["file_roles"] == _base()["file_roles"]
        assert merged["attention"] == _base()["attention"]
        assert merged["review_axes"]["functional_correctness"] == _base()["review_axes"]["functional_correctness"]
        assert report.replaced == ["review_axes.security"]

    def test_an_empty_project_file_changes_nothing(self):
        merged, report = merge_review_profile_data(_base(), {})

        assert merged == _base()
        assert report.is_empty


class TestPerKeyReplacement:

    def test_a_mentioned_key_is_replaced_whole(self):
        merged, report = merge_review_profile_data(
            _base(), {"file_roles": {"tests": ["**/my_tests/**"]}}
        )

        assert merged["file_roles"]["tests"] == ["**/my_tests/**"]
        assert report.replaced == ["file_roles.tests"]

    def test_pattern_lists_are_never_unioned(self):
        """The confusing middle state the design exists to make unreachable."""
        merged, _ = merge_review_profile_data(
            _base(), {"file_roles": {"tests": ["**/my_tests/**"]}}
        )

        assert "**/spec/**" not in merged["file_roles"]["tests"]

    def test_an_unmentioned_key_keeps_titans_value(self):
        merged, _ = merge_review_profile_data(
            _base(), {"file_roles": {"tests": ["**/my_tests/**"]}}
        )

        assert merged["file_roles"]["business_logic"] == ["**/services/**"]

    def test_a_new_key_is_added_and_reported_as_added(self):
        merged, report = merge_review_profile_data(
            _base(), {"file_roles": {"generated": ["**/gen/**"]}}
        )

        assert merged["file_roles"]["generated"] == ["**/gen/**"]
        assert report.added == ["file_roles.generated"]

    def test_a_scalar_is_replaced(self):
        merged, report = merge_review_profile_data(_base(), {"max_context_docs": 4})

        assert merged["max_context_docs"] == 4
        assert "max_context_docs" in report.replaced

    def test_one_role_s_attention_is_merged_without_losing_the_others(self):
        """`attention` merges per role: sending UI to glance must not drop business
        logic back to the fallback tier."""
        merged, report = merge_review_profile_data(_base(), {"attention": {"tests": "skip"}})

        assert merged["attention"] == {"business_logic": "deep", "tests": "skip"}
        assert report.replaced == ["attention.tests"]

    def test_a_key_removed_from_titan_is_reported_as_ignored(self):
        """Project profiles written for the old pipeline still carry scoring keys; they
        must load, and say those keys do nothing."""
        merged, report = merge_review_profile_data(
            _base(), {"candidate_scoring": [{"name": "x"}], "change_patterns": {}}
        )

        assert "candidate_scoring" not in merged
        assert report.ignored_keys == ["candidate_scoring", "change_patterns"]

    def test_the_base_is_never_mutated(self):
        """Titan's defaults are process-wide; writing into them would leak one
        project's configuration into the next resolution."""
        base = _base()
        merge_review_profile_data(base, {"file_roles": {"tests": ["**/x/**"]}})

        assert base["file_roles"]["tests"] == ["**/tests/**", "**/spec/**"]


class TestRemoval:

    def test_a_mapping_key_can_be_removed_explicitly(self):
        merged, report = merge_review_profile_data(_base(), {"remove": {"file_roles": ["tests"]}})

        assert "tests" not in merged["file_roles"]
        assert report.removed == ["file_roles.tests"]

    def test_a_single_name_may_be_given_without_a_list(self):
        merged, _ = merge_review_profile_data(_base(), {"remove": {"file_roles": "tests"}})

        assert "tests" not in merged["file_roles"]

    def test_a_removal_that_matches_nothing_is_reported_not_raised(self):
        """Failing a whole review over a stale line in a config file is a poor trade,
        but the user believes it did something — so it is surfaced."""
        merged, report = merge_review_profile_data(_base(), {"remove": {"file_roles": ["nope"]}})

        assert merged["file_roles"] == _base()["file_roles"]
        assert report.unknown_removals == ["file_roles.nope"]
        assert report.has_warnings

    def test_removing_from_an_unmergeable_field_is_reported(self):
        _, report = merge_review_profile_data(_base(), {"remove": {"version": ["1"]}})

        assert report.unknown_removals == ["version.1"]

    def test_a_malformed_remove_block_is_reported(self):
        _, report = merge_review_profile_data(_base(), {"remove": ["file_roles"]})

        assert report.has_warnings
        assert report.unknown_removals


class TestUnknownSettings:

    def test_an_unknown_field_is_ignored_but_reported(self):
        """Pydantic ignores extras in silence, which turns a typo into a change that
        appears to have been applied."""
        merged, report = merge_review_profile_data(_base(), {"file_rolez": {"tests": []}})

        assert "file_rolez" not in merged
        assert report.ignored_keys == ["file_rolez"]
        assert report.has_warnings


class TestChecklistMerge:

    BASE = [
        {"id": "functional_correctness", "name": "Functional Correctness", "description": "d1",
         "relevant_file_patterns": []},
        {"id": "error_handling", "name": "Error Handling", "description": "d2",
         "relevant_file_patterns": []},
    ]

    def test_a_project_item_replaces_its_default_in_place(self):
        merged, report = merge_review_checklist_items(
            self.BASE,
            [{"id": "error_handling", "name": "Errors", "description": "ours", "relevant_file_patterns": []}],
        )

        assert [i["id"] for i in merged] == ["functional_correctness", "error_handling"]
        assert merged[1]["description"] == "ours"
        assert report.replaced == ["error_handling"]

    def test_adding_one_item_does_not_cost_the_defaults(self):
        merged, report = merge_review_checklist_items(
            self.BASE,
            [{"id": "security", "name": "Security", "description": "ours", "relevant_file_patterns": []}],
        )

        assert len(merged) == 3
        assert report.added == ["security"]

    def test_an_item_can_be_removed_by_id(self):
        merged, report = merge_review_checklist_items(self.BASE, [], ["error_handling"])

        assert [i["id"] for i in merged] == ["functional_correctness"]
        assert report.removed == ["error_handling"]

    def test_removing_an_absent_id_is_reported(self):
        merged, report = merge_review_checklist_items(self.BASE, [], ["made_up"])

        assert len(merged) == 2
        assert report.unknown_removals == ["made_up"]

    def test_an_empty_project_checklist_yields_the_defaults(self):
        merged, report = merge_review_checklist_items(self.BASE, [])

        assert [i["id"] for i in merged] == [i["id"] for i in self.BASE]
        assert report.is_empty
