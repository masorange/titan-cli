from pathlib import Path

from titan_cli.core.plugins.runtime import PluginRuntimeManager


def test_get_runtime_paths_returns_expected_layout(tmp_path: Path):
    manager = PluginRuntimeManager(cache_root=tmp_path)

    paths = manager.get_runtime_paths("sample", "a" * 40)

    assert paths.cache_dir == tmp_path / "sample" / ("a" * 40)
    assert paths.source_dir == paths.cache_dir / "src"
    assert paths.venv_dir == paths.cache_dir / "venv"
    assert paths.site_packages == paths.venv_dir / "lib" / "python3.12" / "site-packages"


def test_ensure_stable_runtime_reuses_existing_runtime(tmp_path: Path, mocker):
    manager = PluginRuntimeManager(cache_root=tmp_path)
    paths = manager.get_runtime_paths("sample", "a" * 40)

    mocker.patch.object(manager, "_is_runtime_ready", return_value=True)
    prepare = mocker.patch.object(manager, "_prepare_runtime")

    resolved = manager.ensure_stable_runtime(
        plugin_name="sample",
        repo_url="https://github.com/example/sample-plugin",
        resolved_commit="a" * 40,
    )

    assert resolved == paths
    prepare.assert_not_called()


def test_ensure_stable_runtime_prepares_and_moves_runtime(tmp_path: Path, mocker):
    manager = PluginRuntimeManager(cache_root=tmp_path)
    final_paths = manager.get_runtime_paths("sample", "b" * 40)
    temp_dir = tmp_path / "sample" / "temp-build"
    temp_dir.parent.mkdir(parents=True, exist_ok=True)

    mocker.patch.object(manager, "_is_runtime_ready", return_value=False)
    mocker.patch("titan_cli.core.plugins.runtime.mkdtemp", return_value=str(temp_dir))

    def fake_prepare(paths, repo_url, resolved_commit, token):
        paths.source_dir.mkdir(parents=True, exist_ok=True)
        paths.site_packages.mkdir(parents=True, exist_ok=True)
        pip_executable = manager._get_venv_executable(paths.venv_dir, "pip")
        pip_executable.parent.mkdir(parents=True, exist_ok=True)
        pip_executable.write_text("", encoding="utf-8")

    mocker.patch.object(manager, "_prepare_runtime", side_effect=fake_prepare)

    resolved = manager.ensure_stable_runtime(
        plugin_name="sample",
        repo_url="https://github.com/example/sample-plugin",
        resolved_commit="b" * 40,
        token="secret",
    )

    assert resolved == final_paths
    assert resolved.cache_dir.exists()
    assert resolved.source_dir.exists()
    assert resolved.site_packages.exists()
    assert not temp_dir.exists()


def test_build_authenticated_repo_url_adds_token():
    manager = PluginRuntimeManager(cache_root=Path("/tmp/cache"))

    result = manager._build_authenticated_repo_url(
        "https://github.com/example/sample-plugin",
        "abc123",
    )

    assert result == "https://abc123@github.com/example/sample-plugin"
