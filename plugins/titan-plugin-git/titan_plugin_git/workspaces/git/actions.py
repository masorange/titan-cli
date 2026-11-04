"""What a press on the screen does: the workspace wires these to state and reads, the drawing only calls them."""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Actions:
    select: Callable[[str], None]
    toggle: Callable[[str, str, object], None]
    more_commits: Callable[[], None]
    fewer_commits: Callable[[], None]
    more_lines: Callable[[str, int], None]
    retry_history: Callable[[], None]
    retry_files: Callable[[str], None]
    retry_diff: Callable[[str, str, object], None]
    copy: Callable[[str, str], None]
    resize: Callable[[tuple], None]
    stash: Callable[[str, object], None]
    index: Callable[[str, list], None]
