
import tomli

from titan_cli.core.plugins.community import (
    CommunityPluginRecord,
    PluginChannel,
    PluginHost,
    check_for_update,
    get_community_plugin_by_name_and_channel,
    load_community_plugins,
    remove_community_plugin_by_channel,
    remove_community_plugin_by_name,
    resolve_ref_to_commit_sha,
    save_community_plugin,
)


def test_resolve_ref_to_commit_sha_accepts_full_sha_for_any_host():
    sha = "a" * 40

    resolved, error = resolve_ref_to_commit_sha(
        "https://gitlab.com/example/plugin",
        sha,
        PluginHost.GITLAB,
    )

    assert resolved == sha
    assert error is None


def test_resolve_ref_to_commit_sha_rejects_non_github_partial_refs():
    resolved, error = resolve_ref_to_commit_sha(
        "https://gitlab.com/example/plugin",
        "v1.2.3",
        PluginHost.GITLAB,
    )

    assert resolved is None
    assert "full commit SHA" in error


def test_resolve_ref_to_commit_sha_resolves_annotated_github_tag(mocker):
    responses = [
        {"object": {"type": "tag", "sha": "b" * 40}},
        {"object": {"sha": "c" * 40}},
    ]

    class DummyResponse:
        def __init__(self, payload):
            self.payload = payload

        def read(self):
            import json
            return json.dumps(self.payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(req, timeout):
        return DummyResponse(responses.pop(0))

    mocker.patch("titan_cli.core.plugins.community.urlopen", side_effect=fake_urlopen)

    resolved, error = resolve_ref_to_commit_sha(
        "https://github.com/example/plugin",
        "v1.2.3",
        PluginHost.GITHUB,
    )

    assert resolved == "c" * 40
    assert error is None


def test_save_and_load_community_plugin_supports_legacy_records(tmp_path, monkeypatch):
    path = tmp_path / "community_plugins.toml"
    path.write_text(
        """
[[plugins]]
repo_url = "https://github.com/example/plugin"
package_name = "example-plugin"
titan_plugin_name = "example"
installed_at = "2026-04-07T00:00:00+00:00"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "titan_cli.core.plugins.community.COMMUNITY_PLUGINS_FILE",
        path,
    )

    records = load_community_plugins()

    assert len(records) == 1
    assert records[0].channel == PluginChannel.STABLE
    assert records[0].requested_ref is None
    assert records[0].resolved_commit is None


def test_save_community_plugin_omits_none_values(tmp_path, monkeypatch):
    path = tmp_path / "community_plugins.toml"
    monkeypatch.setattr(
        "titan_cli.core.plugins.community.COMMUNITY_PLUGINS_FILE",
        path,
    )

    save_community_plugin(
        CommunityPluginRecord(
            repo_url="https://github.com/example/plugin",
            package_name="example-plugin",
            titan_plugin_name="example",
            installed_at="2026-04-07T00:00:00+00:00",
            channel=PluginChannel.STABLE,
            dev_local_path=None,
            requested_ref="v1.0.0",
            resolved_commit=None,
        )
    )

    with open(path, "rb") as f:
        data = tomli.load(f)

    plugin_data = data["plugins"][0]
    assert "dev_local_path" not in plugin_data
    assert "resolved_commit" not in plugin_data
    assert plugin_data["requested_ref"] == "v1.0.0"


def test_remove_community_plugin_by_channel_keeps_other_channel(tmp_path, monkeypatch):
    path = tmp_path / "community_plugins.toml"
    monkeypatch.setattr(
        "titan_cli.core.plugins.community.COMMUNITY_PLUGINS_FILE",
        path,
    )

    save_community_plugin(
        CommunityPluginRecord(
            repo_url="https://github.com/example/plugin",
            package_name="example-plugin",
            titan_plugin_name="example",
            installed_at="2026-04-07T00:00:00+00:00",
            channel=PluginChannel.STABLE,
            dev_local_path=None,
            requested_ref="v1.0.0",
            resolved_commit="a" * 40,
        )
    )
    save_community_plugin(
        CommunityPluginRecord(
            repo_url="",
            package_name="example-plugin",
            titan_plugin_name="example",
            installed_at="2026-04-07T00:00:00+00:00",
            channel=PluginChannel.DEV_LOCAL,
            dev_local_path="/tmp/example-plugin",
            requested_ref=None,
            resolved_commit=None,
        )
    )

    remove_community_plugin_by_channel("example", PluginChannel.STABLE)

    stable_record = get_community_plugin_by_name_and_channel("example", PluginChannel.STABLE)
    dev_record = get_community_plugin_by_name_and_channel("example", PluginChannel.DEV_LOCAL)

    assert stable_record is None
    assert dev_record is not None
    assert dev_record.dev_local_path == "/tmp/example-plugin"


def test_remove_community_plugin_by_name_removes_all_channels(tmp_path, monkeypatch):
    path = tmp_path / "community_plugins.toml"
    monkeypatch.setattr(
        "titan_cli.core.plugins.community.COMMUNITY_PLUGINS_FILE",
        path,
    )

    for channel, repo_url in (
        (PluginChannel.STABLE, "https://github.com/example/plugin"),
        (PluginChannel.DEV_LOCAL, ""),
    ):
        save_community_plugin(
            CommunityPluginRecord(
                repo_url=repo_url,
                package_name="example-plugin",
                titan_plugin_name="example",
                installed_at="2026-04-07T00:00:00+00:00",
                channel=channel,
                dev_local_path="/tmp/example-plugin" if channel == PluginChannel.DEV_LOCAL else None,
                requested_ref="v1.0.0" if channel == PluginChannel.STABLE else None,
                resolved_commit="a" * 40 if channel == PluginChannel.STABLE else None,
            )
        )

    remove_community_plugin_by_name("example")

    assert load_community_plugins() == []


def test_check_for_update_returns_none_for_dev_local():
    record = CommunityPluginRecord(
        repo_url="",
        package_name="example-plugin",
        titan_plugin_name="example",
        installed_at="2026-04-07T00:00:00+00:00",
        channel=PluginChannel.DEV_LOCAL,
        dev_local_path="/tmp/example-plugin",
        requested_ref=None,
        resolved_commit=None,
    )

    assert check_for_update(record) is None


def test_check_for_update_compares_against_requested_ref(mocker):
    record = CommunityPluginRecord(
        repo_url="https://github.com/example/plugin",
        package_name="example-plugin",
        titan_plugin_name="example",
        installed_at="2026-04-07T00:00:00+00:00",
        channel=PluginChannel.STABLE,
        dev_local_path=None,
        requested_ref="v1.0.0",
        resolved_commit="a" * 40,
    )

    class DummyResponse:
        def read(self):
            import json
            return json.dumps({"tag_name": "v1.1.0"}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    mocker.patch(
        "titan_cli.core.plugins.community.urlopen",
        return_value=DummyResponse(),
    )

    assert check_for_update(record) == "v1.1.0"
