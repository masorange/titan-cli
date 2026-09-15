"""HTTP behaviour of the Remote Config executor."""

import pytest

from titan_plugin_firebase.exceptions import FirebaseApiError


def test_get_template_returns_payload_and_etag(
    make_network, make_response, template_payload
):
    network = make_network(
        [make_response(200, template_payload, {"ETag": "etag-1"})]
    )
    template, etag = network.get_template("mm-firebase-yoigo")

    assert etag == "etag-1"
    assert set(template.parameters) == {
        "feature_enabled",
        "welcome_text",
        "legacy_untyped",
    }
    call = network.fake_session.calls[0]
    assert call["url"] == (
        "https://rc.example.com/v1/projects/mm-firebase-yoigo/remoteConfig"
    )
    # The API docs require this header on every request.
    assert call["headers"]["Accept-Encoding"] == "gzip"
    assert call["headers"]["x-goog-user-project"] == "mm-firebase-yoigo"
    assert call["timeout"] == 7


def test_quota_project_override_is_sent(
    make_network, make_response, template_payload
):
    network = make_network(
        [make_response(200, template_payload, {"ETag": "e"})],
        quota_project_id="mm-ragnarok-dev",
    )
    network.get_template("mm-firebase-yoigo")
    assert (
        network.fake_session.calls[0]["headers"]["x-goog-user-project"]
        == "mm-ragnarok-dev"
    )


@pytest.mark.parametrize("project_id", ["", "  ", "UPPER", "ab", "ends-"])
def test_invalid_project_ids_never_reach_the_network(make_network, project_id):
    network = make_network([])
    with pytest.raises(FirebaseApiError):
        network.get_template(project_id)
    assert network.fake_session.calls == []


@pytest.mark.parametrize(
    "status,fragment",
    [
        (401, "gcloud auth application-default login"),
        (403, "serviceusage.services.use"),
        (404, "No existe el proyecto"),
        (409, "ETag"),
        (400, "ETag"),
        (500, "estado 500"),
    ],
)
def test_error_statuses_explain_what_to_do(
    make_network, make_response, status, fragment
):
    network = make_network(
        [make_response(status, {"error": {"message": "denied"}})]
    )
    with pytest.raises(FirebaseApiError) as exc:
        network.get_template("mm-firebase-yoigo")
    assert exc.value.status_code == status
    assert fragment in str(exc.value)
    assert "denied" in str(exc.value)


def test_non_json_response_is_rejected(make_network, make_response):
    network = make_network(
        [make_response(200, None, {"ETag": "e"}, text="<html>")]
    )
    with pytest.raises(FirebaseApiError):
        network.get_template("mm-firebase-yoigo")


def test_non_object_json_is_rejected(make_network, make_response):
    network = make_network([make_response(200, [1, 2], {"ETag": "e"})])
    with pytest.raises(FirebaseApiError):
        network.get_template("mm-firebase-yoigo")


def test_put_sends_if_match_and_content_type(
    make_network, make_response, template_payload
):
    network = make_network(
        [make_response(200, template_payload, {"ETag": "etag-2"})]
    )
    template, etag = network.put_template(
        "mm-firebase-yoigo",
        {"parameters": {}},
        etag="etag-1",
    )

    call = network.fake_session.calls[0]
    assert call["method"] == "PUT"
    assert call["url"].endswith("/remoteConfig")
    assert call["headers"]["If-Match"] == "etag-1"
    assert call["headers"]["Content-Type"] == "application/json; UTF8"
    assert call["json"] == {"parameters": {}}
    assert etag == "etag-2"
    assert template.version.version_number == "42"


def test_put_with_validate_only_uses_the_query_parameter(
    make_network, make_response, template_payload
):
    network = make_network(
        [make_response(200, template_payload, {"ETag": "e-0"})]
    )
    network.put_template(
        "mm-firebase-yoigo",
        {"parameters": {}},
        etag="etag-1",
        validate_only=True,
    )
    assert network.fake_session.calls[0]["url"].endswith("?validate_only=true")


def test_put_without_etag_is_refused_before_the_request(make_network):
    # Publishing with no If-Match (or with "*") silently overwrites whoever is
    # editing the console, so it is rejected rather than offered.
    network = make_network([])
    with pytest.raises(FirebaseApiError) as exc:
        network.put_template("mm-firebase-yoigo", {}, etag="  ")
    assert "If-Match" in str(exc.value)
    assert network.fake_session.calls == []


def test_request_exception_is_wrapped(make_network, monkeypatch):
    import requests

    network = make_network([])

    def _boom(*args, **kwargs):
        raise requests.ConnectionError("dns")

    monkeypatch.setattr(network.fake_session, "get", _boom)
    with pytest.raises(FirebaseApiError) as exc:
        network.get_template("mm-firebase-yoigo")
    assert "dns" in str(exc.value)
