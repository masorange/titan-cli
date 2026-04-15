from unittest.mock import MagicMock

from titan_cli.core.plugins.community_sources import PluginChannel
from titan_cli.ui.tui.screens.main_menu import MainMenuScreen
from titan_cli.ui.tui.screens.plugin_management import PluginManagementScreen


def test_main_menu_builds_project_stable_records_from_shared_pin():
    config = MagicMock()
    config.get_enabled_plugins.return_value = ["sample", "disabled"]
    config.get_project_plugin_repo_url.side_effect = lambda plugin: {
        "sample": "https://github.com/example/sample-plugin",
        "disabled": None,
    }[plugin]
    config.get_project_plugin_resolved_commit.side_effect = lambda plugin: {
        "sample": "a" * 40,
        "disabled": None,
    }[plugin]
    config.get_project_plugin_requested_ref.side_effect = lambda plugin: {
        "sample": "v1.2.3",
        "disabled": None,
    }[plugin]

    screen = MainMenuScreen(config, show_status_bar=False)

    records = screen._get_project_stable_records()

    assert len(records) == 1
    assert records[0].titan_plugin_name == "sample"
    assert records[0].channel == PluginChannel.STABLE
    assert records[0].requested_ref == "v1.2.3"
    assert records[0].resolved_commit == "a" * 40


def test_plugin_management_builds_stable_record_from_project_pin():
    config = MagicMock()
    config.get_project_plugin_repo_url.return_value = "https://github.com/example/sample-plugin"
    config.get_project_plugin_resolved_commit.return_value = "b" * 40
    config.get_project_plugin_requested_ref.return_value = "v2.0.0"
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
    config.get_project_plugin_repo_url.return_value = None
    config.get_project_plugin_resolved_commit.return_value = None
    config.get_project_plugin_requested_ref.return_value = None
    config.get_plugin_source_path.return_value = "/tmp/dev-plugin"

    screen = PluginManagementScreen(config)

    assert screen._build_stable_record("sample") is None
    assert screen._is_community_plugin("sample") is True
