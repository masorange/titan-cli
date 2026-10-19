from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from titan_cli.core.interrupt import WorkflowAborted
from titan_cli.core.mods import ModBus, outcome
from titan_cli.core.workflows import ParsedWorkflow
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Error, Exit, Skip, Success, is_error
from titan_cli.ui.tui.textual_workflow_executor import TextualWorkflowExecutor


def make_executor(mods, steps):
    plugin = MagicMock()
    plugin.get_steps.return_value = steps
    plugin_registry = MagicMock()
    plugin_registry.get_plugin.return_value = plugin
    return TextualWorkflowExecutor(plugin_registry, MagicMock(), message_target=None, mods=mods)


def workflow(*steps):
    return ParsedWorkflow(name="wf", description="", source="test", steps=list(steps), params={})


def test_step_call_hook_blocks_a_step_and_fails_the_workflow():
    bus = ModBus()
    on = bus.on_for("guard")

    @on("step.call", match={"plugin": "git", "step": "push"})
    def guard(m, e, next):
        return m.deny("not on master")

    pushed = MagicMock(return_value=Success("pushed"))
    executor = make_executor(bus, {"push": pushed})

    result = executor.execute(workflow({"id": "push", "plugin": "git", "step": "push"}), WorkflowContext(data={}))

    assert is_error(result)
    pushed.assert_not_called()


def test_step_call_hook_rewrites_params_the_step_sees():
    bus = ModBus()
    on = bus.on_for("rewriter")

    @on("step.call")
    def rewrite(m, e, next):
        return next(replace(e, params={"remote": "upstream"}))

    seen = {}

    def push(ctx):
        seen["remote"] = ctx.data["remote"]
        return Success("pushed")

    executor = make_executor(bus, {"push": push})
    executor.execute(
        workflow({"id": "push", "plugin": "git", "step": "push", "params": {"remote": "origin"}}),
        WorkflowContext(data={}),
    )

    assert seen == {"remote": "upstream"}


def test_workflow_run_hook_sees_start_and_end():
    bus = ModBus()
    on = bus.on_for("timer")
    trace = []

    @on("workflow.run")
    def around(m, e, next):
        trace.append(f"start:{e.workflow}")
        result = next(e)
        trace.append(f"end:{result.message}")
        return result

    executor = make_executor(bus, {"noop": lambda ctx: Success("ok")})
    executor.execute(workflow({"id": "noop", "plugin": "x", "step": "noop"}), WorkflowContext(data={}))

    assert trace == ["start:wf", "end:Workflow 'wf' finished."]


def test_workflow_run_hook_reads_how_the_workflow_ended():
    bus = ModBus()
    on = bus.on_for("watcher")
    ended = []

    @on("workflow.run")
    def around(m, e, next):
        result = next(e)
        ended.append(outcome(result))
        return result

    executor = make_executor(bus, {"ok": lambda ctx: Success("ok"), "boom": lambda ctx: Error("boom")})
    executor.execute(workflow({"id": "ok", "plugin": "x", "step": "ok"}), WorkflowContext(data={}))
    executor.execute(workflow({"id": "boom", "plugin": "x", "step": "boom"}), WorkflowContext(data={}))

    assert ended == ["success", "error"]


def test_an_aborted_workflow_reaches_a_hooks_finally_but_not_the_code_after_next():
    bus = ModBus()
    on = bus.on_for("watcher")
    trace = []

    @on("workflow.run")
    def around(m, e, next):
        try:
            result = next(e)
            trace.append("after next")
            return result
        finally:
            trace.append("finally")

    def aborted(ctx):
        raise WorkflowAborted("user pressed Ctrl+C")

    executor = make_executor(bus, {"stop": aborted})
    with pytest.raises(WorkflowAborted):
        executor.execute(workflow({"id": "stop", "plugin": "x", "step": "stop"}), WorkflowContext(data={}))

    assert trace == ["finally"]


def test_outcome_names_each_result_and_refuses_anything_else():
    assert [outcome(r) for r in (Success("a"), Error("b"), Skip("c"), Exit("d"))] == ["success", "error", "skip", "exit"]
    with pytest.raises(TypeError):
        outcome("ok")


def test_without_mods_the_executor_behaves_as_before():
    executor = make_executor(None, {"noop": lambda ctx: Success("ok")})
    result = executor.execute(workflow({"id": "noop", "plugin": "x", "step": "noop"}), WorkflowContext(data={}))
    assert result.message == "Workflow 'wf' finished."
