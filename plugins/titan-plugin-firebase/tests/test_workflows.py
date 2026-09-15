"""The shipped workflows are valid and only reference registered steps."""

import pytest
import yaml

from titan_plugin_firebase.plugin import FirebasePlugin


def _load(name: str) -> dict:
    # Ask the plugin where its workflows live instead of rebuilding the path:
    # workflows_path is what Titan itself reads, so the test breaks if that
    # accessor ever stops pointing at the shipped files.
    workflows_path = FirebasePlugin().workflows_path
    assert workflows_path is not None
    with open(workflows_path / name, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.mark.parametrize(
    "name",
    [
        "read-remoteconfig.yaml",
        "set-remoteconfig-value.yaml",
        "set-remoteconfig-value-multiproject.yaml",
    ],
)
def test_every_step_is_registered(name):
    workflow = _load(name)
    registered = set(FirebasePlugin().get_steps())

    for step in workflow["steps"]:
        assert step["plugin"] == "firebase"
        assert step["step"] in registered, step["step"]


def test_read_workflow_structure():
    workflow = _load("read-remoteconfig.yaml")

    assert workflow["name"] == "Read Firebase Remote Config"
    assert [step["id"] for step in workflow["steps"]] == [
        "firebase_auth_check",
        "firebase_select_target",
        "firebase_remoteconfig_get",
        "firebase_remoteconfig_conditions",
        "firebase_remoteconfig_select_key",
    ]


def test_write_workflow_gates_publishing_behind_the_diff():
    workflow = _load("set-remoteconfig-value.yaml")
    ids = [step["id"] for step in workflow["steps"]]

    assert workflow["params"]["dry_run"] is False
    # The order is the safety property: read, choose target, enter value,
    # review, and only then publish.
    assert ids == [
        "firebase_auth_check",
        "firebase_select_target",
        "firebase_remoteconfig_get",
        "firebase_remoteconfig_conditions",
        "firebase_remoteconfig_select_key",
        "firebase_remoteconfig_set_value",
        "firebase_remoteconfig_diff",
        "firebase_remoteconfig_publish",
    ]
    assert ids.index("firebase_remoteconfig_diff") < ids.index(
        "firebase_remoteconfig_publish"
    )


def test_multiproject_workflow_confirms_before_publishing():
    workflow = _load("set-remoteconfig-value-multiproject.yaml")
    ids = [step["id"] for step in workflow["steps"]]

    assert workflow["params"]["dry_run"] is False
    # project_ids is declared so the workflow is usable on its own; another
    # plugin can instead publish firebase_project_ids from its own step.
    assert workflow["params"]["project_ids"] == ""
    # The plan step is where each project is validated and confirmed;
    # publishing cannot run before it.
    assert ids == [
        "firebase_auth_check",
        "firebase_select_targets",
        "firebase_remoteconfig_fanout_plan",
        "firebase_remoteconfig_fanout_publish",
    ]
