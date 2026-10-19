import threading

from titan_cli.core.mods import ModBus
from titan_cli.core.mods.keys import key_refusal, normalize_key
from titan_cli.ui.tui.app import TitanApp
from titan_cli.ui.tui.mods_ui import TitanModHost


class FakeApp(TitanApp):
    """TitanApp's class (so its bindings count) without starting Textual."""

    def __init__(self):
        self._thread_id = threading.get_ident()
        self.bound = []

    def bind(self, key, action, *, description="", show=True, **_):
        self.bound.append((key, action, description, show))


def host_and_api(*mods):
    bus = ModBus()
    host = TitanModHost(FakeApp(), bus)
    bus.host = host
    return host, {mod: bus.api(mod) for mod in mods}


def test_normalize_key_lowers_names_and_keeps_single_characters():
    assert normalize_key(" F5 ") == "f5"
    assert normalize_key("Ctrl+K") == "ctrl+k"
    assert normalize_key("A") == "A"


def test_key_refusal_reasons():
    assert key_refusal("f5", {"f4"}, {}, "a") is None
    assert key_refusal("f4", {"f4"}, {}, "a") == "'f4' is already a Titan shortcut"
    assert key_refusal("f6", set(), {"f6": "b"}, "a") == "'f6' is already bound by mod 'b'"
    assert key_refusal("f6", set(), {"f6": "a"}, "a") is None  # binding again replaces its own
    assert key_refusal("a,b", set(), {}, "a") == "'a,b' is not one key"


def test_titan_keys_cover_the_app_screens_and_widgets():
    host, _ = host_and_api()
    keys = host.titan_keys()
    assert {"f2", "f3", "f4", "q", "ctrl+c"} <= keys  # TitanApp
    assert "question_mark" in keys  # "?" in Textual's spelling
    assert "escape" in keys and "enter" in keys  # screens and widgets


def test_a_free_key_is_bound_on_the_app_and_runs_the_mod_function():
    host, apis = host_and_api("dev")
    pressed = []

    assert apis["dev"].keys.bind("F5", "Refresh", lambda: pressed.append(1)) is True
    assert host._app.bound == [("f5", "mod_key('f5')", "Refresh", True)]

    host.press_key("f5")
    assert pressed == [1]


def test_titan_and_other_mods_keys_are_refused():
    host, apis = host_and_api("a", "b")

    assert apis["a"].keys.bind("f4", "Mine", lambda: None) is False
    assert apis["a"].keys.bind("f6", "Mine", lambda: None) is False
    assert apis["a"].keys.bind("?", "Mine", lambda: None) is False
    assert apis["a"].keys.bind("f7", "A's", lambda: None) is True
    assert apis["b"].keys.bind("f7", "B's", lambda: None) is False
    assert [key for key, *_ in host._app.bound] == ["f7"]


def test_a_failing_key_function_is_logged_not_raised():
    host, apis = host_and_api("dev")
    apis["dev"].keys.bind("f7", "Boom", lambda: 1 / 0)
    host.press_key("f7")
    host.press_key("f8")  # unbound: nothing happens
