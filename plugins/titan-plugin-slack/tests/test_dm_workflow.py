from pathlib import Path

import yaml


def test_send_slack_direct_message_workflow_structure() -> None:
    workflow_path = (
        Path(__file__).parent.parent / "titan_plugin_slack" / "workflows" / "send-slack-direct-message.yaml"
    )

    with open(workflow_path, encoding="utf-8") as handle:
        workflow = yaml.safe_load(handle)

    assert workflow["name"] == "Send Slack Direct Message"
    step_ids = [step["id"] for step in workflow["steps"]]
    assert step_ids == [
        "validate_connection",
        "select_user_target",
        "open_direct_message",
        "prompt_message_body",
        "post_message",
    ]
