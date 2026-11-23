"""The feed: one read per topic and period, however many views ask, and only of what is asked."""
import threading
import time
from types import SimpleNamespace

import pytest

from titan_cli.core.result import ClientSuccess
from titan_plugin_github.readers import feed as feed_module
from titan_plugin_github.readers.feed import Feed, feed_for


class Client(SimpleNamespace):
    """A fake client that, like the real one, takes a weak reference (the feed is keyed on it)."""

    __hash__ = object.__hash__


@pytest.fixture
def now(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(feed_module, "clock", lambda: t[0])
    return t


def _github(reads, delay=0.0):
    def runs(trigger=None, limit=10):
        reads.append(("runs", trigger, limit))
        time.sleep(delay)
        return ClientSuccess(data=list(range(limit)))
    return Client(list_workflow_runs=runs, invalidate_reads=lambda: reads.append("invalidated"))


def test_an_answer_younger_than_the_period_is_reused_and_an_older_one_is_not(now):
    reads = []
    feed = Feed(_github(reads))
    feed.runs(None, 10, max_age=30)
    now[0] += 29
    feed.runs(None, 10, max_age=30)
    assert len(reads) == 1
    now[0] += 2
    feed.runs(None, 10, max_age=30)
    assert len(reads) == 2


def test_a_deeper_read_serves_a_shallower_ask_but_not_the_reverse(now):
    reads = []
    feed = Feed(_github(reads))
    feed.runs(None, 20, max_age=30)
    shallow = feed.runs(None, 5, max_age=30)
    assert len(reads) == 1 and len(shallow.runs) == 5 and shallow.limit == 5
    feed.runs(None, 30, max_age=30)
    assert reads[-1] == ("runs", None, 30)


def test_each_trigger_is_its_own_topic(now):
    reads = []
    feed = Feed(_github(reads))
    feed.runs(None, 10, max_age=30)
    feed.runs("merge_group", 10, max_age=30)
    assert [r[1] for r in reads] == [None, "merge_group"]


def test_refresh_forgets_one_topic_and_the_clients_cache(now):
    reads = []
    feed = Feed(_github(reads))
    feed.runs(None, 10, max_age=30)
    feed.runs("merge_group", 10, max_age=30)
    feed.refresh(("runs", "merge_group"))
    feed.runs(None, 10, max_age=30)
    feed.runs("merge_group", 10, max_age=30)
    assert reads == [("runs", None, 10), ("runs", "merge_group", 10), "invalidated", ("runs", "merge_group", 10)]


def test_simultaneous_asks_cost_one_read():
    reads = []
    feed = Feed(_github(reads, delay=0.05))
    threads = [threading.Thread(target=feed.runs, args=(None, 10, 30)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(reads) == 1


def test_the_same_client_gets_the_same_feed():
    github = Client()
    assert feed_for(github) is feed_for(github)
    assert feed_for(github) is not feed_for(Client())
