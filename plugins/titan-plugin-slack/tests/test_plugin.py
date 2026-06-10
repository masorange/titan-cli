from titan_plugin_slack.plugin import SlackPlugin


def test_slack_plugin_basic_properties() -> None:
    plugin = SlackPlugin()

    assert plugin.name == "slack"
    assert plugin.description == "Provides Slack messaging and workspace integration."
    assert plugin.dependencies == []


def test_slack_plugin_has_no_steps_in_phase_one() -> None:
    plugin = SlackPlugin()

    assert plugin.get_steps() == {}


def test_slack_plugin_exposes_workflows_path() -> None:
    plugin = SlackPlugin()

    assert plugin.workflows_path.name == "workflows"
