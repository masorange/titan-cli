import pytest

from rich.console import Console
from rich.text import Text as RichText

from titan_cli.core.mods import AppStart, ModBus, UIRender
from titan_cli.ui.elements import Box, Button, Text
from titan_cli.ui.tui.widgets.element_text import to_rich
from titan_cli.ui.tui.widgets.element_widgets import _spread


class RecordingHost:
    def __init__(self):
        self.calls = []

    def status(self, mod, text):
        self.calls.append(("status", mod, text))

    def toast(self, mod, text, severity):
        self.calls.append(("toast", mod, text))

    def open_pane(self, mod, pane, title, icon):
        self.calls.append(("open", mod, pane, title))

    def badge(self, mod, pane, text, severity):
        self.calls.append(("badge", mod, pane, text, severity))

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
    a = bus.api("a")

    a.state.set("count", 1)
    assert a.state.update("count", lambda n: n + 1) == 2
    assert a.state.get("count") == 2
    assert bus.api("b").state.get("count", "unset") == "unset"
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
    m = bus.api("dev")

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

    assert (routing.task, routing.label, routing.mods) == ("mods.dev", "Dev diagnosis", ["dev"])
    assert TaskRoutingRow._usage_summary(SimpleNamespace(routing=routing)) == "used by mod dev"


def test_a_mod_that_declares_an_assist_task_gets_a_second_row_of_its_own():
    from types import SimpleNamespace

    from titan_cli.ai.router import AIProviderType
    from titan_cli.core.models import AIConfig
    from titan_cli.ui.tui.mods_ui import TitanModHost

    bus = ModBus()
    bus.manifests = {
        "dev": SimpleNamespace(ai_task="Dev diagnosis", ai_assist_task="Fix with AI"),
        "help": SimpleNamespace(ai_task=None, ai_assist_task="Help"),
    }
    host = TitanModHost(SimpleNamespace(config=SimpleNamespace(config=SimpleNamespace(ai=AIConfig()))), bus)

    class FakeExecutor:
        ai_config = host._ai_config()

        def resolve(self, policy):
            return None

    host._executor = FakeExecutor()
    rows = {r.task: r for r in host.ai_routings()}

    assert set(rows) == {"mods.dev", "mods.dev.assist", "mods.help.assist"}
    assert rows["mods.dev.assist"].label == "Fix with AI" and rows["mods.dev.assist"].mods == ["dev"]
    assert rows["mods.dev.assist"].executes == [AIProviderType.CLI_INTERACTIVE]
    assert AIProviderType.CLI_INTERACTIVE not in rows["mods.dev"].executes


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


def test_the_panel_starts_closed_and_opens_when_the_person_picks_a_pane():
    host = _host_with_panes("jira", "git")

    assert host.collapsed
    host.select("git")
    assert (host.active, host.collapsed) == ("git", False)


def test_clicking_the_shown_pane_folds_the_panel_and_another_switches_to_it():
    host = _host_with_panes("jira", "git")

    host.select("jira")
    assert (host.active, host.collapsed) == ("jira", False)
    host.select("jira")
    assert (host.active, host.collapsed) == ("jira", True)
    host.select("git")
    assert (host.active, host.collapsed) == ("git", False)
    host.select("unknown")
    assert (host.active, host.collapsed) == ("git", False)


def test_a_badge_sits_under_its_own_panes_rail_icon_and_none_takes_it_off():
    host = _host_with_panes("git")

    host.badge("m", "git", "2", "warning")
    assert host.badges["git"] == ("2", "warning")
    host.badge("m", "git", None, None)
    assert "git" not in host.badges


def test_a_mod_cannot_badge_a_pane_it_did_not_open():
    host = _host_with_panes("git")

    host.badge("other", "git", "9", "error")
    host.badge("m", "unknown", "9", "error")

    assert host.badges == {}


def test_m_ui_badge_names_the_mod_and_its_pane():
    bus = ModBus()
    bus.host = host = RecordingHost()

    bus.api("git").ui.badge("git", "2", severity="warning")

    assert host.calls == [("badge", "git", "git", "2", "warning")]


def test_the_rail_shows_the_badge_under_the_icon_cut_to_fit():
    from titan_cli.ui.tui.widgets.mod_side_panel import rail_text

    assert rail_text("⎇", None).plain == "\n⎇\n"
    text = rail_text("⎇", ("1234", "warning"))
    assert text.plain == "\n⎇\n123"
    assert "bold" in str(text.spans[0].style)


def test_a_pane_takes_its_rail_icon_from_the_mod_manifest(tmp_path):
    from titan_cli.core.mods import discover_mods, load_mods

    folder = tmp_path / "jira"
    folder.mkdir()
    (folder / "mod.toml").write_text('[mod]\nname = "jira"\nicon = "🎫"\nevents = ["app.start"]\n')
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


def test_a_link_is_underlined_and_a_click_opens_its_url():
    from titan_cli.ui.elements import Link

    line = to_rich(Text(Link("#12", "https://github.com/o/r/pull/12"), " fix it"))

    assert line.plain == "#12 fix it"
    [span] = [span for span in line.spans if span.style.meta]
    assert (span.start, span.end) == (0, 3)
    assert span.style.underline
    assert span.style.meta == {"@click": "open_link('https://github.com/o/r/pull/12')"}


def test_only_web_links_open():
    from types import SimpleNamespace

    from titan_cli.ui.tui.widgets.element_text import Line as _Line

    opened = []
    line = _Line("")
    app = SimpleNamespace(open_url=opened.append)
    type(line).app = property(lambda self: app)
    try:
        line.action_open_link("https://jira.example.com/browse/X-1")
        line.action_open_link("file:///etc/passwd")
    finally:
        del type(line).app
    assert opened == ["https://jira.example.com/browse/X-1"]


def test_a_button_with_a_variant_is_drawn_as_titans_button():
    from titan_cli.ui.tui.widgets.button import Button as TitanButton
    from titan_cli.ui.tui.widgets.element_widgets import kind
    from titan_cli.ui.tui.widgets.pressable_row import PressableRow

    assert kind(Button("▸ fold", lambda: None)) is PressableRow
    assert kind(Button("Review #5", lambda: None, variant="primary")) is TitanButton
    assert TitanButton._variant("loud") == "default"


def test_a_url_in_plain_text_is_one_link_however_it_wraps():
    from titan_cli.ui.tui.widgets.element_text import with_urls

    url = "https://www.figma.com/design/nTUhkbEFwF4V/Home?node-id=1-2"
    text = with_urls(f"Design ({url}). Rest")

    assert text.plain == f"Design ({url}). Rest"
    linked = [text.plain[span.start:span.end] for span in text.spans if span.style.meta.get("@click")]
    assert linked == [url]
    rows = to_rich(Text(f"See {url}", wrap=True)).wrap(Console(width=20), 20)
    assert {span.style.meta["@click"] for row in rows for span in row.spans if span.style.meta.get("@click")} == {f"open_link({url!r})"}


def test_unloading_a_mod_takes_its_timers_keys_panes_badges_and_dock_tile_off_the_host():
    import threading
    from types import SimpleNamespace

    from titan_cli.core.mods.bus import DockSlot
    from titan_cli.ui.tui.mods_ui import TitanModHost

    stopped, cancelled, bindings = [], [], {"f5": object(), "f6": object()}
    app = SimpleNamespace(
        _thread_id=threading.get_ident(), is_running=True,
        set_interval=lambda seconds, fn: SimpleNamespace(stop=lambda: stopped.append(seconds)),
        workers=SimpleNamespace(cancel_group=lambda node, group: cancelled.append(group)),
        _bindings=SimpleNamespace(key_to_bindings=bindings),
        screen=SimpleNamespace(query_one=lambda *a: (_ for _ in ()).throw(LookupError())),
    )
    host = TitanModHost(app=app, bus=ModBus())
    host.repaint = lambda mod: None
    host.every("git", 30, lambda: None, immediately=False)
    host.every("git", 60, lambda: None, immediately=False)
    host.every("other", 5, lambda: None, immediately=False)
    host._keys.update({"f5": ("git", "Refresh", lambda: None), "f6": ("other", "Other", lambda: None)})
    host.open_pane("git", "git", "Git", None)
    host.open_pane("other", "other", "Other", None)
    host.badge("git", "git", "2", "warning")
    host.dock("git", DockSlot("Git"))

    host.unload("git")

    assert stopped == [30, 60] and cancelled == ["mod:git"]
    assert list(host._keys) == ["f6"] and list(bindings) == ["f6"]
    assert list(host.panes) == ["other"] and host.active == "other" and host.badges == {}
    assert host.dock_slots() == []


def test_pane_snapshot_is_a_copy_the_mods_cannot_change_under_the_reader():
    from types import SimpleNamespace

    from titan_cli.core.mods import ModBus
    from titan_cli.ui.tui.mods_ui import TitanModHost

    app = SimpleNamespace(is_running=False)
    host = TitanModHost(app, ModBus())
    host._on_app_thread = lambda fn: True
    host.open_pane("m", "git", "Git")

    panes, badges = host.pane_snapshot()
    host.open_pane("m", "other", "Other")

    assert list(panes) == ["git"] and badges == {}
    assert list(host.panes) == ["git", "other"]


def test_ai_assist_in_the_headless_host_refuses_instead_of_opening_anything():
    from titan_cli.core.mods import ModBus

    assert ModBus().api("dev").ai.assist("fix this").opened is False


def test_every_widget_that_holds_an_element_is_updatable():
    from titan_cli.ui.tui.widgets.button import Button as TitanButton
    from titan_cli.ui.tui.widgets.input_field import InputField
    from titan_cli.ui.tui.widgets.pressable_row import PressableRow
    from titan_cli.ui.tui.widgets.updatable import Updatable

    for cls in (TitanButton, InputField, PressableRow):
        assert issubclass(cls, Updatable)


def test_a_redraw_patches_what_has_the_same_kind_and_replaces_the_rest():
    from titan_cli.ui.tui.widgets.element_widgets import _Group, plan_reconcile
    from titan_cli.ui.tui.widgets.element_text import Line as _Line
    from titan_cli.ui.tui.widgets.pressable_row import PressableRow as _PressableLine

    current = [_Line, _PressableLine, _Group, _Line]
    tree = [Text("a"), Button("b", lambda: None), Text("c")]
    assert plan_reconcile(current, tree) == [("patch", 0), ("patch", 1), ("replace", 2), ("remove", 3)]
    assert plan_reconcile([_Line], tree) == [("patch", 0), ("add", 1), ("add", 2)]
    assert plan_reconcile([], []) == []


def test_a_button_is_compact_by_size_and_keeps_its_callback_across_a_redraw():
    from titan_cli.ui.tui.widgets.button import Button as TitanButton

    pressed = []
    widget = TitanButton("Go", variant="primary", size="compact", on_press=lambda: pressed.append("old"))
    assert widget.has_class("-compact")
    assert not TitanButton("Go").has_class("-compact")

    widget.apply(Button("Stop", lambda: pressed.append("new"), variant="error"))
    widget._on_press()
    assert (str(widget.label), widget.variant, pressed) == ("Stop", "error", ["new"])


def test_a_component_is_drawn_by_the_widget_registered_under_its_name():
    from textual.widget import Widget

    from titan_cli.ui.elements import Component
    from titan_cli.ui.tui.widgets.element_text import Line
    from titan_cli.ui.tui.widgets.element_widgets import kind
    from titan_cli.ui.tui.widgets.registry import register_widget, unregister_widget, widget_for

    class Graph(Widget):
        def apply(self, props):
            self.props = props

    assert kind(Component("test.graph", [1, 2])) is Line  # not registered: a line that says so
    register_widget("test.graph", Graph)
    try:
        assert kind(Component("test.graph", [1, 2])) is Graph
        assert widget_for("test.graph") is Graph
    finally:
        unregister_widget("test.graph")
    assert widget_for("test.graph") is None


def test_only_an_updatable_class_can_be_registered_as_a_widget():
    import pytest
    from textual.widget import Widget

    from titan_cli.ui.tui.widgets.registry import register_widget

    class NoApply(Widget):
        pass

    with pytest.raises(TypeError):
        register_widget("test.bad", NoApply)
    with pytest.raises(TypeError):
        register_widget("test.bad", "not a class")


def test_m_ui_widget_reaches_the_host_and_the_headless_host_only_logs():
    bus = ModBus()
    bus.api("dev").ui.widget("dev.graph", object)  # headless: nothing raised

    seen = []
    bus.host = type("H", (RecordingHost,), {"widget": lambda self, mod, name, widget: seen.append((mod, name, widget))})()
    bus.api("dev").ui.widget("dev.graph", int)
    assert seen == [("dev", "dev.graph", int)]


def test_a_plugin_client_is_cached_until_the_plugin_is_rebuilt():
    from types import SimpleNamespace

    from titan_cli.ui.tui.mods_ui import TitanModHost

    class Plugin:
        def __init__(self):
            self.client = object()

        def is_available(self):
            return True

        def get_client(self):
            return self.client

    class Registry:
        def __init__(self):
            self.plugin, self.initialized, self.inits = Plugin(), set(), 0

        def ensure_initialized(self, name):
            self.inits += 1
            self.initialized.add(name)
            return self.plugin

        def is_initialized(self, name):
            return name in self.initialized

    registry = Registry()
    host = TitanModHost(SimpleNamespace(config=None), ModBus(), registry)

    first = host.client("google")
    assert host.client("google") is first and registry.inits == 1

    registry.initialized.clear()          # a forced reload rebuilt the plugins
    registry.plugin.client = rebuilt = object()

    assert host.client("google") is rebuilt


def _timer_app(started, scheduled):
    import threading
    from types import SimpleNamespace

    return SimpleNamespace(
        _thread_id=threading.get_ident(), is_running=True,
        set_interval=lambda seconds, fn: SimpleNamespace(stop=lambda: None),
        set_timer=lambda delay, fn: scheduled.append((delay, fn)) or SimpleNamespace(stop=lambda: None),
        run_worker=lambda work, **kwargs: started.append(kwargs["group"]),
        workers=SimpleNamespace(cancel_group=lambda node, group: None),
        _bindings=SimpleNamespace(key_to_bindings={}),
        screen=SimpleNamespace(query_one=lambda *a: (_ for _ in ()).throw(LookupError())),
    )


def test_first_ticks_wait_for_the_first_frame_then_go_one_after_another():
    from titan_cli.core.mods import ModBus
    from titan_cli.ui.tui.mods_ui import TitanModHost

    started, scheduled = [], []
    host = TitanModHost(app=_timer_app(started, scheduled), bus=ModBus())
    host.repaint = lambda mod: None
    host.every("git", 30, lambda: None, immediately=True)
    host.every("github", 30, lambda: None, immediately=True)
    host.every("gone", 30, lambda: None, immediately=True)
    host.every("quiet", 30, lambda: None, immediately=False)
    host.unload("gone")

    assert started == []  # nothing runs while the first screen is still being drawn

    host.release_first_ticks(delay=0.2, spacing=0.1)

    assert [delay for delay, _ in scheduled] == pytest.approx([0.2, 0.3])
    for _, tick in scheduled:
        tick()
    assert started == ["mod:git", "mod:github"]

    host.every("late", 30, lambda: None, immediately=True)  # after the first frame: at once
    assert started[-1] == "mod:late"


def test_a_slot_resent_unchanged_is_not_painted_again():
    from titan_cli.core.mods import ModBus
    from titan_cli.core.mods.bus import DockSlot, HomeCardSlot
    from titan_cli.ui.elements import Button
    from titan_cli.ui.tui.mods_ui import TitanModHost

    host = TitanModHost(app=_timer_app([], []), bus=ModBus())
    painted = []
    host._paint_dock = lambda: painted.append("dock")
    host._paint_home_cards = lambda: painted.append("home")

    host.dock("git", DockSlot("Git", badge="2", on_click=lambda: None))
    host.dock("git", DockSlot("Git", badge="2", on_click=lambda: None))  # new lambda, same look
    assert painted == ["dock"]
    host.dock("git", DockSlot("Git", badge="3", on_click=lambda: None))
    host.dock("git", DockSlot("Git", badge="3"))  # no longer pressable: drawn differently
    host.dock("git", None)
    assert painted == ["dock"] * 4

    press = lambda: None  # noqa: E731
    host.home_card("git", HomeCardSlot("Git", "clean", actions=(Button("Pull", press, "primary"),)))
    host.home_card("git", HomeCardSlot("Git", "clean", actions=(Button("Pull", lambda: None, "primary"),)))
    assert painted.count("home") == 1
    host.home_card("git", HomeCardSlot("Git", "clean", actions=(Button("Push", press, "primary"),)))
    assert painted.count("home") == 2


def test_a_plugins_mod_and_workspace_of_one_name_get_one_row_per_task_listing_both():
    from types import SimpleNamespace

    from titan_cli.core.models import AIConfig
    from titan_cli.ui.tui.mods_ui import TitanModHost
    from titan_cli.ui.tui.screens.ai_routing import TaskRoutingRow

    manifest = SimpleNamespace(ai_task="Branch name", ai_assist_task="Fix with AI", plugin="git")
    mods, workspaces = ModBus(), ModBus(prefix="workspace.")
    mods.manifests = {"git": manifest}
    workspaces.manifests = {"git": manifest, "notes": SimpleNamespace(ai_task="Notes", ai_assist_task=None, plugin=None)}
    app = SimpleNamespace(config=SimpleNamespace(config=SimpleNamespace(ai=AIConfig())), workspaces=workspaces)
    host = TitanModHost(app, mods)

    class FakeExecutor:
        ai_config = host._ai_config()

        def resolve(self, policy):
            return None

    host._executor = FakeExecutor()
    rows = {r.task: r for r in host.ai_routings()}

    assert set(rows) == {"mods.git", "mods.git.assist", "mods.workspace.notes"}
    assert rows["mods.git"].mods == ["git", "workspace.git"]
    assert TaskRoutingRow._usage_summary(SimpleNamespace(routing=rows["mods.git"])) == "used by mod git · workspace git"
    assert TaskRoutingRow._usage_summary(SimpleNamespace(routing=rows["mods.workspace.notes"])) == "used by workspace notes"


def test_a_plugins_workspace_asks_under_its_mods_task_but_is_named_as_itself():
    from types import SimpleNamespace

    from titan_cli.core.models import AIConfig
    from titan_cli.ui.tui.mods_ui import TitanModHost

    workspaces = ModBus(prefix="workspace.")
    # Found but not loaded (switched off): its task is still the mod's.
    workspaces.found = {"git": SimpleNamespace(plugin="git"), "notes": SimpleNamespace(plugin=None)}
    app = SimpleNamespace(config=SimpleNamespace(config=SimpleNamespace(ai=AIConfig())), workspaces=workspaces)
    host = TitanModHost(app, ModBus())
    toasts = []
    host.toast = lambda mod, text, severity: toasts.append(mod)
    host._ai_executor = lambda: None

    assert host._policy("workspace.git").task == "mods.git"
    assert host._assist_policy("workspace.git").task == "mods.git.assist"
    assert host._policy("workspace.notes").task == "mods.workspace.notes"
    assert workspaces.api("git").ai.task == "mods.git"
    assert workspaces.api("git").ident == "workspace.git"

    host.ai_configure("workspace.git", "Branch name", None)
    assert toasts == ["workspace.git"]


def test_ai_per_task_lists_the_steps_tasks_before_the_mods_each_by_label():
    from titan_cli.ui.tui.screens.ai_routing import TaskRouting, order_task_routings

    rows = [
        TaskRouting(task="mods.git", label="Branch name", mods=["git"]),
        TaskRouting(task="review", label="Review PR"),
        TaskRouting(task="mods.jira", label="Algo", mods=["jira"]),
        TaskRouting(task="commit", label="commit message"),
    ]

    assert [r.task for r in order_task_routings(rows)] == ["commit", "review", "mods.jira", "mods.git"]
