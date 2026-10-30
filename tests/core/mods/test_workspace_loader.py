from titan_cli.core.mods import MODS, WORKSPACES, ModBus, discover_mods, load_mods, mod_sources
from titan_cli.core.mods.loader import build_mod_bus, mod_dirs, read_manifest, read_mods_config
from titan_cli.core.mods.status import FAILED, LOADED

WORKSPACE_TOML = '[workspace]\nname = "{name}"\nversion = "1.0.0"\n{extra}'
REGISTER = "def register(w, on, options):\n    w.ui.toast(f'hello {options[\"who\"]}')\n"
WITH_OPTION = '\n[options.who]\ntype = "string"\ndefault = "there"\n'


def write_workspace(root, name, source=REGISTER, extra=WITH_OPTION):
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "workspace.toml").write_text(WORKSPACE_TOML.format(name=name, extra=extra))
    (folder / "workspace.py").write_text(source)
    return folder


class Host:
    def __init__(self):
        self.calls = []

    def toast(self, mod, text, severity):
        self.calls.append(("toast", mod, text))

    def repaint(self, mod):
        self.calls.append(("repaint", mod))

    def unload(self, mod):
        self.calls.append(("unload", mod))

    def every(self, mod, seconds, fn, immediately):
        self.calls.append(("every", mod))


def test_workspaces_have_the_same_sources_as_mods_under_their_own_folders(tmp_path):
    titan, plugin, repo, user = (tmp_path / n for n in ("titan", "plugin", "repo", "user"))
    for root in (titan, plugin, repo / ".titan" / "workspaces", user):
        write_workspace(root, "everywhere")
    write_workspace(plugin, "from_plugin")

    sources = mod_sources({"github": plugin}, project_root=repo, user_root=user, titan_root=titan, kind=WORKSPACES)
    found = discover_mods(sources, WORKSPACES)

    assert found["everywhere"].source == "user"
    assert found["from_plugin"].source == "plugin:github"
    assert found["everywhere"].entrypoint.name == "workspace.py"
    paths = [path for _, path in mod_sources({}, project_root=repo, user_root=user, kind=WORKSPACES)]
    assert repo / ".titan" / "workspaces" in paths


def test_a_workspace_folder_is_not_found_as_a_mod_and_the_other_way_round(tmp_path):
    write_workspace(tmp_path, "w1")
    assert discover_mods([("user", tmp_path)], MODS) == {}
    assert list(discover_mods([("user", tmp_path)], WORKSPACES)) == ["w1"]


def test_the_manifest_table_is_workspace_not_mod(tmp_path):
    folder = write_workspace(tmp_path, "w1")
    assert read_manifest(folder, "user", WORKSPACES).version == "1.0.0"
    import pytest

    with pytest.raises(ValueError):
        read_manifest(folder, "user", MODS)  # no mod.toml there


def test_register_gets_w_with_its_options_and_the_host_sees_the_prefixed_name(tmp_path):
    write_workspace(tmp_path, "github")
    bus = ModBus(prefix=WORKSPACES.host_prefix, store_dir=WORKSPACES.store_dir)
    bus.host = host = Host()

    loaded = load_mods(bus, discover_mods([("user", tmp_path)], WORKSPACES), kind=WORKSPACES)

    assert loaded == ["github"]
    assert bus.statuses["github"].state == LOADED
    assert host.calls == [("toast", "workspace.github", "hello there")]


def test_a_mod_and_a_workspace_with_the_same_name_do_not_share_what_the_host_keeps(tmp_path):
    mods_bus, ws_bus = ModBus(), ModBus(prefix="workspace.", store_dir="workspaces")
    mods_bus.host = ws_bus.host = host = Host()

    mods_bus.api("github").clock.every(60, lambda: None)
    ws_bus.api("github").clock.every(60, lambda: None)
    ws_bus.unload("github")

    assert host.calls == [("every", "github"), ("every", "workspace.github"), ("unload", "workspace.github")]
    assert mods_bus.api("github").store.path != ws_bus.api("github").store.path
    assert ws_bus.api("github").store.path.parent.name == "workspaces"


def test_a_workspace_that_fails_is_left_out_and_reported(tmp_path):
    write_workspace(tmp_path, "broken", source="raise RuntimeError('boom')\n")
    bus = ModBus(prefix="workspace.")
    bus.host = Host()

    assert load_mods(bus, discover_mods([("user", tmp_path)], WORKSPACES), kind=WORKSPACES) == []
    assert bus.statuses["broken"].state == FAILED


def test_an_entry_point_with_no_register_says_which_signature_it_wants(tmp_path):
    write_workspace(tmp_path, "empty", source="x = 1\n")
    bus = ModBus(prefix="workspace.")
    load_mods(bus, discover_mods([("user", tmp_path)], WORKSPACES), kind=WORKSPACES)
    assert "register(w, on, options)" in bus.statuses["empty"].error


def test_config_and_dirs_come_from_the_workspaces_table(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        '[workspaces.github]\nenabled = false\n[workspaces]\ndirs = ["/tmp/ws-checkout"]\n[mods.github]\nenabled = true\n'
    )
    assert read_mods_config(config, project_root_path=tmp_path, kind=WORKSPACES) == {"github": {"enabled": False}}
    assert [str(p) for p in mod_dirs(config_path=config, environ={}, kind=WORKSPACES)] == ["/tmp/ws-checkout"]
    assert mod_dirs(config_path=config, environ={"TITAN_WORKSPACE_DIRS": "/tmp/a"}, kind=WORKSPACES)[-1].name == "a"
    assert mod_dirs(config_path=config, environ={"TITAN_MOD_DIRS": "/tmp/a"}, kind=WORKSPACES)[-1].name == "ws-checkout"


def test_a_disabled_workspace_never_imports(tmp_path):
    write_workspace(tmp_path, "off", source="raise RuntimeError('must not run')\n")
    bus = ModBus(prefix="workspace.")
    load_mods(bus, discover_mods([("user", tmp_path)], WORKSPACES), {"off": {"enabled": False}}, kind=WORKSPACES)
    assert bus.statuses["off"].state == "disabled"


def test_build_mod_bus_for_workspaces_prefixes_and_loads(tmp_path, monkeypatch):
    write_workspace(tmp_path / "ws", "github")
    bus = build_mod_bus(cli_mod_dirs=[str(tmp_path / "ws" / "github")], kind=WORKSPACES)
    assert bus.prefix == "workspace."
    assert bus.statuses["github"].state == LOADED


def test_a_workspace_hooks_events_with_the_on_it_is_given_and_only_those_it_declares(tmp_path):
    hooked = (
        "def register(w, on, options):\n"
        "    @on('workflow.run')\n"
        "    def seen(m, e, next):\n"
        "        m.ui.toast('ran ' + e.workflow)\n"
        "        return next(e)\n"
    )
    write_workspace(tmp_path, "listens", source=hooked, extra='events = ["workflow.run"]\n')
    write_workspace(tmp_path, "silent", source=hooked, extra="")
    bus = ModBus(prefix=WORKSPACES.host_prefix, store_dir=WORKSPACES.store_dir)
    bus.host = host = Host()

    load_mods(bus, discover_mods([("user", tmp_path)], WORKSPACES), kind=WORKSPACES)
    bus.dispatch("workflow.run", type("E", (), {"workflow": "x"})(), lambda e: None)

    assert bus.statuses["listens"].state == LOADED
    assert bus.statuses["silent"].state == FAILED
    assert ("toast", "workspace.listens", "ran x") in host.calls
    assert not any(c[1] == "workspace.silent" and c[0] == "toast" for c in host.calls)
