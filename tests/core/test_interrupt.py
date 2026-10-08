"""Tests for cooperative interruption of blocking workflow calls."""

import contextvars
import threading
import time

import pytest

from titan_cli.core.interrupt import (
    WorkflowAborted,
    abort_requested,
    clear_abort_check,
    run_interruptible,
    set_abort_check,
)


@pytest.fixture(autouse=True)
def _clean_abort_check():
    clear_abort_check()
    yield
    clear_abort_check()


class TestWithoutAbortCheck:
    def test_runs_inline_and_returns_result(self):
        assert run_interruptible(lambda: 42) == 42

    def test_propagates_exception(self):
        with pytest.raises(ValueError, match="boom"):
            run_interruptible(lambda: (_ for _ in ()).throw(ValueError("boom")))

    def test_abort_requested_is_false(self):
        assert abort_requested() is False


class TestWithAbortCheck:
    def test_returns_result_when_not_aborted(self):
        set_abort_check(lambda: False)
        assert run_interruptible(lambda: "ok") == "ok"

    def test_propagates_exception_when_not_aborted(self):
        set_abort_check(lambda: False)

        def fail():
            raise RuntimeError("provider down")

        with pytest.raises(RuntimeError, match="provider down"):
            run_interruptible(fail)

    def test_raises_workflow_aborted_while_call_is_blocked(self):
        aborted = threading.Event()
        set_abort_check(aborted.is_set)

        release = threading.Event()

        def blocking_call():
            release.wait(timeout=30)
            return "too late"

        aborted.set()
        started = time.monotonic()
        with pytest.raises(WorkflowAborted):
            run_interruptible(blocking_call)
        # It escaped by polling, not by waiting the call out.
        assert time.monotonic() - started < 5
        release.set()

    def test_workflow_aborted_is_not_an_exception_subclass(self):
        # Transports and the step loop catch `Exception` broadly; an abort must
        # pass through those handlers untouched.
        assert not issubclass(WorkflowAborted, Exception)
        assert issubclass(WorkflowAborted, BaseException)

    def test_failing_check_counts_as_abort(self):
        def broken_check():
            raise RuntimeError("app torn down")

        set_abort_check(broken_check)
        assert abort_requested() is True


class TestContextPropagation:
    """A blocking call must not lose the context it was made from.

    `run_interruptible` moves the call onto a daemon thread, and a bare thread starts
    with an EMPTY context — which silently stripped the log's run id from every AI call
    in a review, since they all go through here. Measured 2026-09-22: 3,573
    `findings_batch_adapter_call` events and every `ai_call_cost` event had no `run`
    field. Cost that cannot be attributed to a run cannot be compared between runs,
    which was the whole point of recording it.
    """

    def test_a_contextvar_set_by_the_caller_is_visible_inside(self):
        set_abort_check(lambda: False)
        marker = contextvars.ContextVar("marker", default="unset")
        marker.set("set-by-caller")

        assert run_interruptible(marker.get) == "set-by-caller"

    def test_it_still_propagates_when_running_inline(self):
        """With no abort check the call runs inline, which must behave the same."""
        clear_abort_check()
        marker = contextvars.ContextVar("marker_inline", default="unset")
        marker.set("set-by-caller")

        assert run_interruptible(marker.get) == "set-by-caller"

    def test_a_binding_made_inside_does_not_leak_back_to_the_caller(self):
        """The thread gets a COPY, so the caller's context is left as it was."""
        set_abort_check(lambda: False)
        marker = contextvars.ContextVar("marker_leak", default="unset")
        marker.set("caller")

        run_interruptible(lambda: marker.set("inside"))

        assert marker.get() == "caller"
