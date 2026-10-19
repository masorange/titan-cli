import os
from pathlib import Path

import sys

import pytest

from titan_cli.core.mods import ModBus, StepCall, discover_mods, import_mod, load_mods, mod_sources
from titan_cli.core.mods.loader import mod_dirs, read_mods_config
from titan_cli.core.mods.status import FAILED
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
        manifest if manifest is not None else f'[mod]\nname = "{name}"\nversion = "1.0.0"\nevents = ["step.call"]\n\n[options.reason]\ntype = "string"\ndefault = "from {root.name}"\n'
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
        "[options.every]\ntype = \"int\"\ndefault = 30\n",
    )

    manifest = discover_mods([("user", tmp_path)])["panel"]

    assert (manifest.version, manifest.description) == ("0.2.0", "A pane")
    assert manifest.requires_plugins == ("git",)
    assert manifest.events == ("app.start", "ui.render")
    assert manifest.slots == ("pane",)
    assert manifest.options["every"].default == 30


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


def test_a_mod_cannot_hook_an_event_its_manifest_does_not_declare(tmp_path):
    write_mod(tmp_path, "sneaky", manifest='[mod]\nname = "sneaky"\nevents = ["ui.render"]\n\n[options.reason]\ntype = "string"\ndefault = "x"\n')
    bus = ModBus()

    assert load_mods(bus, discover_mods([("user", tmp_path)])) == []
    assert not bus.has_hooks("step.call")
    assert isinstance(push_result(bus), Success)


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


def test_dev_folder_is_one_mod_and_overrides_every_other_source(tmp_path):
    user = tmp_path / "user"
    write_mod(user, "guard")
    checkout = write_mod(tmp_path / "git", "guard")
    second = write_mod(tmp_path / "git", "other")

    found = discover_mods(mod_sources({}, user_root=user, dev_dirs=[checkout, second]))

    assert (found["guard"].source, found["guard"].folder) == ("dev", checkout)
    assert found["other"].source == "dev"


def test_dev_folder_takes_its_name_from_the_manifest(tmp_path):
    checkout = write_mod(tmp_path, "titan-mod-guard", manifest='[mod]\nname = "guard"\n')

    found = discover_mods([("dev", checkout)])

    assert list(found) == ["guard"]


def test_dev_folder_without_a_mod_is_skipped(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()

    assert discover_mods([("dev", empty), ("dev", tmp_path / "missing")]) == {}


def test_dirs_cannot_name_a_mod(tmp_path):
    write_mod(tmp_path, "dirs")

    assert discover_mods([("user", tmp_path)]) == {}


def test_mod_dirs_come_from_config_then_env_then_flag(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[mods]\ndirs = ["~/from-config", "/shared"]\n\n[mods.guard]\nenabled = false\n')
    env = {"TITAN_MOD_DIRS": f"/from-env{os.pathsep}/shared"}

    dirs = mod_dirs(["/from-flag"], config_path=config, environ=env)

    assert dirs == [Path.home() / "from-config", Path("/from-env"), Path("/shared"), Path("/from-flag")]
    assert read_mods_config(config, tmp_path / "unscoped-project") == {"guard": {"enabled": False}}


def test_invalid_mod_dirs_config_is_ignored(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[mods]\ndirs = "/not-a-list"\n')

    assert mod_dirs(config_path=config, environ={}) == []


MULTI_FILE = """
from .rules import reason

def register(on, options):
    @on("step.call", match={"step": "push"})
    def guard(m, e, next):
        return m.deny(reason())
"""


def write_multi_file_mod(root, name, said):
    folder = write_mod(root, name, source=MULTI_FILE)
    (folder / "rules").mkdir()
    (folder / "rules" / "__init__.py").write_text("from ..wording import said\n\ndef reason():\n    return said\n")
    (folder / "wording.py").write_text(f"said = {said!r}\n")
    return folder


def test_a_mod_imports_its_own_modules_relatively(tmp_path):
    write_multi_file_mod(tmp_path, "guard", "split across files")
    bus = ModBus()

    assert load_mods(bus, discover_mods([("user", tmp_path)])) == ["guard"]
    assert push_result(bus).message.endswith("split across files")


def test_two_mods_with_a_module_of_the_same_name_do_not_shadow_each_other(tmp_path):
    first = write_multi_file_mod(tmp_path, "first", "from first")
    second = write_multi_file_mod(tmp_path, "second", "from second")

    assert import_mod(first).rules.reason() == "from first"
    assert import_mod(second).rules.reason() == "from second"


def test_a_mod_that_fails_to_register_leaves_none_of_its_modules_behind(tmp_path):
    folder = write_multi_file_mod(tmp_path, "broken", "x")
    (folder / "mod.py").write_text("from . import wording\n\ndef register(on, options):\n    raise RuntimeError('no')\n")

    assert load_mods(ModBus(), discover_mods([("user", tmp_path)])) == []
    assert not [m for m in sys.modules if m.startswith("titan_mod_broken")]


def test_a_mod_that_fails_to_import_leaves_none_of_its_modules_behind(tmp_path):
    folder = write_multi_file_mod(tmp_path, "typo", "x")
    (folder / "mod.py").write_text("from . import wording\nfrom . import missing\n")

    with pytest.raises(ImportError):
        import_mod(folder)
    assert not [m for m in sys.modules if m.startswith("titan_mod_typo")]


def test_a_mod_name_must_be_usable_as_a_package_name(tmp_path):
    checkout = write_mod(tmp_path, "checkout", manifest='[mod]\nname = "has.dot"\n')

    assert discover_mods([("dev", checkout)]) == {}


@pytest.mark.parametrize(
    "toml, expected",
    [
        ("[mods]\nenabled = false\n", {}),
        ("mods = 1\n", {}),
        ("[mods.guard]\noptions = 1\n", {"guard": {"options": {}}}),
        ("[mods.guard]\nsections = 1\nenabled = false\n", {"guard": {"sections": {}, "enabled": False}}),
    ],
)
def test_malformed_mods_config_is_dropped_without_raising(tmp_path, toml, expected):
    config = tmp_path / "config.toml"
    config.write_text(toml)

    assert read_mods_config(config, tmp_path / "project") == expected
    assert mod_dirs(config_path=config, environ={}) == []


def test_scoped_sections_merge_over_a_malformed_background_one(tmp_path):
    project = tmp_path / "project"
    user = tmp_path / "config.toml"
    from titan_cli.core.utils import project_source_scope_key

    key = project_source_scope_key(project)
    user.write_text(f'[mods.guard]\nsections = 1\n\n[project_sources."{key}".mods.guard.sections]\nprs = false\n')

    assert read_mods_config(user, project) == {"guard": {"sections": {"prs": False}}}


def test_invalid_config_option_falls_back_to_the_default(tmp_path):
    write_mod(tmp_path, "guard")
    bus = ModBus()

    load_mods(bus, discover_mods([("user", tmp_path)]), {"guard": {"options": {"reason": 5, "typo": 1}}})

    assert f"from {tmp_path.name}" in push_result(bus).message


def test_manifest_with_untyped_option_is_skipped(tmp_path):
    write_mod(tmp_path, "old", manifest='[mod]\nname = "old"\n[options]\nevery = 30\n')

    assert discover_mods([("user", tmp_path)]) == {}


@pytest.mark.parametrize(
    "manifest",
    [
        'mod = "x"\n',
        '[mod]\nname = 5\n',
        '[mod]\nname = "bad"\nevents = "ui.render"\n',
        '[mod]\nname = "bad"\nslots = [1]\n',
        '[mod]\nname = "bad"\n\n[options]\n',  # valid: control case below
        'options = 1\n[mod]\nname = "bad"\n',
        'sections = 1\n[mod]\nname = "bad"\n',
    ],
)
def test_type_malformed_manifests_are_skipped_without_raising(tmp_path, manifest):
    write_mod(tmp_path, "bad", manifest=manifest)
    found = discover_mods([("user", tmp_path)])

    assert ("bad" in found) == manifest.startswith('[mod]\nname = "bad"\n\n[options]')


def test_the_projects_scoped_override_wins_over_the_background_default(tmp_path):
    from titan_cli.core.utils import project_source_scope_key

    user = tmp_path / "user.toml"
    project = tmp_path / "project"
    project.mkdir()
    key = project_source_scope_key(project)
    user.write_text(
        '[mods.mine]\nenabled = true\n[mods.git]\nenabled = false\n[mods.git.sections]\nqueue = false\nprs = false\n'
        '[mods.git.options]\nrefresh_key = "f6"\n'
        f'\n[project_sources.{key}]\nproject_path = "{project}"\n'
        "[project_sources.{0}.mods.mine]\nenabled = false\n"
        "[project_sources.{0}.mods.git]\nenabled = true\n"
        "[project_sources.{0}.mods.git.sections]\nqueue = true\n"
        "[project_sources.{0}.mods.team]\nenabled = false\n"
        '[project_sources.{0}.mods.opts]\noptions = {{ x = 1 }}\n'
        '[project_sources.{0}.mods.bad]\nenabled = "no"\n'.format(key)
    )

    assert read_mods_config(user, project) == {
        "mine": {"enabled": False},
        "git": {"enabled": True, "sections": {"queue": True, "prs": False}, "options": {"refresh_key": "f6"}},
        "team": {"enabled": False},
        "opts": {},
        "bad": {},
    }


def test_a_different_projects_scoped_override_changes_nothing(tmp_path):
    user = tmp_path / "user.toml"
    user.write_text("[mods.git]\nenabled = false\n")

    assert read_mods_config(user, tmp_path / "some-other-project") == {"git": {"enabled": False}}


SECTIONED = (
    '[mod]\nname = "multi"\nevents = ["step.call"]\n'
    '[sections.queue]\ntitle = "Merge queue"\ndefault = false\n[sections.prs]\ntitle = "PRs"\n'
)
SEEN = "def register(on, options):\n    import builtins\n    builtins.SEEN_SECTIONS = dict(options['sections'])\n"


def test_sections_reach_the_mod_as_switches(tmp_path):
    import builtins

    write_mod(tmp_path, "multi", source=SEEN, manifest=SECTIONED)

    found = discover_mods([("user", tmp_path)])
    assert {n: (s.title, s.default) for n, s in found["multi"].sections.items()} == {"queue": ("Merge queue", False), "prs": ("PRs", True)}

    load_mods(ModBus(), found, {"multi": {"sections": {"queue": True, "prs": "no", "typo": False}}})
    assert builtins.SEEN_SECTIONS == {"queue": True, "prs": True}


def test_every_mod_found_gets_a_status(tmp_path):
    from titan_cli.core.mods.status import DISABLED, FAILED, LOADED

    write_mod(tmp_path, "fine")
    write_mod(tmp_path, "off")
    write_mod(tmp_path, "broken", source="def register(on, options):\n    raise RuntimeError('boom')\n")
    bus = ModBus()

    load_mods(bus, discover_mods([("user", tmp_path)]), {"off": {"enabled": False}})

    assert {n: s.state for n, s in bus.statuses.items()} == {"fine": LOADED, "off": DISABLED, "broken": FAILED}
    assert "boom" in bus.statuses["broken"].error
    assert set(bus.found) == {"fine", "off", "broken"}


def test_option_named_sections_is_reserved(tmp_path):
    write_mod(tmp_path, "x", manifest='[mod]\nname = "x"\n[options.sections]\ntype = "bool"\ndefault = true\n')

    assert discover_mods([("user", tmp_path)]) == {}


def test_settings_are_written_scoped_to_the_project_in_the_users_own_config(tmp_path):
    from titan_cli.core.mods.settings import set_mod_enabled, set_mod_section

    config = tmp_path / "config.toml"
    config.write_text('[ai]\ndefault = "x"\n\n[mods.git]\nenabled = true\n')
    project = tmp_path / "project"
    project.mkdir()

    set_mod_enabled("git", False, project, config)
    set_mod_section("git", "queue", False, project, config)
    set_mod_section("new", "a", True, project, config)

    assert read_mods_config(config, project) == {
        "git": {"enabled": False, "sections": {"queue": False}},
        "new": {"sections": {"a": True}},
    }
    assert 'default = "x"' in config.read_text()
    assert '[mods.git]\nenabled = true' in config.read_text()  # The background default is untouched.

    # A project that has never run Titan yet gets the file created, no error.
    set_mod_enabled("git", True, tmp_path / "missing" / "repo", tmp_path / "missing" / "config.toml")
    assert read_mods_config(tmp_path / "missing" / "config.toml", tmp_path / "missing" / "repo") == {
        "git": {"enabled": True}
    }


def test_entries_list_every_mod_by_source_with_what_is_saved(tmp_path):
    from titan_cli.core.mods.status import mod_entries

    titan, user = tmp_path / "titan", tmp_path / "user"
    write_mod(user, "zed", manifest=SECTIONED.replace("multi", "zed"))
    write_mod(user, "alpha")
    write_mod(titan, "core")
    found = discover_mods([("titan", titan), ("user", user)])
    bus = ModBus()
    load_mods(bus, found, {})

    entries = mod_entries(bus.found, bus.statuses, {"alpha": {"enabled": False}, "zed": {"sections": {"queue": True}}})

    assert [e.name for e in entries] == ["core", "alpha", "zed"]
    alpha, zed = entries[1], entries[2]
    assert alpha.enabled is False
    assert zed.sections == {"queue": True, "prs": True}


def test_a_section_switched_while_running_reaches_the_mod_at_once(tmp_path):
    seen = []
    source = (
        "def register(on, options):\n"
        "    import builtins\n"
        "    builtins.LIVE = options['sections']\n"
        "    @on('section.change', match={'section': 'queue'})\n"
        "    def changed(m, e, next):\n"
        "        builtins.CHANGES.append((e.section, e.enabled, options['sections']['queue']))\n"
        "        return next(e)\n"
    )
    import builtins

    builtins.CHANGES = seen
    write_mod(tmp_path, "multi", source=source, manifest=SECTIONED.replace('["step.call"]', '["section.change"]'))
    write_mod(tmp_path, "other", source="def register(on, options): pass\n", manifest=SECTIONED.replace("multi", "other"))
    bus = ModBus()
    repaints = []
    bus.host.repaint = repaints.append
    load_mods(bus, discover_mods([("user", tmp_path)]), {})

    assert bus.set_section("multi", "queue", True)
    assert not bus.set_section("multi", "nope", True)
    assert not bus.set_section("ghost", "queue", True)
    assert bus.set_section("multi", "prs", False)  # no hook for it: still switched

    assert seen == [("queue", True, True)]
    assert builtins.LIVE == {"queue": True, "prs": False}
    assert repaints == ["multi", "multi"]


RELOADABLE = (
    "def register(on, options):\n"
    "    import builtins\n"
    "    builtins.REGISTERED = getattr(builtins, 'REGISTERED', 0) + 1\n"
    "    builtins.OPTION_SEEN = options['reason']\n"
    "    @on('app.start')\n"
    "    def start(m, e, next):\n"
    "        builtins.STARTS = getattr(builtins, 'STARTS', []) + [e.project_root]\n"
    "        return next(e)\n"
    "    @on('step.call')\n"
    "    def guard(m, e, next):\n"
    "        return m.deny('x')\n"
)


def _reloadable(tmp_path):
    import builtins

    for attr in ("REGISTERED", "STARTS", "OPTION_SEEN"):
        if hasattr(builtins, attr):
            delattr(builtins, attr)
    write_mod(tmp_path, "r", source=RELOADABLE, manifest='[mod]\nname = "r"\nevents = ["app.start", "step.call"]\n[options.reason]\ntype = "string"\ndefault = "d"\n')
    bus = ModBus()
    unloaded = []
    bus.host = type("H", (), {"unload": lambda self, mod: unloaded.append(mod), "repaint": lambda self, mod: None})()
    load_mods(bus, discover_mods([("user", tmp_path)]), {})
    return bus, unloaded


def test_reload_switches_a_mod_off_and_on_without_a_restart(tmp_path):
    import builtins

    from titan_cli.core.mods import AppStart, reload_mod
    from titan_cli.core.mods.status import DISABLED, LOADED

    bus, unloaded = _reloadable(tmp_path)
    bus.dispatch("app.start", AppStart(project_root="/repo"), lambda e: None)
    assert push_result(bus).__class__.__name__ == "Error"

    assert reload_mod(bus, "r", {"r": {"enabled": False}}) == DISABLED
    assert push_result(bus).__class__.__name__ == "Success"  # its hook is gone
    assert unloaded == ["r"]
    assert "r" not in bus.manifests and "r" not in bus.sections

    assert reload_mod(bus, "r", {}) == LOADED
    assert push_result(bus).__class__.__name__ == "Error"
    assert builtins.REGISTERED == 2
    # The mod missed Titan's own app.start, so it gets one of its own, and only it.
    assert builtins.STARTS == ["/repo", "/repo"]


def test_reload_applies_options_and_rereads_the_manifest(tmp_path):
    import builtins

    from titan_cli.core.mods import reload_mod

    bus, _ = _reloadable(tmp_path)
    assert builtins.OPTION_SEEN == "d"

    reload_mod(bus, "r", {"r": {"options": {"reason": "from config"}}})

    assert builtins.OPTION_SEEN == "from config"


def test_a_reload_that_fails_leaves_the_mod_failed_and_unloaded(tmp_path):
    from titan_cli.core.mods import reload_mod
    from titan_cli.core.mods.status import FAILED

    bus, unloaded = _reloadable(tmp_path)
    (tmp_path / "r" / "mod.py").write_text("def register(on, options):\n    raise RuntimeError('boom')\n")

    assert reload_mod(bus, "r", {}) == FAILED
    assert "boom" in bus.statuses["r"].error
    assert push_result(bus).__class__.__name__ == "Success"

    (tmp_path / "r" / "mod.toml").write_text("[mod\n")
    assert reload_mod(bus, "r", {}) == FAILED


def test_a_thread_left_by_an_unloaded_mod_reaches_nothing(tmp_path):
    from titan_cli.core.mods import reload_mod

    bus, _ = _reloadable(tmp_path)
    calls = []
    bus.host.toast = lambda *a: calls.append(a)
    old = bus.api("r")
    old.ui.toast("alive")
    reload_mod(bus, "r", {"r": {"enabled": False}})

    old.ui.toast("from a thread that outlived its mod")

    assert len(calls) == 1
    assert old.alive is False


def test_reloading_an_unknown_mod_is_an_error(tmp_path):
    from titan_cli.core.mods import reload_mod

    with pytest.raises(KeyError):
        reload_mod(ModBus(), "ghost", {})


GITHUB_MANIFEST = '[mod]\nname = "needs_gh"\nevents = ["step.call"]\nrequires_plugins = ["github"]\n'


def test_mod_requiring_a_missing_plugin_fails_without_importing(tmp_path):
    write_mod(tmp_path, "needs_gh", source="raise RuntimeError('must not run')\n", manifest=GITHUB_MANIFEST)
    bus = ModBus()

    loaded = load_mods(bus, discover_mods([("user", tmp_path)]), enabled_plugins=["git"])

    assert loaded == []
    assert bus.statuses["needs_gh"].state == FAILED
    assert "github" in bus.statuses["needs_gh"].error


def test_mod_requiring_an_enabled_plugin_loads(tmp_path):
    write_mod(tmp_path, "needs_gh", manifest=GITHUB_MANIFEST)

    assert load_mods(ModBus(), discover_mods([("user", tmp_path)]), enabled_plugins=["git", "github"]) == ["needs_gh"]


def test_plugin_requirements_are_not_checked_when_enabled_plugins_is_unknown(tmp_path):
    write_mod(tmp_path, "needs_gh", manifest=GITHUB_MANIFEST)

    assert load_mods(ModBus(), discover_mods([("user", tmp_path)])) == ["needs_gh"]


def test_reload_keeps_checking_the_plugins_the_bus_was_loaded_with(tmp_path):
    from titan_cli.core.mods import reload_mod

    write_mod(tmp_path, "needs_gh", manifest=GITHUB_MANIFEST)
    bus = ModBus()
    load_mods(bus, discover_mods([("user", tmp_path)]), enabled_plugins=["git"])

    assert reload_mod(bus, "needs_gh", {}) == FAILED


def test_a_mod_that_calls_sys_exit_is_left_out_without_stopping_the_rest(tmp_path):
    write_mod(tmp_path, "a_exits_at_import", source="import sys\nsys.exit(2)\n")
    write_mod(tmp_path, "b_exits_in_register", source="import sys\ndef register(on, options):\n    sys.exit(3)\n")
    write_mod(tmp_path, "c_good")

    bus = ModBus()

    assert load_mods(bus, discover_mods([("user", tmp_path)])) == ["c_good"]
    assert bus.statuses["a_exits_at_import"].state == FAILED


def test_a_dropped_option_is_logged_without_its_value(tmp_path, monkeypatch):
    manifest = '[mod]\nname = "tok"\nversion = "1"\nevents = ["step.call"]\n\n[options.api_token]\ntype = "int"\ndefault = 1\n'
    write_mod(tmp_path, "tok", manifest=manifest)
    logged = []
    monkeypatch.setattr("titan_cli.core.mods.loader.logger.warning", lambda *a, **k: logged.append((a, k)))

    load_mods(ModBus(), discover_mods([("user", tmp_path)]), {"tok": {"options": {"api_token": "hunter2"}}})

    assert any(a == ("mod_option_dropped",) for a, _ in logged)
    assert "hunter2" not in repr(logged)


def test_a_mod_replacing_another_of_the_same_name_is_logged(tmp_path, monkeypatch):
    first, second = tmp_path / "a", tmp_path / "b"
    write_mod(first, "git")
    write_mod(second, "git")
    logged = []
    monkeypatch.setattr("titan_cli.core.mods.loader.logger.warning", lambda *a, **k: logged.append((a, k)))

    found = discover_mods([("titan", first), ("project", second)])

    assert found["git"].source == "project"
    assert [k["replaces"] for a, k in logged if a == ("mod_overrides_mod",)] == ["titan"]
