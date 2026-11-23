"""
The one place the repo's PRs, merge queue and runs are read from GitHub.

The github mod and the github workspace show the same data. Each asks the feed for what it draws,
from its own timer, with how old an answer it accepts (`max_age`, its refresh period): the feed
goes to GitHub only when the snapshot it holds is older than that, and only one asker at a time,
so the others wait and share the answer. N views of the same topic cost one read per period, and
a topic nobody asks for (a closed screen, a folded pane) costs nothing.

A deeper read serves a shallower one: runs read 30 deep answer a view that shows 10, the queue
read for 8 entries answers one that shows 5. `refresh()` forgets a topic (or all of them), for the
reads that follow a change or that the user asked to repeat.

Views keep their timers (Titan stops them with the view); the feed has no thread of its own.
"""
import threading
import time
import weakref
from dataclasses import replace
from typing import Any, Callable, Dict, Hashable, Optional, Tuple

from . import invalidate
from .models import Others, Prs, Queue, Runs
from .prs import read_others, read_prs
from .queue import read_queue
from .runs import read_runs

clock: Callable[[], float] = time.monotonic


class Feed:
    def __init__(self, github: Any):
        self._github = github
        self._lock = threading.Lock()
        # topic -> (when it was read, how deep, the snapshot)
        self._held: Dict[Hashable, Tuple[float, int, Any]] = {}
        self._flights: Dict[Hashable, threading.Lock] = {}

    # -- what the views ask for ------------------------------------------------

    def prs(self, max_age: float) -> Prs:
        """Review requests, your PRs and the open count."""
        return self._get("prs", 0, max_age, lambda _: read_prs(self._github), None)

    def others(self, max_age: float) -> Others:
        """Every open PR (the workspace's "others")."""
        return self._get("others", 0, max_age, lambda _: read_others(self._github), None)

    def queue(self, shown: int, max_age: float) -> Queue:
        """The merge queue, `shown` entries deep."""
        return self._get("queue", shown, max_age, lambda n: read_queue(self._github, n),
                         lambda q, n: replace(q, entries=q.entries[:n]))

    def runs(self, trigger: Optional[str], limit: int, max_age: float) -> Runs:
        """The latest `limit` runs, of one trigger event when given ("merge_group" is the queue's)."""
        return self._get(("runs", trigger), limit, max_age, lambda n: read_runs(self._github, trigger, n),
                         lambda r, n: replace(r, runs=r.runs[:n], limit=n))

    def refresh(self, topic: Optional[Hashable] = None) -> None:
        """Make the next ask of `topic` (every topic when None) go to GitHub, past the client's own cache too."""
        with self._lock:
            if topic is None:
                self._held.clear()
            else:
                self._held = {k: v for k, v in self._held.items() if k != topic and not (
                    isinstance(k, tuple) and k[0] == topic)}
        invalidate(self._github)

    # -- how ---------------------------------------------------------------------

    def _fresh(self, topic: Hashable, depth: int, max_age: float) -> Optional[Any]:
        with self._lock:
            held = self._held.get(topic)
        if held is None:
            return None
        read_at, held_depth, snapshot = held
        if held_depth < depth or clock() - read_at > max_age:
            return None
        return snapshot, held_depth

    def _get(self, topic, depth, max_age, read, shrink):
        hit = self._fresh(topic, depth, max_age)
        if hit is None:
            with self._flight(topic):
                hit = self._fresh(topic, depth, max_age)  # a simultaneous ask may have just read it
                if hit is None:
                    snapshot = read(depth)
                    with self._lock:
                        self._held[topic] = (clock(), depth, snapshot)
                    return snapshot
        snapshot, held_depth = hit
        if shrink is not None and held_depth > depth:
            return shrink(snapshot, depth)
        return snapshot

    def _flight(self, topic: Hashable) -> threading.Lock:
        with self._lock:
            return self._flights.setdefault(topic, threading.Lock())


_feeds: "weakref.WeakKeyDictionary[Any, Feed]" = weakref.WeakKeyDictionary()
_feeds_lock = threading.Lock()


def feed_for(github: Any) -> Feed:
    """The feed of this client: the mod and the workspace get the same client, so the same feed."""
    if github is None:
        return Feed(None)  # nothing to share: every read says the plugin is not available
    with _feeds_lock:
        feed = _feeds.get(github)
        if feed is None:
            feed = _feeds[github] = Feed(github)
        return feed
