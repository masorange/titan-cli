from pathlib import Path

import yaml


def test_discover_slack_workspace_workflow_structure() -> None:
    workflow_path = (
        Path(__file__).parent.parent / "titan_plugin_slack" / "workflows" / "discover-slack-workspace.yaml"
    )

    with open(workflow_path, encoding="utf-8") as handle:
        workflow = yaml.safe_load(handle)

    assert workflow["name"] == "Discover Slack Workspace"
    assert workflow["params"]["slack_limit"] == 20
    assert workflow["params"]["slack_exclude_archived"] is True

    steps = workflow["steps"]
    assert [step["id"] for step in steps] == [
        "validate_connection",
        "list_public_channels",
        "list_users",
    ]

    assert steps[0]["plugin"] == "slack"
    assert steps[0]["step"] == "validate_connection"
    assert steps[1]["step"] == "list_public_channels"
    assert steps[2]["step"] == "list_users"


def test_send_slack_direct_message_workflow_structure() -> None:
    workflow_path = (
        Path(__file__).parent.parent / "titan_plugin_slack" / "workflows" / "send-slack-direct-message.yaml"
    )

    with open(workflow_path, encoding="utf-8") as handle:
        workflow = yaml.safe_load(handle)

    assert workflow["name"] == "Send Slack Direct Message"
    assert [step["id"] for step in workflow["steps"]] == [
        "validate_connection",
        "select_user_target",
        "prepare_message_destination",
        "prompt_message_body",
        "post_message",
    ]
    assert workflow["steps"][2]["step"] == "prepare_message_destination"


def test_send_slack_channel_message_workflow_structure() -> None:
    workflow_path = (
        Path(__file__).parent.parent / "titan_plugin_slack" / "workflows" / "send-slack-channel-message.yaml"
    )

    with open(workflow_path, encoding="utf-8") as handle:
        workflow = yaml.safe_load(handle)

    assert workflow["name"] == "Send Slack Channel Message"
    assert [step["id"] for step in workflow["steps"]] == [
        "validate_connection",
        "select_channel_target",
        "prepare_message_destination",
        "prompt_message_body",
        "post_message",
    ]
