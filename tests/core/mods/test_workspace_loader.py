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


def test_a_workspace_that_is_off_by_default_loads_only_when_the_user_enables_it(tmp_path):
    write_workspace(tmp_path, "quiet", extra="default_enabled = false\n", source="def register(w, on, options):\n    pass\n")
    found = discover_mods([("user", tmp_path)], WORKSPACES)

    off = ModBus(prefix="workspace.")
    load_mods(off, found, {}, kind=WORKSPACES)
    on = ModBus(prefix="workspace.")
    load_mods(on, found, {"quiet": {"enabled": True}}, kind=WORKSPACES)

    assert off.statuses["quiet"].state == "disabled"
    assert on.statuses["quiet"].state == LOADED


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


def test_a_plugins_workspace_shares_the_ai_task_of_its_mod_and_a_personal_one_does_not(tmp_path):
    write_workspace(tmp_path / "plugin", "git")
    write_workspace(tmp_path / "user", "notes")
    found = discover_mods([("plugin:git", tmp_path / "plugin"), ("user", tmp_path / "user")], WORKSPACES)
    bus = ModBus(prefix=WORKSPACES.host_prefix, store_dir=WORKSPACES.store_dir)
    bus.host = Host()
    load_mods(bus, found, kind=WORKSPACES)

    assert found["git"].plugin == "git" and found["notes"].plugin is None
    assert bus.api("git").ai.task == "mods.git"
    assert bus.api("notes").ai.task == "mods.workspace.notes"
    # Only the AI task is shared: timers, keys and the store stay the workspace's own.
    assert bus.api("git").ident == "workspace.git"


def test_a_plugins_workspace_reads_the_options_it_shares_with_its_mod_from_the_mods_table(tmp_path):
    source = "seen = {}\ndef register(w, on, options):\n    seen.update(options)\n"
    shared = WITH_OPTION + 'shared = true\n[options.key]\ntype = "string"\ndefault = "f6"\n'
    write_workspace(tmp_path / "plugin", "git", source=source, extra=shared)
    write_workspace(tmp_path / "user", "notes", source=source, extra=shared)
    config = tmp_path / "config.toml"
    config.write_text(
        '[mods.git.options]\nwho = "from the mod"\nmod_only = 5\nkey = "f5"\n'
        '[mods.notes.options]\nwho = "not mine"\n'
    )
    configs = read_mods_config(config, project_root_path=tmp_path, kind=WORKSPACES)
    found = discover_mods([("plugin:git", tmp_path / "plugin"), ("user", tmp_path / "user")], WORKSPACES)
    bus = ModBus(prefix=WORKSPACES.host_prefix)
    bus.host = Host()

    import sys

    load_mods(bus, {"git": found["git"]}, configs, kind=WORKSPACES)
    assert sys.modules["titan_workspace_git"].seen["who"] == "from the mod"
    assert "mod_only" not in sys.modules["titan_workspace_git"].seen
    # Declared alike but not `shared`: each surface's own (a key both bound would collide).
    assert sys.modules["titan_workspace_git"].seen["key"] == "f6"
    load_mods(bus, {"notes": found["notes"]}, configs, kind=WORKSPACES)
    assert sys.modules["titan_workspace_notes"].seen["who"] == "there"

    # The workspace's own table still wins for itself.
    config.write_text('[mods.git.options]\nwho = "from the mod"\n[workspaces.git.options]\nwho = "mine"\n')
    load_mods(bus, {"git": found["git"]}, read_mods_config(config, project_root_path=tmp_path, kind=WORKSPACES), kind=WORKSPACES)
    assert sys.modules["titan_workspace_git"].seen["who"] == "mine"


def test_an_official_plugins_mod_and_workspace_declare_the_options_they_share_alike():
    # They are set once, in `[mods.<name>.options]`: a type or default that differed would
    # make one value mean two things, or be refused by one surface only.
    from pathlib import Path

    plugins = Path(__file__).resolve().parents[3] / "plugins"
    pairs = 0
    for workspace_toml in plugins.glob("titan-plugin-*/titan_plugin_*/workspaces/*/workspace.toml"):
        mod_folder = workspace_toml.parents[2] / "mods" / workspace_toml.parent.name
        if not (mod_folder / "mod.toml").is_file():
            continue
        pairs += 1
        workspace = read_manifest(workspace_toml.parent, "plugin:x", WORKSPACES).options
        mod = read_manifest(mod_folder, "plugin:x", MODS).options
        for name, spec in workspace.items():
            if not spec.shared:
                continue
            def value(spec):
                return (spec.type, spec.default, spec.values, spec.min, spec.max)

            assert name in mod, f"{workspace_toml.parent.name}: shared option '{name}' is not the mod's"
            assert value(spec) == value(mod[name]), f"{workspace_toml.parent.name}: shared option '{name}' differs"
    assert pairs


def test_shared_is_refused_in_a_mods_own_options(tmp_path):
    import pytest

    folder = tmp_path / "m"
    folder.mkdir()
    (folder / "mod.toml").write_text('[mod]\nname = "m"\n[options.x]\ntype = "int"\ndefault = 1\nshared = true\n')
    with pytest.raises(ValueError, match="shared is for a workspace"):
        read_manifest(folder, "user", MODS)
