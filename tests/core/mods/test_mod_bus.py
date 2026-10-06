from dataclasses import replace

import pytest

from titan_cli.core.mods import ModBus, StepCall
from titan_cli.engine.results import Error, Success


def step_event(**overrides):
    fields = dict(workflow="wf", step_id="push", step_name="Push", plugin="git", step="push", params={"remote": "origin"})
    fields.update(overrides)
    return StepCall(**fields)


class RecordingSink:
    def __init__(self):
        self.statuses = []
        self.toasts = []

    def status(self, mod, text):
        self.statuses.append((mod, text))

    def toast(self, mod, text, severity):
        self.toasts.append((mod, text, severity))


def test_no_hooks_runs_titan_behaviour():
    bus = ModBus()
    assert bus.dispatch("step.call", step_event(), lambda e: Success("ran")).message == "ran"


def test_hook_answers_without_next_and_step_never_runs():
    bus = ModBus()
    on = bus.on_for("guard")

    @on("step.call")
    def deny(m, e, next):
        return m.deny("no pushes today")

    ran = []
    result = bus.dispatch("step.call", step_event(), lambda e: ran.append(e) or Success("ran"))

    assert isinstance(result, Error)
    assert "guard" in result.message and "no pushes today" in result.message
    assert ran == []


def test_hook_rewrites_params_for_the_rest_of_the_chain():
    bus = ModBus()
    on = bus.on_for("rewriter")

    @on("step.call")
    def rewrite(m, e, next):
        return next(replace(e, params={**e.params, "remote": "upstream"}))

    seen = []
    bus.dispatch("step.call", step_event(), lambda e: seen.append(e.params["remote"]) or Success("ok"))

    assert seen == ["upstream"]


def test_hook_observes_the_result():
    bus = ModBus()
    bus.host = sink = RecordingSink()
    on = bus.on_for("watcher")

    @on("step.call")
    def watch(m, e, next):
        result = next(e)
        m.ui.status(f"{e.step_id}: {result.message}")
        return result

    result = bus.dispatch("step.call", step_event(), lambda e: Success("done"))

    assert result.message == "done"
    assert sink.statuses == [("watcher", "push: done")]


def test_hooks_chain_in_load_order():
    bus = ModBus()
    order = []
    for name in ("first", "second"):
        on = bus.on_for(name)

        @on("step.call")
        def hook(m, e, next, name=name):
            order.append(f"{name}:before")
            result = next(e)
            order.append(f"{name}:after")
            return result

    bus.dispatch("step.call", step_event(), lambda e: order.append("step") or Success("ok"))

    assert order == ["first:before", "second:before", "step", "second:after", "first:after"]


def test_matcher_selects_hooks_by_event_fields():
    bus = ModBus()
    on = bus.on_for("guard")

    @on("step.call", match={"plugin": "git", "step": "push"})
    def deny(m, e, next):
        return m.deny("blocked")

    assert isinstance(bus.dispatch("step.call", step_event(), lambda e: Success("ok")), Error)
    other = step_event(plugin="github", step="create_pr")
    assert isinstance(bus.dispatch("step.call", other, lambda e: Success("ok")), Success)


def test_hook_that_raises_before_next_is_skipped():
    bus = ModBus()
    on = bus.on_for("broken")

    @on("step.call")
    def boom(m, e, next):
        raise RuntimeError("bug in mod")

    ran = []
    result = bus.dispatch("step.call", step_event(), lambda e: ran.append(1) or Success("ok"))

    assert result.message == "ok"
    assert ran == [1]


def test_hook_that_raises_after_next_does_not_run_the_step_twice():
    bus = ModBus()
    on = bus.on_for("broken")

    @on("step.call")
    def boom(m, e, next):
        next(e)
        raise RuntimeError("bug after the step")

    ran = []
    result = bus.dispatch("step.call", step_event(), lambda e: ran.append(1) or Success("ok"))

    assert result.message == "ok"
    assert ran == [1]


def test_hook_that_forgets_to_return_keeps_the_result():
    bus = ModBus()
    on = bus.on_for("forgetful")

    @on("step.call")
    def observe(m, e, next):
        next(e)

    assert bus.dispatch("step.call", step_event(), lambda e: Success("ok")).message == "ok"


def test_hook_returning_nothing_without_next_does_not_skip_the_step():
    bus = ModBus()
    on = bus.on_for("forgetful")

    @on("step.call")
    def noop(m, e, next):
        pass

    ran = []
    bus.dispatch("step.call", step_event(), lambda e: ran.append(1) or Success("ok"))

    assert ran == [1]


def test_next_twice_is_refused_and_step_runs_once():
    bus = ModBus()
    on = bus.on_for("greedy")

    @on("step.call")
    def twice(m, e, next):
        next(e)
        return next(e)

    ran = []
    result = bus.dispatch("step.call", step_event(), lambda e: ran.append(1) or Success("ok"))

    assert ran == [1]
    assert result.message == "ok"


def test_unknown_event_is_rejected_at_registration():
    on = ModBus().on_for("typo")
    with pytest.raises(ValueError, match="step.cal"):
        on("step.cal")


def test_event_params_are_read_only():
    with pytest.raises(TypeError):
        step_event().params["remote"] = "x"
