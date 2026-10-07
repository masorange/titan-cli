from titan_cli.core.mods import ModBus, StepCall, discover_mods, load_mods, mod_sources
from titan_cli.engine.results import Error, Success

GUARD = """
def register(on, options):
    @on("step.call", match={"step": "push"})
    def guard(m, e, next):
        return m.deny(options["reason"])
"""


def write_mod(root, name, source=GUARD, manifest=None):
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "mod.toml").write_text(
        manifest if manifest is not None else f'[mod]\nname = "{name}"\nversion = "1.0.0"\n\n[options]\nreason = "from {root.name}"\n'
    )
    (folder / "mod.py").write_text(source)
    return folder


def push_result(bus):
    event = StepCall(workflow="wf", step_id="p", step_name="p", plugin="git", step="push")
    return bus.dispatch("step.call", event, lambda e: Success("ok"))


def test_user_mod_overrides_plugin_mod_of_the_same_name(tmp_path):
    plugin, user = tmp_path / "plugin", tmp_path / "user"
    write_mod(plugin, "guard")
    write_mod(user, "guard")
    write_mod(plugin, "only_in_plugin")

    found = discover_mods(mod_sources({"github": plugin}, user_root=user))

    assert found["guard"].source == "user"
    assert found["only_in_plugin"].source == "plugin:github"


def test_sources_go_from_titan_to_plugin_to_project_to_user(tmp_path):
    titan, plugin, repo, user = (tmp_path / n for n in ("titan", "plugin", "repo", "user"))
    for root in (titan, plugin, repo / ".titan" / "mods", user):
        write_mod(root, "everywhere")
    write_mod(titan, "from_titan")
    write_mod(repo / ".titan" / "mods", "from_repo")
    write_mod(repo / ".titan" / "mods", "repo_and_user")
    write_mod(user, "repo_and_user")

    found = discover_mods(mod_sources({"github": plugin}, project_root=repo, user_root=user, titan_root=titan))

    assert {name: m.source for name, m in found.items()} == {
        "everywhere": "user",
        "from_titan": "titan",
        "from_repo": "project",
        "repo_and_user": "user",
    }


def test_manifest_is_read_without_running_the_mod(tmp_path):
    write_mod(
        tmp_path,
        "panel",
        source="raise RuntimeError('must not run')\n",
        manifest='[mod]\nname = "panel"\nversion = "0.2.0"\ndescription = "A pane"\n'
        'requires_plugins = ["git"]\nevents = ["app.start", "ui.render"]\nslots = ["pane"]\n'
        "[options]\nevery = 30\n",
    )

    manifest = discover_mods([("user", tmp_path)])["panel"]

    assert (manifest.version, manifest.description) == ("0.2.0", "A pane")
    assert manifest.requires_plugins == ("git",)
    assert manifest.events == ("app.start", "ui.render")
    assert manifest.slots == ("pane",)
    assert manifest.options == {"every": 30}


def test_folders_without_a_valid_manifest_or_entrypoint_are_skipped(tmp_path):
    (tmp_path / "no_manifest").mkdir()
    (tmp_path / "no_manifest" / "mod.py").write_text(GUARD)
    write_mod(tmp_path, "bad_toml", manifest="[mod\n")
    write_mod(tmp_path, "wrong_name", manifest='[mod]\nname = "other"\n')
    (write_mod(tmp_path, "no_entry") / "mod.py").unlink()
    write_mod(tmp_path, "good")

    assert list(discover_mods([("user", tmp_path), ("user", tmp_path / "missing")])) == ["good"]


def test_options_merge_config_over_manifest_defaults(tmp_path):
    write_mod(tmp_path, "guard")
    bus = ModBus()

    load_mods(bus, discover_mods([("user", tmp_path)]), {"guard": {"options": {"reason": "from config"}}})

    assert "from config" in push_result(bus).message


def test_disabled_mod_never_runs(tmp_path):
    write_mod(tmp_path, "guard", source="raise RuntimeError('must not run')\n")
    bus = ModBus()

    loaded = load_mods(bus, discover_mods([("user", tmp_path)]), {"guard": {"enabled": False}})

    assert loaded == []
    assert isinstance(push_result(bus), Success)


def test_loaded_mod_hooks_the_bus(tmp_path):
    write_mod(tmp_path, "guard")
    bus = ModBus()

    assert load_mods(bus, discover_mods([("user", tmp_path)])) == ["guard"]
    result = push_result(bus)
    assert isinstance(result, Error) and "guard" in result.message


def test_broken_mods_are_left_out_without_stopping_the_rest(tmp_path):
    write_mod(tmp_path, "a_syntax", source="def register(on, options):\n    @@@\n")
    write_mod(tmp_path, "b_no_register", source="x = 1\n")
    write_mod(tmp_path, "c_raises", source="def register(on, options):\n    raise RuntimeError('boom')\n")
    write_mod(tmp_path, "d_bad_event", source="def register(on, options):\n    on('nope')\n")
    write_mod(tmp_path, "e_good")

    assert load_mods(ModBus(), discover_mods([("user", tmp_path)])) == ["e_good"]


def test_a_register_that_fails_half_way_leaves_no_hooks_behind(tmp_path):
    write_mod(tmp_path, "half", source=GUARD + "    raise RuntimeError('boom')\n")
    bus = ModBus()

    assert load_mods(bus, discover_mods([("user", tmp_path)])) == []
    assert not bus.has_hooks("step.call")
    assert bus.mods == [] and "half" not in bus.manifests
    assert isinstance(push_result(bus), Success)


def test_loaded_mods_keep_their_manifest_and_declared_ai_task(tmp_path):
    write_mod(tmp_path, "ai_mod", source="def register(on, options):\n    pass\n",
              manifest='[mod]\nname = "ai_mod"\nai_task = "My diagnosis"\n')
    write_mod(tmp_path, "plain", source="def register(on, options):\n    pass\n", manifest='[mod]\nname = "plain"\n')
    bus = ModBus()

    load_mods(bus, discover_mods([("user", tmp_path)]))

    assert bus.manifests["ai_mod"].ai_task == "My diagnosis"
    assert bus.manifests["plain"].ai_task is None
