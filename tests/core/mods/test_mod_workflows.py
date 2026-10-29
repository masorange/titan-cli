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


class AssistApp(FakeApp):
    """An app that can suspend and says which CLI the assistant resolves to."""

    def __init__(self):
        super().__init__()
        self.suspended = 0

    def suspend(self):
        app = self

        class Ctx:
            def __enter__(self_inner):
                app.suspended += 1

            def __exit__(self_inner, *exc):
                return False

        return Ctx()

    def model_for_cli(self, cli):
        return "opus"


def assist_host(monkeypatch, app, decision):

    launched = []
    bus = ModBus()
    host = TitanModHost(app, bus)
    bus.host = host
    asked = []
    monkeypatch.setattr(host, "_ai_executor", lambda: SimpleNamespace(resolve=lambda policy: asked.append(policy.task) or decision))
    monkeypatch.setattr("titan_cli.external_cli.launcher.launcher_for",
                        lambda cli: SimpleNamespace(launch=lambda **kw: launched.append((cli, kw)) or 0))
    return bus.api("github"), launched, asked


def test_assist_suspends_titan_and_launches_the_resolved_interactive_cli(monkeypatch):
    from titan_cli.ai.router import AIProviderType, AIRouteDecision

    app = AssistApp()
    decision = AIRouteDecision(provider=AIProviderType.CLI_INTERACTIVE, cli="claude")
    m, launched, asked = assist_host(monkeypatch, app, decision)

    assert m.ai.assist("fix this", cwd="/repo").opened is True
    assert asked == ["mods.github.assist"]

    assert app.suspended == 1
    assert launched == [("claude", {"prompt": "fix this", "cwd": "/repo", "model": "opus"})]


def test_assist_refuses_with_a_toast_when_nothing_interactive_resolves(monkeypatch):
    from titan_cli.ai.router import AIRouteNeedsInput

    app = AssistApp()
    m, launched, _ = assist_host(monkeypatch, app, AIRouteNeedsInput(reason="no interactive CLI is installed", candidates=[]))

    result = m.ai.assist("fix this")

    assert result.opened is False and "no interactive CLI" in result.reason
    assert launched == [] and app.suspended == 0
    assert any("no interactive CLI" in text for text, _ in app.notices)


def test_assist_refuses_a_task_the_user_pinned_to_something_that_is_not_interactive(monkeypatch):
    from titan_cli.ai.router import AIProviderType, AIRouteDecision

    app = AssistApp()
    m, launched, _ = assist_host(monkeypatch, app, AIRouteDecision(provider=AIProviderType.REMOTE, connection_id="work"))

    assert m.ai.assist("fix this").opened is False
    assert launched == [] and app.suspended == 0
    assert any("interactive CLI" in text for text, _ in app.notices)


def test_the_help_task_offers_only_the_interactive_cli_and_the_complete_task_never_does():
    from titan_cli.ai.router import AIProviderType

    assist, complete = TitanModHost._assist_policy("github"), TitanModHost._policy("github")

    assert assist.task == "mods.github.assist" and assist.executes == [AIProviderType.CLI_INTERACTIVE]
    assert AIProviderType.CLI_INTERACTIVE not in complete.executes


def test_every_mod_ai_request_is_logged_without_its_prompt(monkeypatch):
    from titan_cli.ai.router import AIExecutionError, AIExecutionSuccess, AIProviderType, AIRouteDecision

    decision = AIRouteDecision(provider=AIProviderType.CLI_HEADLESS, cli="opencode", model="gpt-oss")
    results = [AIExecutionSuccess(decision=decision, data="a name"),
               AIExecutionError(error_message="model not found", error_code="EXECUTION_FAILED", decision=decision)]
    bus = ModBus()
    host = TitanModHost(AssistApp(), bus)
    monkeypatch.setattr(host, "_ai_executor", lambda: SimpleNamespace(generate_text=lambda *a, **k: results.pop(0)))
    logged = []
    monkeypatch.setattr(
        "titan_cli.ui.tui.mods_ui.logger",
        SimpleNamespace(info=lambda e, **kw: logged.append((e, kw)), warning=lambda e, **kw: logged.append((e, kw))),
    )

    assert host.ai("git", "a secret prompt", None, 60, None, 30).text == "a name"
    assert host.ai("git", "a secret prompt", None, 60, None, 30).error == "model not found"

    (ok, ok_fields), (bad, bad_fields) = logged
    assert (ok, ok_fields["task"], ok_fields["cli"], ok_fields["model"]) == ("mod_ai_answered", "mods.git", "opencode", "gpt-oss")
    assert (bad, bad_fields["error_code"], bad_fields["error"]) == ("mod_ai_refused_or_failed", "EXECUTION_FAILED", "model not found")
    assert "secret" not in str(logged)
