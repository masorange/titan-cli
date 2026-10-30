"""The jira_ready pane: the issues assigned to you, each one opening the jira workspace on it."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from titan_cli.core.mods import ModBus, UIRender
from titan_cli.core.mods.loader import import_mod
from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.ui.elements import Button, plain
from titan_plugin_jira.models import UIJiraIssue
from titan_plugin_jira.readers import issues as reader
from titan_plugin_jira.readers.models import Ready

mod = import_mod(Path(__file__).parent, "jira_ready")
OPTIONS = {"project": "", "shown": 20, "refresh_seconds": 300}


def issue(key="PROJ-1") -> UIJiraIssue:
    return UIJiraIssue(
        key=key, id="1", summary="Do it", description="", status="In Progress", status_icon="🟡",
        status_category="In Progress", issue_type="Task", issue_type_icon="✅", assignee="ANA", assignee_email=None,
        reporter="", priority="High", priority_icon="🔴", formatted_created_at="", formatted_updated_at="",
        labels=[], components=[], fix_versions=[], is_subtask=False, parent_key=None, subtask_count=0,
    )


def buttons(element):
    if isinstance(element, Button):
        yield element
    for child in getattr(element, "children", ()) or ():
        if child:
            yield from buttons(child)


def test_read_mine_asks_for_unfinished_issues_assigned_to_the_user_in_the_projects():
    jira = Mock(project_key="PROJ")
    jira.issue_url.return_value = "u"
    jira.search_issues.return_value = ClientSuccess(data=[issue(), issue("PROJ-2")])

    ready = reader.read_mine(jira, ["PROJ"], 1)

    query = jira.search_issues.call_args.args[0]
    assert 'project = "PROJ"' in query and "assignee = currentUser()" in query and "statusCategory != Done" in query
    assert jira.search_issues.call_args.kwargs["max_results"] == 2
    assert [i.key for i in ready.issues] == ["PROJ-1"] and ready.more


def test_read_mine_reports_a_failed_search_and_a_missing_plugin():
    jira = Mock(project_key="PROJ")
    jira.search_issues.return_value = ClientError(error_message="HTTP 401")

    assert reader.read_mine(jira, [], 5).error == "HTTP 401"
    assert "not available" in reader.read_mine(None, [], 5).error


def test_pressing_an_issue_opens_the_workspace_on_it_and_the_button_opens_it_plain():
    opened = []
    bus = ModBus()
    bus.host = SimpleNamespace(open_workspace=lambda mod, name, focus=None: opened.append((name, focus)),
                               repaint=lambda mod: None)
    m = bus.api("jira_ready")
    m.state.set("ready", Ready("q", [issue()], "PROJ"))
    mod.register(bus.on_for("jira_ready"), OPTIONS)

    tree = bus.dispatch("ui.render", UIRender(component="Pane", pane=mod.PANE, width=40), lambda e: None)
    by_label = {plain(b.label): b for b in buttons(tree)}

    by_label["🟡 PROJ-1 Do it"].on_press()
    by_label["Open Jira workspace"].on_press()
    assert opened == [("jira", {"issue": "PROJ-1"}), ("jira", None)]


def test_a_failed_read_is_an_error_card_and_nothing_assigned_says_all_clear():
    m = ModBus().api("jira_ready")
    m.state.set("ready", Ready("q", [], error="HTTP 500"))
    assert mod.draw(m, OPTIONS).children[0].border == "error"

    m.state.set("ready", Ready("q", []))
    assert any("Nothing assigned" in str(getattr(c, "parts", "")) for c in mod.draw(m, OPTIONS).children)


def test_the_error_card_retries_the_read_off_the_ui_thread():
    runs = []
    jira = Mock(project_key="PROJ")
    jira.issue_url.return_value = "u"
    jira.search_issues.return_value = ClientSuccess(data=[issue()])
    bus = ModBus()
    bus.host = SimpleNamespace(run=lambda mod, fn: runs.append(fn), client=lambda name: jira, repaint=lambda mod: None)
    m = bus.api("jira_ready")
    m.state.set("ready", Ready("q", [], error="HTTP 500"))

    next(b for b in buttons(mod.draw(m, OPTIONS)) if b.label == "↻ Retry").on_press()
    assert m.state.get("ready").error == "HTTP 500"
    runs.pop()()

    assert [i.key for i in m.state.get("ready").issues] == ["PROJ-1"]
