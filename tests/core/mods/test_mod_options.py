import pytest

from titan_cli.core.mods.options import parse_option_specs, resolve_options

SPECS = parse_option_specs(
    {
        "shown": {"type": "int", "default": 10, "min": 1, "max": 50},
        "ratio": {"type": "float", "default": 0.5},
        "key": {"type": "string", "default": "f5"},
        "on": {"type": "bool", "default": True},
        "dirs": {"type": "list", "default": ["a"]},
        "speed": {"type": "choice", "values": ["fast", "smart"], "default": "fast"},
    }
)


def test_defaults_apply_when_nothing_is_overridden():
    values, dropped = resolve_options(SPECS, {})

    assert values == {"shown": 10, "ratio": 0.5, "key": "f5", "on": True, "dirs": ["a"], "speed": "fast"}
    assert dropped == []


def test_valid_overrides_win():
    values, dropped = resolve_options(SPECS, {"shown": 20, "speed": "smart", "dirs": ["x", "y"], "ratio": 2})

    assert (values["shown"], values["speed"], values["dirs"], values["ratio"]) == (20, "smart", ["x", "y"], 2.0)
    assert dropped == []


@pytest.mark.parametrize(
    "name,value",
    [
        ("shown", "20"),
        ("shown", 2.5),
        ("shown", True),
        ("shown", 0),
        ("shown", 51),
        ("on", "yes"),
        ("key", 5),
        ("dirs", "a"),
        ("dirs", [1]),
        ("speed", "slow"),
    ],
)
def test_invalid_value_is_dropped_and_default_kept(name, value):
    values, dropped = resolve_options(SPECS, {name: value})

    assert values[name] == SPECS[name].default
    assert [d[0] for d in dropped] == [name]


def test_undeclared_option_is_dropped():
    values, dropped = resolve_options(SPECS, {"shwon": 5})

    assert "shwon" not in values
    assert dropped == [("shwon", "not declared in mod.toml")]


@pytest.mark.parametrize(
    "table",
    [
        {"a": 5},
        {"a": {"type": "int"}},
        {"a": {"type": "number", "default": 1}},
        {"a": {"type": "choice", "default": "x"}},
        {"a": {"type": "choice", "values": ["x"], "default": "y"}},
        {"a": {"type": "string", "default": "x", "values": ["x"]}},
        {"a": {"type": "string", "default": "x", "min": 1}},
        {"a": {"type": "int", "default": 0, "min": 1}},
        {"a": {"type": "int", "default": 1, "color": "red"}},
    ],
)
def test_malformed_declaration_is_rejected(table):
    with pytest.raises(ValueError):
        parse_option_specs(table)
