"""
Quick Launch Service

Chooses which workflows fill the home screen's quick-launch slots, and in which order.

UI-agnostic on purpose: the home renders whatever this returns, so the whole fill rule can
be tested without a screen. The rule exists because a grid that only rendered favorites
would have nothing to show the user who has none - which is every user on their first run.
"""
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence

from .workflow_filter_service import WorkflowFilterService
from .workflow_sources import WorkflowInfo

# One slot per number key. Fixed rather than derived from the terminal size: a set that grew
# and shrank on resize would silently remap the keys under the user's fingers.
DEFAULT_SLOT_COUNT = 9


@dataclass(frozen=True)
class QuickLaunchSlot:
    """One card on the home screen.

    Attributes:
        workflow: The workflow this slot launches.
        is_favorite: Whether the user starred it, which the card marks.
        key: The number key that launches it, or None for a favorite past the key range.
    """
    workflow: WorkflowInfo
    is_favorite: bool
    key: Optional[int]


class QuickLaunchService:
    """Builds the home screen's quick-launch slots."""

    @staticmethod
    def build_slots(
        workflows: Sequence[WorkflowInfo],
        favorite_names: Sequence[str],
        last_used: Mapping[str, str] = None,
        slot_count: int = DEFAULT_SLOT_COUNT,
    ) -> List[QuickLaunchSlot]:
        """Choose and order the workflows the home screen offers.

        Fills in three stages, each skipping what an earlier stage already placed:

        1. Favorites, in the order they were starred. **Never truncated** - a favorite the
           user starred by hand is always shown, even past `slot_count`, because hiding one
           with no indication it exists is worse than a row below the fold.
        2. Workflows by most recent run.
        3. Round-robin across the groups `detect_plugin_name()` reports - one per group per
           pass, groups in alphabetical order - until the slots are full or the candidates
           run out.

        Stage 3 takes no per-group cap. Round-robin already balances (nine slots over three
        groups gives three each), and a cap would leave holes exactly where it bit: one group
        holding twenty workflows would fill three slots and leave six empty.

        Args:
            workflows: Discovered workflows. Deduplicated by name here, so callers may pass
                raw discovery output.
            favorite_names: Starred workflow names, in star order.
            last_used: Workflow name to ISO-8601 timestamp. Sorts lexicographically, which
                for ISO-8601 UTC is chronological.
            slot_count: How many slots to fill, and how many number keys to assign.

        Returns:
            Slots in display order. Length is `slot_count`, or the favorite count when that
            is greater, or the number of available workflows when that is fewer.
        """
        by_name = {
            wf.name: wf
            for wf in WorkflowFilterService.remove_duplicates(list(workflows))
        }

        chosen: List[WorkflowInfo] = []
        favorites: set = set()
        placed: set = set()

        def take(name: str) -> bool:
            """Place a workflow by name, if it exists and is not already placed."""
            workflow = by_name.get(name)
            if workflow is None or name in placed:
                return False
            placed.add(name)
            chosen.append(workflow)
            return True

        # 1. Favorites, in star order. A name with no matching workflow is skipped rather
        # than reported: a disabled plugin's workflows come back when it is re-enabled.
        for name in favorite_names:
            if take(name):
                favorites.add(name)

        # 2. Most recently run first.
        recents = sorted(
            ((name, stamp) for name, stamp in (last_used or {}).items()),
            key=lambda item: item[1],
            reverse=True,
        )
        for name, _ in recents:
            if len(chosen) >= slot_count:
                break
            take(name)

        # 3. Round-robin across groups, so no single group crowds the grid out.
        if len(chosen) < slot_count:
            queues = QuickLaunchService._group_queues(by_name, placed)
            while len(chosen) < slot_count and queues:
                for queue in list(queues):
                    if len(chosen) >= slot_count:
                        break
                    take(queue.pop(0))
                queues = [queue for queue in queues if queue]

        return [
            QuickLaunchSlot(
                workflow=workflow,
                is_favorite=workflow.name in favorites,
                key=index + 1 if index < slot_count else None,
            )
            for index, workflow in enumerate(chosen)
        ]

    @staticmethod
    def _group_queues(
        by_name: Dict[str, WorkflowInfo],
        placed: set,
    ) -> List[List[str]]:
        """Remaining candidate names per group, groups alphabetical.

        Alphabetical rather than by size, so the grid a user sees does not reshuffle when a
        group gains a workflow. Within a group, discovery order is preserved.
        """
        grouped = WorkflowFilterService.group_by_plugin(
            [wf for name, wf in by_name.items() if name not in placed]
        )
        return [
            [wf.name for wf in grouped[group]]
            for group in sorted(grouped)
            if grouped[group]
        ]
