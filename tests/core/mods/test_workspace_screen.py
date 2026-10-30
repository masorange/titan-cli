import threading
from pathlib import Path
from types import SimpleNamespace

from titan_cli.core.mods import WORKSPACES, ModBus, discover_mods, load_mods
from titan_cli.ui.elements import Text
from titan_cli.ui.tui.mods_ui import TitanModHost
from titan_cli.ui.tui.screens.workspace_screen import WorkspaceScreen

SHIPPED = Path(__file__).resolve().parents[3] / "plugins/titan-plugin-github/titan_plugin_github/workspaces"


class FakeApp:
    def __init__(self, bus=None, screen=None):
        self._thread_id = threading.get_ident()
        self.is_running = True
        self.config = SimpleNamespace()
        self.workspaces = bus
        self.screen = screen
        self.pushed = []
        self.notices = []
        self.workers = SimpleNamespace(cancel_group=lambda *a: None)

    def push_screen(self, screen):
        self.pushed.append(screen)

    def notify(self, text, severity="information", **_):
        self.notices.append((text, severity))

    def call_later(self, fn):
        pass

    def batch_update(self):
        return None


def workspace_bus(app):
    bus = ModBus(prefix="workspace.", store_dir="workspaces")
    app.workspaces = bus
    bus.host = TitanModHost(app, bus)
    return bus


def test_a_workspace_draws_what_its_view_answers_for_the_width_it_is_given():
    bus = workspace_bus(FakeApp())
    w = bus.api("jira")
    w.ui.view(lambda width: Text(f"{width} columns"), title="Jira")

    assert bus.views["jira"][0] == "Jira"
    assert bus.render_view("jira", 80) == Text("80 columns")


def test_opening_a_workspace_pushes_its_screen_with_its_title():
    app = FakeApp()
    bus = workspace_bus(app)
    w = bus.api("jira")
    w.ui.view(lambda width: None, title="Jira board")

    assert w.ui.open_workspace() is True

    [screen] = app.pushed
    assert isinstance(screen, WorkspaceScreen) and screen.workspace == "jira"
    assert screen.screen_title == "Jira board"


def test_opening_a_workspace_that_does_not_exist_is_refused_with_a_toast():
    app = FakeApp()
    bus = workspace_bus(app)

    assert bus.api("jira").ui.open_workspace("nope") is False
    assert app.pushed == [] and "no workspace 'nope'" in app.notices[0][0]


def test_opening_the_workspace_already_on_top_does_nothing():
    app = FakeApp()
    bus = workspace_bus(app)
    w = bus.api("jira")
    w.ui.view(lambda width: None)
    app.screen = object.__new__(WorkspaceScreen)
    app.screen.workspace = "jira"

    assert w.ui.open_workspace() is True
    assert app.pushed == []


def test_unloading_a_workspace_takes_its_view_back():
    bus = workspace_bus(FakeApp())
    bus.api("jira").ui.view(lambda width: None)
    bus.unload("jira")
    assert "jira" not in bus.views


def test_a_headless_bus_cannot_open_a_workspace():
    bus = ModBus(prefix="workspace.")
    assert bus.api("jira").ui.open_workspace() is False


def test_a_workspace_with_an_ai_task_gets_rows_on_the_ai_screen_apart_from_a_mod_of_the_same_name():
    from titan_cli.core.models import AIConfig
    from titan_cli.ui.tui.screens.ai_routing import TaskRoutingRow

    app = FakeApp()
    mods = ModBus()
    workspaces = workspace_bus(app)
    manifest = SimpleNamespace(ai_task="Diagnosis", ai_assist_task=None)
    mods.manifests = {"github": manifest}
    workspaces.manifests = {"github": manifest}
    app.config = SimpleNamespace(config=SimpleNamespace(ai=AIConfig()))
    host = TitanModHost(app, mods)

    class FakeExecutor:
        ai_config = host._ai_config()

        def resolve(self, policy):
            return None

    host._executor = FakeExecutor()
    rows = {r.task: r for r in host.ai_routings()}

    assert set(rows) == {"mods.github", "mods.workspace.github"}
    assert TaskRoutingRow._usage_summary(SimpleNamespace(routing=rows["mods.workspace.github"])) == "used by workspace github"
    assert TaskRoutingRow._usage_summary(SimpleNamespace(routing=rows["mods.github"])) == "used by mod github"


def test_the_github_workspace_ships_a_view():
    bus = workspace_bus(FakeApp())
    loaded = load_mods(bus, discover_mods([("plugin:github", SHIPPED)], WORKSPACES), kind=WORKSPACES)

    assert loaded == ["github"]
    assert bus.render_view("github", 60) is not None


def test_what_a_workspace_asks_at_start_runs_when_the_bus_starts_with_the_host_in_place():
    bus = ModBus(prefix="workspace.")
    seen = []
    bus.api("jira").on_start(lambda w: seen.append(w.name))
    bus.api("jira").on_start(lambda w: 1 / 0)  # one that raises does not stop the rest

    assert seen == []  # nothing runs at register time
    bus.start()
    assert seen == ["jira"]
    bus.start("nope")  # no such workspace: nothing happens


def test_the_github_workspace_puts_its_tile_in_the_dock_on_start():
    app = FakeApp()
    bus = workspace_bus(app)
    tiles = {}
    bus.host.dock = lambda mod, slot: tiles.update({mod: slot})
    load_mods(bus, discover_mods([("plugin:github", SHIPPED)], WORKSPACES), kind=WORKSPACES)
    assert tiles == {}  # register alone draws nothing

    bus.start()

    assert tiles["workspace.github"].label == "GitHub"
    assert tiles["workspace.github"].on_click is not None
