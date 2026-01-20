# tests/core/test_config.py
import tomli_w
from pathlib import Path
from titan_cli.core.config import TitanConfig

def test_config_project_overrides_global(tmp_path: Path, monkeypatch, mocker):
    """
    Test that project-specific config correctly overrides the global config.
    """
    # Mock PluginRegistry
    mocker.patch('titan_cli.core.config.PluginRegistry')

    # 1. Create a mock global config
    global_config_dir = tmp_path / "home" / ".titan"
    global_config_dir.mkdir(parents=True)
    global_config_path = global_config_dir / "config.toml"
    global_config_data = {
        "ai": {
            "default": "anthropic",
            "providers": {
                "anthropic": {
                    "provider": "anthropic",
                    "model": "claude-3-5-sonnet",
                    "name": "Global Claude",
                    "type": "individual",
                    "temperature": 0.7,
                    "max_tokens": 4096
                }
            }
        }
    }
    with open(global_config_path, "wb") as f:
        tomli_w.dump(global_config_data, f)

    # 2. Create a mock project config
    project_dir = tmp_path / "my_project"
    project_titan_dir = project_dir / ".titan"
    project_titan_dir.mkdir(parents=True)
    project_config_path = project_titan_dir / "config.toml"
    project_config_data = {
        "project": {"name": "My Specific Project"},
        "ai": {
            "default": "gemini",
            "providers": {
                "gemini": {
                    "provider": "gemini",
                    "model": "gemini-1.5-pro",
                    "name": "Project Gemini",
                    "type": "individual",
                    "temperature": 0.7,
                    "max_tokens": 4096
                }
            }
        },
        "plugins": {
            "github": {"enabled": True, "config": {"org": "project-org"}},
            "git": {"enabled": True, "config": {}}
        }
    }
    with open(project_config_path, "wb") as f:
        tomli_w.dump(project_config_data, f)

    # 3. Patch global config path and project config path
    monkeypatch.setattr(TitanConfig, "GLOBAL_CONFIG", global_config_path)

    # Change to project directory so it finds the project config
    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        config_instance = TitanConfig()

        # 4. Assert that the merge was successful
        # Project name is from project config
        assert config_instance.config.project.name == "My Specific Project"
        # AI provider is overridden by project config
        assert config_instance.config.ai.default == "gemini"
        assert config_instance.config.ai.providers["gemini"].model == "gemini-1.5-pro"
        assert config_instance.config.ai.providers["gemini"].name == "Project Gemini"
        # Plugin configs are from project
        assert config_instance.config.plugins["github"].enabled is True
        assert config_instance.config.plugins["github"].config["org"] == "project-org"
        assert config_instance.config.plugins["git"].enabled is True
    finally:
        os.chdir(original_cwd)


def test_config_dependency_injection(mocker, monkeypatch):
    """
    Test that the PluginRegistry is correctly injected into TitanConfig.
    """
    # Mock PluginRegistry to ensure it's called
    mock_registry = mocker.MagicMock()
    mocker.patch('titan_cli.core.config.PluginRegistry', return_value=mock_registry)

    # Patch config paths to nonexistent files
    monkeypatch.setattr(TitanConfig, "GLOBAL_CONFIG", Path("/nonexistent/config.toml"))
    monkeypatch.setattr(TitanConfig, "_find_project_config", lambda self, path: None)

    config_instance = TitanConfig()

    # Assert that the registry was injected
    assert config_instance.registry is mock_registry


def test_load_toml_handles_decode_error(tmp_path: Path, capsys, monkeypatch, mocker):
    """
    Test that _load_toml handles TOMLDecodeError gracefully.
    """
    # Mock PluginRegistry
    mocker.patch('titan_cli.core.config.PluginRegistry')

    # Create an invalid TOML file
    invalid_toml_path = tmp_path / "invalid.toml"
    invalid_toml_path.write_text("this is not valid toml ][")

    # Patch config paths
    monkeypatch.setattr(TitanConfig, "GLOBAL_CONFIG", invalid_toml_path)
    monkeypatch.setattr(TitanConfig, "_find_project_config", lambda self, path: None)

    # This should not raise an exception
    config_instance = TitanConfig()

    # Should have empty config
    assert config_instance.global_config == {}


def test_config_deep_merges_plugins(tmp_path: Path, monkeypatch, mocker):
    """
    Test that the plugin configuration is deep-merged, not just overridden.
    """
    # Mock PluginRegistry
    mocker.patch('titan_cli.core.config.PluginRegistry')

    # 1. Create project directory structure
    project_dir = tmp_path / "test_project"
    project_titan_dir = project_dir / ".titan"
    project_titan_dir.mkdir(parents=True)

    # 2. Global config defines a plugin with 'enabled' and a nested 'config' key
    global_config_path = tmp_path / "home" / ".titan" / "config.toml"
    global_config_path.parent.mkdir(parents=True)
    global_config_data = {
        "plugins": {
            "github": {"enabled": True, "config": {"user": "global-user", "repo": "global-repo"}}
        }
    }
    with open(global_config_path, "wb") as f:
        tomli_w.dump(global_config_data, f)

    # 3. Project config overrides only the nested 'user' key
    project_config_path = project_titan_dir / "config.toml"
    project_config_data = {
        "project": {"name": "Test Project"},
        "plugins": {
            "github": {"config": {"user": "project-user"}}
        }
    }
    with open(project_config_path, "wb") as f:
        tomli_w.dump(project_config_data, f)

    # 4. Patch config paths and initialize from project directory
    monkeypatch.setattr(TitanConfig, "GLOBAL_CONFIG", global_config_path)

    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        config_instance = TitanConfig()

        # 5. Assert that the 'enabled' key from global is preserved
        #    and the nested 'user' key is overridden, but 'repo' is preserved
        github_plugin_config = config_instance.config.plugins.get("github")
        assert github_plugin_config is not None
        assert github_plugin_config.enabled is True  # This should be preserved from global
        assert github_plugin_config.config["user"] == "project-user"  # This should be overridden by project
        assert github_plugin_config.config["repo"] == "global-repo"  # This should be preserved from global
    finally:
        os.chdir(original_cwd)
