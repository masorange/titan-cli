from unittest.mock import MagicMock, PropertyMock

from titan_cli.core.plugins.models import PluginPin, PluginPinScope
from titan_cli.core.plugins.community_sources import PluginChannel
from titan_cli.ui.tui.screens.main_menu import MainMenuScreen
from titan_cli.ui.tui.screens.plugin_management import PluginManagementScreen


def test_main_menu_builds_project_stable_records_from_shared_pin():
    config = MagicMock()
    config.get_enabled_plugins.return_value = ["sample", "disabled"]
    config.get_plugin_pin.side_effect = lambda plugin: {
        "sample": PluginPin(scope=PluginPinScope.PROJECT, repo_url="https://github.com/example/sample-plugin", resolved_commit="a" * 40, requested_ref="v1.2.3"),
        "disabled": None,
    }[plugin]

    screen = MainMenuScreen(config, show_dock=False)

    records = screen._get_project_stable_records()

    assert len(records) == 1
    assert records[0].titan_plugin_name == "sample"
    assert records[0].channel == PluginChannel.STABLE
    assert records[0].requested_ref == "v1.2.3"
    assert records[0].resolved_commit == "a" * 40


def test_main_menu_notifies_plugin_sync_events():
    config = MagicMock()
    config.get_plugin_sync_events.return_value = ["Syncing plugin 'sample' to project version v1.2.3."]

    screen = MainMenuScreen(config, show_dock=False)
    app = MagicMock()
    type(screen).app = PropertyMock(return_value=app)
    screen.run_worker = MagicMock()

    screen.on_mount()

    app.notify.assert_called_once_with(
        "Syncing plugin 'sample' to project version v1.2.3.",
        severity="information",
        timeout=6,
    )
    screen.run_worker.assert_called_once()
    worker_coro = screen.run_worker.call_args.args[0]
    worker_coro.close()


def test_plugin_management_builds_stable_record_from_project_pin():
    config = MagicMock()
    config.get_plugin_pin.return_value = PluginPin(scope=PluginPinScope.PROJECT, repo_url="https://github.com/example/sample-plugin", resolved_commit="b" * 40, requested_ref="v2.0.0")
    config.get_plugin_source_path.return_value = None

    screen = PluginManagementScreen(config)

    record = screen._build_stable_record("sample")

    assert record is not None
    assert record.titan_plugin_name == "sample"
    assert record.channel == PluginChannel.STABLE
    assert record.requested_ref == "v2.0.0"
    assert record.resolved_commit == "b" * 40


def test_plugin_management_detects_community_plugin_from_dev_path_only():
    config = MagicMock()
    config.get_plugin_pin.return_value = None
    config.get_plugin_source_path.return_value = "/tmp/dev-plugin"

    screen = PluginManagementScreen(config)

    assert screen._build_stable_record("sample") is None
    assert screen._is_community_plugin("sample") is True


def test_remove_project_pinned_plugin_drops_project_entry_and_dev_override():
    config = MagicMock()
    config.get_plugin_pin.return_value = PluginPin(
        scope=PluginPinScope.PROJECT, repo_url="u", resolved_commit="a" * 40, requested_ref="v1"
    )
    screen = PluginManagementScreen(config)

    assert screen._remove_plugin("sample") is PluginPinScope.PROJECT

    config.remove_plugin_from_project.assert_called_once_with("sample")
    config.clear_plugin_pin.assert_not_called()
    config.clear_local_plugin_override.assert_called_once_with("sample")


def test_remove_globally_pinned_plugin_clears_only_the_global_pin():
    config = MagicMock()
    config.get_plugin_pin.return_value = PluginPin(
        scope=PluginPinScope.GLOBAL, repo_url="u", resolved_commit="a" * 40, requested_ref="v1"
    )
    screen = PluginManagementScreen(config)

    assert screen._remove_plugin("sample") is PluginPinScope.GLOBAL

    config.clear_plugin_pin.assert_called_once_with("sample", PluginPinScope.GLOBAL)
    config.remove_plugin_from_project.assert_not_called()
    config.clear_local_plugin_override.assert_called_once_with("sample")


def test_pin_scope_label_reports_where_the_pin_lives():
    config = MagicMock()
    screen = PluginManagementScreen(config)

    config.get_plugin_pin.return_value = PluginPin(
        scope=PluginPinScope.GLOBAL, repo_url="u", resolved_commit="a" * 40
    )
    assert screen._pin_scope_label("sample") == "global"

    config.get_plugin_pin.return_value = None
    assert screen._pin_scope_label("sample") == "project"


def test_toggle_disables_a_global_plugin_for_this_project_only(mocker):
    config = MagicMock()
    config.is_plugin_enabled.return_value = True
    screen = PluginManagementScreen(config)
    screen.selected_plugin = "sample"
    mocker.patch.object(PluginManagementScreen, "app", new_callable=PropertyMock, return_value=MagicMock())
    mocker.patch.object(screen, "_load_plugins")

    screen.action_toggle_plugin()

    config.set_plugin_enabled_in_project.assert_called_once_with("sample", False)


def _stable_record():
    from titan_cli.core.plugins.community_sources import CommunityPluginRecord

    return CommunityPluginRecord(
        repo_url="https://github.com/example/sample-plugin",
        package_name="sample",
        titan_plugin_name="sample",
        installed_at="",
        channel=PluginChannel.STABLE,
        dev_local_path=None,
        requested_ref="0.10.0",
        resolved_commit="c" * 40,
    )


def test_run_update_does_not_pin_an_incompatible_candidate(mocker):
    import asyncio

    config = MagicMock()
    screen = PluginManagementScreen(config)
    app = MagicMock()
    mocker.patch.object(PluginManagementScreen, "app", new_callable=PropertyMock, return_value=app)

    mocker.patch("titan_cli.ui.tui.screens.plugin_management.get_github_token", return_value=None)
    mocker.patch("titan_cli.ui.tui.screens.plugin_management.check_for_update", return_value="0.12.0")
    mocker.patch(
        "titan_cli.core.plugins.community_sources.resolve_ref_to_commit_sha",
        return_value=("d" * 40, None),
    )
    mocker.patch.object(
        screen,
        "_check_candidate_incompatibility",
        return_value="requires titan-cli >=0.9, but titan-cli 0.8.0 is running.",
    )
    
    asyncio.run(screen._run_update(_stable_record()))

    config.set_plugin_pin.assert_not_called()
    error_messages = [
        call.kwargs | {"message": call.args[0]}
        for call in app.notify.call_args_list
    ]
    assert any(
        m.get("severity") == "error" and "requires titan-cli >=0.9" in m["message"]
        for m in error_messages
    )


def test_check_candidate_incompatibility_only_blocks_on_positive_detection(mocker):
    from titan_cli.core.plugins.community_sources import PluginHost

    config = MagicMock()
    screen = PluginManagementScreen(config)

    fetch = mocker.patch(
        "titan_cli.core.plugins.community_sources.fetch_pyproject_toml",
        return_value=(None, "network_error"),
    )
    assert screen._check_candidate_incompatibility(
        "https://github.com/example/sample-plugin", "e" * 40, PluginHost.GITHUB, None
    ) is None
    assert fetch.called

    fetch.return_value = (
        '[project]\nname = "sample"\ndependencies = ["titan-cli>=999.0"]',
        None,
    )
    message = screen._check_candidate_incompatibility(
        "https://github.com/example/sample-plugin", "e" * 40, PluginHost.GITHUB, None
    )
    assert message is not None and ">=999.0" in message


def _install_screen(scope):
    from titan_cli.ui.tui.screens.install_plugin_screen import InstallPluginScreen

    config = MagicMock()
    screen = InstallPluginScreen(config)
    screen._scope = scope
    screen._base_url = "https://github.com/example/sample-plugin"
    screen._requested_ref = "v1.0.0"
    screen._resolved_commit = "a" * 40
    screen._runtime_manager = MagicMock()
    return screen, config


def test_install_wizard_pins_in_the_chosen_scope():
    for scope in (PluginPinScope.PROJECT, PluginPinScope.GLOBAL):
        screen, config = _install_screen(scope)

        assert screen._prepare_plugin_install("sample") is None

        config.set_plugin_pin.assert_called_once_with(
            "sample",
            scope,
            repo_url="https://github.com/example/sample-plugin",
            requested_ref="v1.0.0",
            resolved_commit="a" * 40,
            subdirectory=None,
        )
        screen._runtime_manager.ensure_stable_runtime.assert_called_once()


def test_install_wizard_reports_a_failed_save_without_provisioning():
    screen, config = _install_screen(PluginPinScope.GLOBAL)
    config.set_plugin_pin.side_effect = OSError("read-only home")

    assert "read-only home" in screen._prepare_plugin_install("sample")
    screen._runtime_manager.ensure_stable_runtime.assert_not_called()
