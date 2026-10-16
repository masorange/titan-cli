import threading
from types import SimpleNamespace

from titan_cli.core.mods import ModBus
from titan_cli.ui.tui.mods_ui import TitanModHost
from titan_cli.ui.tui.screens.workflow_execution import WorkflowExecutionScreen


class FakeApp:
    """What the host reads of the app, without starting Textual."""

    def __init__(self, workflows=("review-pr",), screens=()):
        self._thread_id = threading.get_ident()
        self.is_running = True
        self.config = SimpleNamespace(
            workflows=SimpleNamespace(get_workflow=lambda name: object() if name in workflows else None),
            is_favorite_workflow=lambda name: False,
        )
        self.screen_stack = list(screens)
        self.pushed = []
        self.notices = []

    def push_screen(self, screen):
        self.pushed.append(screen)

    def notify(self, text, severity="information", **_):
        self.notices.append((text, severity))


def workflows_of(app):
    bus = ModBus()
    bus.host = TitanModHost(app, bus)
    return bus.api("git").workflows


def test_a_mod_opens_a_workflow_with_its_params_over_the_workflow_ones():
    app = FakeApp()

    assert workflows_of(app).run("review-pr", {"review_pr_number": 42}) is True

    [screen] = app.pushed
    assert isinstance(screen, WorkflowExecutionScreen)
    assert screen.workflow_name == "review-pr"
    assert screen.params == {"review_pr_number": 42}


def test_a_workflow_is_not_opened_over_one_that_is_running():
    app = FakeApp(screens=[object.__new__(WorkflowExecutionScreen)])

    assert workflows_of(app).run("review-pr", {"review_pr_number": 42}) is False
    assert app.pushed == []
    assert "another workflow is running" in app.notices[0][0]


def test_an_unknown_workflow_is_refused_with_a_toast():
    app = FakeApp()

    assert workflows_of(app).run("nope") is False
    assert app.pushed == [] and "no workflow 'nope'" in app.notices[0][0]


def test_without_a_tui_a_workflow_never_opens():
    assert ModBus().api("git").workflows.run("review-pr") is False
