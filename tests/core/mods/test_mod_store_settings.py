import json
import tomllib

import pytest

from titan_cli.core.errors import ConfigWriteError
from titan_cli.core.mods.settings import set_mod_enabled
from titan_cli.core.mods.store import ModStore


def store(tmp_path):
    return ModStore("demo", root=lambda: tmp_path)


def test_a_store_file_that_is_not_an_object_reads_as_empty(tmp_path):
    (tmp_path / "demo.json").write_text("[1, 2]")

    assert store(tmp_path).get("k", "fallback") == "fallback"
    s = store(tmp_path)
    s.set("k", 1)
    assert s.get("k") == 1


def test_a_value_json_cannot_encode_leaves_the_stored_data_alone(tmp_path):
    s = store(tmp_path)
    s.set("keep", 1)
    loop: list = []
    loop.append(loop)

    s.set("bad", loop)

    assert json.loads((tmp_path / "demo.json").read_text()) == {"keep": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["demo.json"]


def test_toggling_a_mod_writes_the_scoped_setting_and_keeps_other_config(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[ai]\nprovider = "x"\n')

    set_mod_enabled("git", False, project_root=tmp_path, config_path=config)

    data = tomllib.loads(config.read_text())
    assert data["ai"] == {"provider": "x"}
    (scoped,) = data["project_sources"].values()
    assert scoped["mods"]["git"]["enabled"] is False
    assert [p.name for p in tmp_path.iterdir() if p.name != "config.toml"] == []


def test_a_malformed_config_is_reported_and_left_untouched(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("not = [valid")

    with pytest.raises(ConfigWriteError):
        set_mod_enabled("git", True, project_root=tmp_path, config_path=config)

    assert config.read_text() == "not = [valid"


def test_a_non_table_node_in_the_way_is_replaced_not_crashed_on(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('project_sources = "oops"\n')

    set_mod_enabled("git", True, project_root=tmp_path, config_path=config)

    (scoped,) = tomllib.loads(config.read_text())["project_sources"].values()
    assert scoped["mods"]["git"]["enabled"] is True
