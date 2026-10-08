from rich.text import Text as RichText

from titan_cli.core.mods import AppStart, Box, Button, ModBus, Text, UIRender
from titan_cli.ui.tui.widgets.mod_side_panel import _spread, to_rich


class RecordingHost:
    def __init__(self):
        self.calls = []

    def status(self, mod, text):
        self.calls.append(("status", mod, text))

    def toast(self, mod, text, severity):
        self.calls.append(("toast", mod, text))

    def open_pane(self, mod, pane, title, icon):
        self.calls.append(("open", mod, pane, title))

    def repaint(self, mod):
        self.calls.append(("repaint", mod))

    def every(self, mod, seconds, fn, immediately):
        self.calls.append(("every", mod, seconds, immediately))

    def client(self, name):
        return f"client:{name}"


def test_app_start_and_ui_render_drive_a_pane():
    bus = ModBus()
    bus.host = host = RecordingHost()
    on = bus.on_for("panel")

    @on("app.start")
    def start(m, e, next):
        m.ui.open("p1", "Panel")
        m.clock.every(30, lambda: None)
        return next(e)

    @on("ui.render", match={"component": "Pane", "pane": "p1"})
    def render(m, e, next):
        return Text(f"{m.client('git')} at {e.width}")

    bus.dispatch("app.start", AppStart(project_root="/repo"), lambda e: None)
    tree = bus.dispatch("ui.render", UIRender(component="Pane", pane="p1", width=40), lambda e: None)
    other = bus.dispatch("ui.render", UIRender(component="Pane", pane="p2", width=40), lambda e: None)

    assert host.calls == [("open", "panel", "p1", "Panel"), ("every", "panel", 30, True)]
    assert tree.parts == ("client:git at 40",)
    assert other is None


def test_state_changes_repaint_only_their_mod():
    bus = ModBus()
    bus.host = host = RecordingHost()
    bus.on_for("a")
    bus.on_for("b")
    a = bus._apis["a"]

    a.state.set("count", 1)
    assert a.state.update("count", lambda n: n + 1) == 2
    assert a.state.get("count") == 2
    assert bus._apis["b"].state.get("count", "unset") == "unset"
    assert host.calls == [("repaint", "a"), ("repaint", "a")]


def test_falsy_children_are_dropped_and_lists_flattened():
    box = Box(None, False, "", 0, [], Text("a"), [Text("b"), [None, Text("c")]], border="info")
    assert [c.parts for c in box.children] == [("a",), ("b",), ("c",)]
    assert Text("x", 0 and "never", "y").parts == ("x", "y")


def test_nested_text_spans_inherit_and_override_style():
    rich = to_rich(Text("a", Text("b", color="error"), bold=True))
    assert rich.plain == "ab"
    spans = {rich.plain[s.start:s.end]: s.style for s in rich.spans}
    assert spans["a"].bold and spans["b"].bold
    assert spans["b"].color is not None and spans["a"].color is None


def test_a_row_of_texts_spreads_across_the_width():
    line = _spread([Text("Pull requests"), Text("4 open")], 30)
    assert isinstance(line, RichText)
    assert line.plain == "Pull requests" + " " * 11 + "4 open"


def test_button_keeps_its_callback():
    pressed = []
    button = Button("toggle", lambda: pressed.append(1))
    button.on_press()
    assert pressed == [1]


def test_mod_ai_routes_under_its_own_task():
    from types import SimpleNamespace

    from titan_cli.ai.router import AIExecutionError, AIExecutionSuccess, AIProviderType
    from titan_cli.ui.tui.mods_ui import TitanModHost

    calls = []

    ai_config = object()

    class FakeExecutor:
        def __init__(self):
            self.ai_config = ai_config

        def generate_text(self, prompt, **kwargs):
            calls.append((prompt, kwargs))
            if prompt == "fail":
                return AIExecutionError(error_message="AI is turned off for this task.", error_code="AI_DISABLED")
            return AIExecutionSuccess(decision=SimpleNamespace(model="qwen3-coder"), data="hi")

    bus = ModBus()
    host = TitanModHost(SimpleNamespace(config=SimpleNamespace(config=SimpleNamespace(ai=ai_config))), bus)
    host._executor = FakeExecutor()
    bus.host = host
    bus.on_for("dev")
    m = bus._apis["dev"]

    answer = m.ai.complete("hello", system="be brief", model="opus")
    failed = m.ai.complete("fail")

    policy = calls[0][1]["policy"]
    assert (answer.text, answer.model, answer.ok) == ("hi", "qwen3-coder", True)
    assert (failed.ok, failed.error) == (False, "AI is turned off for this task.")
    assert policy.task == "mods.dev" == m.ai.task
    assert policy.executes == [AIProviderType.REMOTE, AIProviderType.CLI_HEADLESS]
    assert (calls[0][1]["system_prompt"], calls[0][1]["model"]) == ("be brief", "opus")


def test_host_sees_a_mod_task_as_the_ai_screen_does():
    """The routing handed to Titan's task pickers: the mod's task, what it can run, its pins."""
    from types import SimpleNamespace

    from titan_cli.ai.router import AIProviderType
    from titan_cli.core.models import AIConfig, AIPreferences, AIProviderPreference
    from titan_cli.ui.tui.mods_ui import TitanModHost

    ai = AIConfig(default_connection="llm", default_cli="claude", preferences=AIPreferences(
        tasks={"mods.dev": AIProviderPreference(provider="cli_headless", cli="codex", model="o4")}))
    host = TitanModHost(SimpleNamespace(config=SimpleNamespace(config=SimpleNamespace(ai=ai))), ModBus())

    class FakeExecutor:
        ai_config = ai

        def resolve(self, policy):
            return "resolved:" + policy.task

    host._executor = FakeExecutor()
    routing = host._task_routing("dev", "Dev diagnosis")

    assert (routing.task, routing.label, routing.resolution) == ("mods.dev", "Dev diagnosis", "resolved:mods.dev")
    assert routing.executes == [AIProviderType.REMOTE, AIProviderType.CLI_HEADLESS]
    assert (routing.pinned_cli, routing.pinned_model, routing.has_preference) == ("codex", "o4", True)
    assert host.ai_pinned("dev") == "cli:codex"


def test_mod_ai_follows_a_reloaded_config(monkeypatch):
    """TitanConfig.load() replaces the AI config on every screen change; a pin saved since must be seen."""
    from types import SimpleNamespace

    import titan_cli.ai.router as router
    from titan_cli.ui.tui.mods_ui import TitanModHost

    built = []

    class RecordingExecutor:
        def __init__(self, ai_config, **kwargs):
            self.ai_config = ai_config
            built.append(ai_config)

    monkeypatch.setattr(router, "AIExecutor", RecordingExecutor)
    first, reloaded = object(), object()
    config = SimpleNamespace(config=SimpleNamespace(ai=first))
    host = TitanModHost(SimpleNamespace(config=config), ModBus())

    host._ai_executor()
    host._ai_executor()
    config.config = SimpleNamespace(ai=reloaded)
    executor = host._ai_executor()

    assert built == [first, reloaded]
    assert executor.ai_config is reloaded


def test_ai_screen_lists_only_mods_that_declare_an_ai_task():
    from types import SimpleNamespace

    from titan_cli.core.models import AIConfig
    from titan_cli.ui.tui.mods_ui import TitanModHost
    from titan_cli.ui.tui.screens.ai_routing import TaskRoutingRow

    bus = ModBus()
    bus.manifests = {"dev": SimpleNamespace(ai_task="Dev diagnosis"), "clock": SimpleNamespace(ai_task=None)}
    host = TitanModHost(SimpleNamespace(config=SimpleNamespace(config=SimpleNamespace(ai=AIConfig()))), bus)

    class FakeExecutor:
        ai_config = host._ai_config()

        def resolve(self, policy):
            return None

    host._executor = FakeExecutor()
    [routing] = host.ai_routings()

    assert (routing.task, routing.label, routing.mod) == ("mods.dev", "Dev diagnosis", "dev")
    assert TaskRoutingRow._usage_summary(SimpleNamespace(routing=routing)) == "used by mod dev"


def test_a_dragged_panel_stays_between_its_minimum_and_the_room_the_screen_needs():
    from titan_cli.ui.tui.widgets.mod_side_panel import MIN_MAIN_WIDTH, MIN_PANEL_WIDTH, clamp_panel_width

    assert clamp_panel_width(70, 200) == 70
    assert clamp_panel_width(5, 200) == MIN_PANEL_WIDTH
    assert clamp_panel_width(190, 200) == 200 - MIN_MAIN_WIDTH
    assert clamp_panel_width(60, 50) == MIN_PANEL_WIDTH  # a tiny terminal still gets a usable panel


def _host_with_panes(*panes):
    from titan_cli.ui.tui.mods_ui import TitanModHost

    host = TitanModHost(app=None, bus=ModBus())
    host.repaint = lambda mod: None
    for pane in panes:
        host.open_pane("m", pane, pane.title(), None)
    return host


def test_the_first_pane_opened_is_the_one_shown_and_gets_its_initial_as_icon():
    host = _host_with_panes("jira", "git")

    assert host.active == "jira"
    assert host.panes["git"] == ("m", "Git", "G")


def test_clicking_the_shown_pane_folds_the_panel_and_another_switches_to_it():
    host = _host_with_panes("jira", "git")

    host.select("jira")
    assert (host.active, host.collapsed) == ("jira", True)
    host.select("git")
    assert (host.active, host.collapsed) == ("git", False)
    host.select("unknown")
    assert (host.active, host.collapsed) == ("git", False)


def test_a_pane_takes_its_rail_icon_from_the_mod_manifest(tmp_path):
    from titan_cli.core.mods import discover_mods, load_mods

    folder = tmp_path / "jira"
    folder.mkdir()
    (folder / "mod.toml").write_text('[mod]\nname = "jira"\nicon = "🎫"\n')
    (folder / "mod.py").write_text(
        'def register(on, options):\n'
        '    @on("app.start")\n'
        '    def start(m, e, next):\n'
        '        m.ui.open("p", "Jira")\n'
        '        return next(e)\n'
    )
    bus = ModBus()
    opened = []
    bus.host = type("H", (RecordingHost,), {"open_pane": lambda self, *a: opened.append(a)})()
    load_mods(bus, discover_mods([("user", tmp_path)]))

    bus.dispatch("app.start", AppStart(project_root="/repo"), lambda e: None)

    assert opened == [("jira", "p", "Jira", "🎫")]
