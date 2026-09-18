"""
Tests for QuickLaunchService

The home screen's fill rule: favorites in star order, then most recently run, then a
balanced round-robin across groups.
"""
from pathlib import Path
from typing import List

from titan_cli.core.workflows.quick_launch_service import (
    DEFAULT_SLOT_COUNT,
    QuickLaunchService,
    QuickLaunchSlot,
)
from titan_cli.core.workflows.workflow_sources import WorkflowInfo


def _wf(name: str, source: str = "plugin:git", **kwargs) -> WorkflowInfo:
    """Build a discovered workflow with only the fields the fill rule reads."""
    return WorkflowInfo(
        name=name,
        description=f"{name} description",
        source=source,
        path=Path(f"/workflows/{name}.yaml"),
        **kwargs,
    )


def _names(slots: List[QuickLaunchSlot]) -> List[str]:
    return [slot.workflow.name for slot in slots]


def _group_counts(slots: List[QuickLaunchSlot]) -> dict:
    """How many slots each source contributed, keyed by the source's bare plugin name."""
    counts: dict = {}
    for slot in slots:
        key = slot.workflow.source.split(":", 1)[-1]
        counts[key] = counts.get(key, 0) + 1
    return counts


class TestFavorites:
    """Stage 1: starred workflows, in the order they were starred."""

    def test_favorites_come_first_in_star_order(self):
        workflows = [_wf("alpha"), _wf("beta"), _wf("gamma")]

        slots = QuickLaunchService.build_slots(workflows, ["gamma", "alpha"])

        assert _names(slots)[:2] == ["gamma", "alpha"]
        assert [slot.is_favorite for slot in slots][:2] == [True, True]

    def test_star_order_is_not_recency_order(self):
        """A favorite's position comes from when it was starred, not when it last ran.

        The user set that order deliberately by starring in sequence; a grid that
        reshuffled itself under fixed number keys between sessions would undo the point
        of having fixed keys.
        """
        workflows = [_wf("alpha"), _wf("beta")]

        slots = QuickLaunchService.build_slots(
            workflows,
            ["alpha", "beta"],
            {"beta": "2026-09-18T10:00:00Z", "alpha": "2026-01-01T00:00:00Z"},
        )

        assert _names(slots) == ["alpha", "beta"]

    def test_a_favorite_naming_a_workflow_that_is_gone_is_skipped(self):
        """A disabled plugin's workflows come back, so the stored name is left alone."""
        slots = QuickLaunchService.build_slots([_wf("alpha")], ["vanished", "alpha"])

        assert _names(slots) == ["alpha"]

    def test_every_favorite_is_shown_even_past_the_slot_count(self):
        """D-007: more favorites than slots means the grid grows, never truncates."""
        workflows = [_wf(f"wf-{index:02d}") for index in range(12)]
        favorites = [wf.name for wf in workflows]

        slots = QuickLaunchService.build_slots(workflows, favorites, slot_count=9)

        assert len(slots) == 12
        assert all(slot.is_favorite for slot in slots)

    def test_only_the_first_slots_get_a_number_key(self):
        """Keys stop at the slot count; the rest are reachable by arrow navigation."""
        workflows = [_wf(f"wf-{index:02d}") for index in range(12)]

        slots = QuickLaunchService.build_slots(
            workflows, [wf.name for wf in workflows], slot_count=9
        )

        assert [slot.key for slot in slots[:9]] == [1, 2, 3, 4, 5, 6, 7, 8, 9]
        assert [slot.key for slot in slots[9:]] == [None, None, None]


class TestRecents:
    """Stage 2: most recently run first."""

    def test_recents_fill_after_favorites_newest_first(self):
        workflows = [_wf("alpha"), _wf("beta"), _wf("gamma")]

        slots = QuickLaunchService.build_slots(
            workflows,
            ["alpha"],
            {"beta": "2026-09-01T00:00:00Z", "gamma": "2026-09-18T00:00:00Z"},
            slot_count=3,
        )

        assert _names(slots) == ["alpha", "gamma", "beta"]
        assert [slot.is_favorite for slot in slots] == [True, False, False]

    def test_a_recent_that_is_already_a_favorite_is_not_repeated(self):
        workflows = [_wf("alpha"), _wf("beta")]

        slots = QuickLaunchService.build_slots(
            workflows, ["alpha"], {"alpha": "2026-09-18T00:00:00Z"}, slot_count=2
        )

        assert _names(slots) == ["alpha", "beta"]

    def test_a_recent_naming_a_workflow_that_is_gone_is_skipped(self):
        slots = QuickLaunchService.build_slots(
            [_wf("alpha")], [], {"vanished": "2026-09-18T00:00:00Z"}
        )

        assert _names(slots) == ["alpha"]


class TestRoundRobinBalance:
    """Stage 3: no single group crowds the grid out."""

    def test_the_worked_example(self):
        """git(2), github(5), jira(4), project(1) with no favorites.

        This is the balance the feature was specified by, kept verbatim: pass one takes one
        of each (4), pass two takes git+github+jira (7, project exhausted), pass three takes
        github+jira (9, git exhausted).
        """
        workflows = (
            [_wf(f"git-{i}", "plugin:git") for i in range(2)]
            + [_wf(f"github-{i}", "plugin:github") for i in range(5)]
            + [_wf(f"jira-{i}", "plugin:jira") for i in range(4)]
            + [_wf("project-0", "project")]
        )

        slots = QuickLaunchService.build_slots(workflows, [], slot_count=9)

        assert len(slots) == 9
        assert _group_counts(slots) == {"git": 2, "github": 3, "jira": 3, "project": 1}

    def test_one_group_with_more_workflows_than_slots_fills_them_all(self):
        """The case a per-group cap of 3 would have broken, leaving six empty slots."""
        workflows = [_wf(f"github-{index:02d}", "plugin:github") for index in range(20)]

        slots = QuickLaunchService.build_slots(workflows, [], slot_count=9)

        assert len(slots) == 9
        assert _group_counts(slots) == {"github": 9}

    def test_groups_are_visited_alphabetically(self):
        """Alphabetical, so the grid does not reshuffle when a group gains a workflow."""
        workflows = [
            _wf("zulu-0", "plugin:zulu"),
            _wf("alpha-0", "plugin:alpha"),
            _wf("mike-0", "plugin:mike"),
        ]

        slots = QuickLaunchService.build_slots(workflows, [], slot_count=3)

        assert _names(slots) == ["alpha-0", "mike-0", "zulu-0"]

    def test_an_explicit_category_is_the_grouping_axis(self):
        """The axis is detect_plugin_name(), which a workflow's own `category:` overrides.

        So a workflow that merely uses a github step can sit in its team's own group, and
        the balance is computed over the groups the Workflows screen already shows - not
        over the list of installed plugins.
        """
        workflows = [
            _wf("gh-0", "plugin:github"),
            _wf("gh-1", "plugin:github"),
            _wf("release-0", "plugin:github", category="Release"),
        ]

        slots = QuickLaunchService.build_slots(workflows, [], slot_count=2)

        # Github and Release are two groups, so one comes from each rather than both
        # from Github.
        assert _names(slots) == ["gh-0", "release-0"]

    def test_fewer_workflows_than_slots_returns_what_exists(self):
        slots = QuickLaunchService.build_slots([_wf("alpha"), _wf("beta")], [], slot_count=9)

        assert _names(slots) == ["alpha", "beta"]

    def test_no_workflows_returns_no_slots(self):
        assert QuickLaunchService.build_slots([], ["alpha"], {"beta": "x"}) == []


class TestInputHandling:
    def test_duplicate_workflow_names_are_collapsed(self):
        """Discovery can return the same name from several sources; the first one wins."""
        workflows = [
            _wf("commit", "plugin:git"),
            _wf("commit", "project"),
            _wf("other", "plugin:git"),
        ]

        slots = QuickLaunchService.build_slots(workflows, [], slot_count=9)

        assert _names(slots) == ["commit", "other"]
        assert slots[0].workflow.source == "plugin:git"

    def test_last_used_may_be_omitted(self):
        slots = QuickLaunchService.build_slots([_wf("alpha")], [])

        assert _names(slots) == ["alpha"]

    def test_the_three_stages_never_repeat_a_workflow(self):
        """A name reachable by all three stages still occupies exactly one slot."""
        workflows = [_wf(f"wf-{index}", "plugin:git") for index in range(4)]

        slots = QuickLaunchService.build_slots(
            workflows,
            ["wf-0"],
            {"wf-0": "2026-09-18T00:00:00Z", "wf-1": "2026-09-17T00:00:00Z"},
            slot_count=9,
        )

        assert _names(slots) == ["wf-0", "wf-1", "wf-2", "wf-3"]
        assert len(set(_names(slots))) == 4

    def test_the_default_slot_count_is_nine(self):
        """One per number key - the constant the screen and the keys both read."""
        assert DEFAULT_SLOT_COUNT == 9

        workflows = [_wf(f"wf-{index:02d}", "plugin:git") for index in range(20)]

        assert len(QuickLaunchService.build_slots(workflows, [])) == 9
