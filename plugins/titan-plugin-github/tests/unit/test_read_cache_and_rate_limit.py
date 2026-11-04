import time
from unittest.mock import patch

import pytest

from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_github.clients.network import rate_limit
from titan_plugin_github.clients.services.read_cache import ReadCache, cached_read


class Service:
    def __init__(self):
        self._reads = ReadCache(ttl=60)
        self.calls = 0

    @cached_read
    def read(self, n):
        self.calls += 1
        return ClientSuccess(data=n) if n >= 0 else ClientError(error_message="no")


def test_a_repeated_read_is_answered_from_the_first():
    s = Service()
    s.read(1)
    s.read(1)
    s.read(2)
    assert s.calls == 2


def test_errors_are_not_kept():
    s = Service()
    s.read(-1)
    s.read(-1)
    assert s.calls == 2


def test_invalidate_forgets_everything():
    s = Service()
    s.read(1)
    s._reads.invalidate()
    s.read(1)
    assert s.calls == 2


def test_an_old_entry_is_not_served():
    cache = ReadCache(ttl=0.01)
    cache.put("k", 1)
    time.sleep(0.03)
    assert cache.get("k") is None


@pytest.fixture(autouse=True)
def _reset_pause():
    rate_limit.clear()
    yield
    rate_limit.clear()


def test_a_rate_limit_pauses_calls_until_it_resets():
    with patch.object(rate_limit, "_reset_time", return_value=time.time() + 600):
        rate_limit.start_pause()
    assert "paused until" in rate_limit.paused_message()


def test_without_a_reset_time_the_pause_falls_back():
    with patch.object(rate_limit, "_reset_time", return_value=None):
        rate_limit.start_pause()
    assert rate_limit.paused_message() is not None


def test_no_pause_means_calls_go_out():
    assert rate_limit.paused_message() is None


def test_rate_limit_text_is_recognised():
    assert rate_limit.is_rate_limit("GraphQL: API rate limit already exceeded for user ID 1.")
    assert not rate_limit.is_rate_limit("not found")
