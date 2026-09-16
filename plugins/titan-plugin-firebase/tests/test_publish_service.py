"""The write path: read, modify, validate, publish, and ETag recovery."""

import pytest

from titan_cli.core.result import ClientError, ClientSuccess

from titan_plugin_firebase.clients.services.remoteconfig_service import (
    RemoteConfigService,
)
from titan_plugin_firebase.operations.template_operations import build_change_set

PROJECT = "mm-firebase-yoigo"


def _published(payload: dict, version_number: str = "43") -> dict:
    """The template Firebase echoes back after a publish."""
    answer = dict(payload)
    answer["version"] = {
        "versionNumber": version_number,
        "updateUser": {"email": "alex@example.com"},
        "updateOrigin": "REST_API",
        "updateType": "INCREMENTAL_UPDATE",
        "description": "Titan: feature_enabled = true [valor por defecto]",
    }
    return answer


@pytest.fixture
def change_set(template_payload):
    """A validated boolean flip of the default value."""
    return build_change_set(template_payload, "feature_enabled", "TRUE", [None])


@pytest.fixture
def multi_target_change_set(template_payload):
    """The same value written to the default value and to a condition."""
    return build_change_set(
        template_payload, "feature_enabled", "TRUE", [None, "android_prod"]
    )


def test_validate_change_reports_the_replaced_value(
    make_network, make_response, template_payload
):
    service = RemoteConfigService(
        make_network([make_response(200, template_payload, {"ETag": "e1"})])
    )
    result = service.validate_change_set(PROJECT, "feature_enabled", "TRUE")

    assert isinstance(result, ClientSuccess)
    assert result.data.new_raw_value == "true"
    assert [c.old_raw_value for c in result.data.changes] == ["false"]


def test_validate_change_rejects_an_invalid_value(
    make_network, make_response, template_payload
):
    service = RemoteConfigService(
        make_network([make_response(200, template_payload, {"ETag": "e1"})])
    )
    result = service.validate_change_set(PROJECT, "feature_enabled", "quizá")

    assert isinstance(result, ClientError)
    assert result.error_code == "INVALID_VALUE"
    assert result.log_level == "warning"


def test_validate_change_rejects_an_unknown_condition(
    make_network, make_response, template_payload
):
    service = RemoteConfigService(
        make_network([make_response(200, template_payload, {"ETag": "e1"})])
    )
    result = service.validate_change_set(PROJECT, "feature_enabled", "true", "ios_beta")

    assert isinstance(result, ClientError)
    assert result.error_code == "TEMPLATE_EDIT_ERROR"


def test_publish_sends_the_read_etag_and_the_modified_template(
    make_network, make_response, template_payload, change_set
):
    network = make_network(
        [
            make_response(200, template_payload, {"ETag": "e1"}),
            make_response(200, _published(template_payload), {"ETag": "e2"}),
        ]
    )

    result = RemoteConfigService(network).publish_change_set(PROJECT, change_set)

    assert isinstance(result, ClientSuccess)
    assert result.data.version_number == "43"
    assert result.data.version.update_origin == "REST_API"
    # The audit trail names the person behind the ADC token.
    assert result.data.version.update_user_email == "alex@example.com"
    assert result.data.retried_after_conflict is False

    put = network.fake_session.calls[-1]
    assert put["method"] == "PUT"
    assert put["headers"]["If-Match"] == "e1"
    assert (
        put["json"]["parameters"]["feature_enabled"]["defaultValue"]["value"] == "true"
    )
    assert put["json"]["version"] == {
        "description": "Titan: feature_enabled = true [valor por defecto]"
    }


def test_publish_reads_again_right_before_writing(
    make_network, make_response, template_payload, change_set
):
    network = make_network(
        [
            make_response(200, template_payload, {"ETag": "e1"}),
            make_response(200, _published(template_payload), {"ETag": "e2"}),
        ]
    )
    RemoteConfigService(network).publish_change_set(PROJECT, change_set)

    # The read happens inside the publish, so the ETag is fresh even if the
    # user spent a while reviewing the diff.
    assert [call["method"] for call in network.fake_session.calls] == ["GET", "PUT"]


def test_validate_only_does_not_publish(
    make_network, make_response, template_payload, change_set
):
    network = make_network(
        [
            make_response(200, template_payload, {"ETag": "e1"}),
            make_response(200, template_payload, {"ETag": "e1-0"}),
        ]
    )

    result = RemoteConfigService(network).publish_change_set(
        PROJECT, change_set, validate_only=True
    )

    assert isinstance(result, ClientSuccess)
    assert result.data.validated_only is True
    assert network.fake_session.calls[-1]["url"].endswith("?validate_only=true")


def test_etag_conflict_is_retried_against_the_fresh_template(
    make_network, make_response, template_payload, change_set
):
    fresh = dict(template_payload)
    network = make_network(
        [
            # First cycle: read, then a conflicting publish.
            make_response(200, template_payload, {"ETag": "e1"}),
            make_response(409, {"error": {"message": "etag mismatch"}}),
            # Retry: read the new template, publish over its ETag.
            make_response(200, fresh, {"ETag": "e9"}),
            make_response(200, _published(fresh, "44"), {"ETag": "e10"}),
        ]
    )

    result = RemoteConfigService(network).publish_change_set(PROJECT, change_set)

    assert isinstance(result, ClientSuccess)
    assert result.data.retried_after_conflict is True
    assert result.data.version_number == "44"
    assert "ETag" in result.message
    # The retry re-read first: the second PUT carries the new ETag, not the old
    # one, which is what keeps a concurrent console edit from being lost.
    puts = [call for call in network.fake_session.calls if call["method"] == "PUT"]
    assert [put["headers"]["If-Match"] for put in puts] == ["e1", "e9"]


def test_a_second_conflict_is_reported_instead_of_retried_forever(
    make_network, make_response, template_payload, change_set
):
    network = make_network(
        [
            make_response(200, template_payload, {"ETag": "e1"}),
            make_response(409, {"error": {"message": "again"}}),
            make_response(200, template_payload, {"ETag": "e2"}),
            make_response(409, {"error": {"message": "again"}}),
        ]
    )

    result = RemoteConfigService(network).publish_change_set(PROJECT, change_set)

    assert isinstance(result, ClientError)
    assert result.error_code == "ETAG_CONFLICT"


def test_publish_fails_when_the_read_returns_no_etag(
    make_network, make_response, template_payload, change_set
):
    network = make_network([make_response(200, template_payload, {})])

    result = RemoteConfigService(network).publish_change_set(PROJECT, change_set)

    assert isinstance(result, ClientError)
    assert result.error_code == "MISSING_ETAG"
    # Nothing was written: publishing without If-Match would clobber whoever
    # is editing the console.
    assert [call["method"] for call in network.fake_session.calls] == ["GET"]


def test_publish_fails_when_the_parameter_disappeared(
    make_network, make_response, template_payload, change_set
):
    without_parameter = {
        "conditions": template_payload["conditions"],
        "parameters": {"other": {"defaultValue": {"value": "x"}}},
    }
    network = make_network([make_response(200, without_parameter, {"ETag": "e2"})])

    result = RemoteConfigService(network).publish_change_set(PROJECT, change_set)

    assert isinstance(result, ClientError)
    assert result.error_code == "TEMPLATE_EDIT_ERROR"


def test_publish_reports_permission_denied_as_is(
    make_network, make_response, template_payload, change_set
):
    network = make_network(
        [
            make_response(200, template_payload, {"ETag": "e1"}),
            make_response(403, {"error": {"message": "no update permission"}}),
        ]
    )

    result = RemoteConfigService(network).publish_change_set(PROJECT, change_set)

    assert isinstance(result, ClientError)
    assert result.error_code == "PERMISSION_DENIED"
    assert "no update permission" in result.error_message


def test_a_multi_target_set_publishes_one_version(
    make_network, make_response, template_payload, multi_target_change_set
):
    network = make_network(
        [
            make_response(200, template_payload, {"ETag": "e1"}),
            make_response(200, _published(template_payload), {"ETag": "e2"}),
        ]
    )

    result = RemoteConfigService(network).publish_change_set(
        PROJECT, multi_target_change_set
    )

    assert isinstance(result, ClientSuccess)
    # One PUT, not two: the template is replaced whole, so writing the default
    # value and a conditional value is a single Remote Config version.
    puts = [call for call in network.fake_session.calls if call["method"] == "PUT"]
    assert len(puts) == 1
    parameter = puts[0]["json"]["parameters"]["feature_enabled"]
    assert parameter["defaultValue"]["value"] == "true"
    assert parameter["conditionalValues"]["android_prod"]["value"] == "true"
    # android_prod already holds "true", so the version description names only
    # the target that actually changes — the history should say what changed.
    assert puts[0]["json"]["version"]["description"] == (
        "Titan: feature_enabled = true [valor por defecto]"
    )
    assert [c.target_label for c in multi_target_change_set.pending] == [
        "valor por defecto"
    ]


def test_validate_change_set_rejects_an_unknown_target_in_the_list(
    make_network, make_response, template_payload
):
    service = RemoteConfigService(
        make_network([make_response(200, template_payload, {"ETag": "e1"})])
    )
    result = service.validate_change_set(
        PROJECT, "feature_enabled", "true", [None, "ios_beta"]
    )

    # One bad target invalidates the whole set rather than silently writing the
    # good ones: the user asked for both.
    assert isinstance(result, ClientError)
    assert result.error_code == "TEMPLATE_EDIT_ERROR"
