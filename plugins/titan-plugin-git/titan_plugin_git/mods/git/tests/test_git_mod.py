"""The git mod: its reading and drawing are plain functions over a fake client."""
from types import SimpleNamespace

import pytest


def test_draw_shows_branch_and_commits(mod, flatten):
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x", has_upstream=True, ahead=1, added=4, commits=[
        SimpleNamespace(short_hash="abc", message_subject="feat: y (#9)", pr_number=9, formatted_date="today"),
    ]))

    lines = flatten(mod.draw.draw(m, 44))

    assert lines[0] == "⎇ feat/x ↑1 ↓0 +4"
    assert "▸ #9 feat: y" in lines


def test_a_branch_without_upstream_says_so(mod, flatten):
    from titan_cli.core.mods import ModBus

    m = ModBus().api("git")
    m.state.set("repo", mod.models.Repo(branch="feat/x"))
    assert flatten(mod.draw.draw(m, 44))[0] == "⎇ feat/x no upstream"


def test_refresh_key_is_bound_at_start_and_refreshes_the_repo(mod, tmp_path):
    from titan_cli.core.mods import AppStart, ModBus

    keys, runs = {}, []
    host = SimpleNamespace(
        open_pane=lambda *a: None, every=lambda *a: None, repaint=lambda mod: None,
        run=lambda mod, fn: runs.append(fn), client=lambda name: None,
        bind_key=lambda mod, key, description, fn: keys.setdefault(key, (description, fn)) and None,
    )
    bus = ModBus()
    bus.host = host
    options = {"repo_refresh_seconds": 30, "refresh_key": "f5", "recent_commits": 10}
    mod.register(bus.on_for("git"), options)

    bus.dispatch("app.start", AppStart(project_root=str(tmp_path)), lambda e: None)
    assert list(keys) == ["f5"] and keys["f5"][0] == "Refresh status"

    runs.clear()
    keys["f5"][1]()
    assert len(runs) == 1  # the refresh goes off the UI thread
    runs[0]()
    state = bus.api("git").state
    assert state.get("repo").error == "git plugin not available"


def test_a_finished_or_aborted_workflow_refreshes_off_its_thread(mod, tmp_path):
    from titan_cli.core.mods import AppStart, ModBus, WorkflowRun

    runs = []
    host = SimpleNamespace(
        open_pane=lambda *a: None, every=lambda *a: None, repaint=lambda mod: None,
        run=lambda mod, fn: runs.append(fn), client=lambda name: None, bind_key=lambda *a: None,
    )
    bus = ModBus()
    bus.host = host
    mod.register(bus.on_for("git"), {"repo_refresh_seconds": 30, "refresh_key": "", "recent_commits": 10})
    bus.dispatch("app.start", AppStart(project_root=str(tmp_path)), lambda e: None)
    state = bus.api("git").state
    runs.clear()

    bus.dispatch("workflow.run", WorkflowRun("review-pr", "plugin", nested=True), lambda e: None)
    assert runs == [] and state.get("repo") is None  # a nested workflow is part of its parent

    bus.dispatch("workflow.run", WorkflowRun("review-pr", "plugin", nested=False), lambda e: None)
    assert state.get("repo") is None  # not on the workflow's thread
    runs[-1]()
    assert state.get("repo") is not None

    runs.clear()

    def aborted(e):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        bus.dispatch("workflow.run", WorkflowRun("review-pr", "plugin", nested=False), aborted)
    assert len(runs) == 1  # an aborted run refreshes too
