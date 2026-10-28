"""Workflow runs as the pane lists them: state, duration and the PR a queue run is for."""
import pytest

from titan_plugin_github.models.formatting import format_duration
from titan_plugin_github.models.mappers import from_rest_workflow_run
from titan_plugin_github.models.network.rest import NetworkWorkflowRun


def network_run(**kw):
    base = dict(id=1, name="build", display_title="feat: x", event="pull_request", status="completed",
                conclusion="success", head_branch="feat/x", html_url="https://github.com/o/r/actions/runs/1",
                created_at="2026-10-28T11:00:00Z", updated_at="2026-10-28T11:02:56Z")
    return NetworkWorkflowRun(**{**base, **kw})


@pytest.mark.parametrize("seconds,expected", [(None, ""), (-1, ""), (45, "45s"), (176, "2m 56s"), (3900, "1h 05m")])
def test_format_duration(seconds, expected):
    assert format_duration(seconds) == expected


@pytest.mark.parametrize("conclusion,state,label", [
    ("success", "success", "passed"), ("failure", "failure", "failed"), ("timed_out", "failure", "timed out"),
    ("cancelled", "cancelled", "cancelled"), ("skipped", "other", "skipped"), (None, "other", "finished"),
])
def test_a_finished_run_maps_its_conclusion(conclusion, state, label):
    run = from_rest_workflow_run(network_run(conclusion=conclusion))

    assert (run.state, run.state_label) == (state, label)


def test_a_run_not_completed_is_running_with_no_duration():
    waiting = from_rest_workflow_run(network_run(status="queued", conclusion=None))
    going = from_rest_workflow_run(network_run(status="in_progress", conclusion=None))

    assert (waiting.state, waiting.state_label, waiting.duration) == ("running", "queued", "")
    assert (going.state, going.state_label) == ("running", "in progress")


def test_only_a_queue_branch_gives_a_pr_number():
    queued = from_rest_workflow_run(network_run(
        event="merge_group", head_branch="gh-readonly-queue/develop/pr-3783-07a8ba11b605a2d25092a8242743244e3206d8a7"))
    plain = from_rest_workflow_run(network_run(head_branch="feat/pr-12-x"))

    assert queued.pr_number == 3783 and queued.is_merge_queue
    assert plain.pr_number is None and not plain.is_merge_queue
