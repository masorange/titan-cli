"""Value typing: inference, parsing, and the serialization writes depend on."""

import pytest

from titan_plugin_firebase.models.values import (
    RemoteConfigValueError,
    RemoteConfigValueType,
    infer_value_type,
    normalize_value_type,
    parse_value,
    serialize_value,
)

T = RemoteConfigValueType


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", T.BOOLEAN),
        ("FALSE", T.BOOLEAN),
        ('{"a": 1}', T.JSON),
        ("[1, 2]", T.JSON),
        ("{not json", T.STRING),
        ("42", T.NUMBER),
        ("3.5", T.NUMBER),
        ("hola", T.STRING),
        ("", T.STRING),
        (None, T.UNKNOWN),
    ],
)
def test_infer_value_type(raw, expected):
    assert infer_value_type(raw) == expected


@pytest.mark.parametrize(
    "raw,value_type,expected",
    [
        ("true", T.BOOLEAN, True),
        ("false", T.BOOLEAN, False),
        ("sí", T.BOOLEAN, "sí"),
        ('{"a": 1}', T.JSON, {"a": 1}),
        ("nope", T.JSON, "nope"),
        ("42", T.NUMBER, 42),
        ("3.5", T.NUMBER, 3.5),
        ("hola", T.STRING, "hola"),
        (None, T.STRING, None),
    ],
)
def test_parse_value(raw, value_type, expected):
    assert parse_value(raw, value_type) == expected


def test_normalize_value_type_accepts_unknown_names():
    assert normalize_value_type("BOOLEAN") == T.BOOLEAN
    assert normalize_value_type("something_new") == T.UNKNOWN
    assert normalize_value_type(None) == T.UNKNOWN


@pytest.mark.parametrize(
    "raw,expected",
    [("true", "true"), ("TRUE", "true"), ("1", "true"), ("yes", "true"),
     ("false", "false"), ("0", "false"), ("Off", "false")],
)
def test_serialize_boolean_normalizes_to_api_literals(raw, expected):
    # Firebase documents "True", "1" and "0" as wrong representations, so they
    # are normalized here rather than published as strings.
    assert serialize_value(raw, T.BOOLEAN) == expected


def test_serialize_boolean_rejects_non_boolean():
    with pytest.raises(RemoteConfigValueError):
        serialize_value("maybe", T.BOOLEAN)


def test_serialize_json_compacts_and_validates():
    assert serialize_value('{ "a" : [1, 2] }', T.JSON) == '{"a":[1,2]}'
    with pytest.raises(RemoteConfigValueError):
        serialize_value("{oops}", T.JSON)


def test_serialize_json_keeps_non_ascii_readable():
    assert serialize_value('{"marca": "Yoigo ñ"}', T.JSON) == '{"marca":"Yoigo ñ"}'


def test_serialize_number_validates():
    assert serialize_value(" 42 ", T.NUMBER) == "42"
    with pytest.raises(RemoteConfigValueError):
        serialize_value("cuarenta", T.NUMBER)


def test_serialize_string_preserves_whitespace():
    # Leading/trailing spaces can be meaningful in a string parameter.
    assert serialize_value("  hola  ", T.STRING) == "  hola  "
