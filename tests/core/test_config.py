# tests/core/test_config.py
import pytest
import tomli_w
from pathlib import Path
from titan_cli.core.config import TitanConfig
from titan_cli.core.models import TitanConfigModel

def test_config_initialization_no_files(monkeypatch):
    """
    Test that TitanConfig initializes with default values when no config files are present.
    """
    # Use monkeypatch to prevent it from finding any real config files
    monkeypatch.setattr(TitanConfig, "GLOBAL_CONFIG", Path("/nonexistent/config.toml"))
    monkeypatch.setattr(TitanConfig, "_find_project_config", lambda self, path: None)

    # Initialize TitanConfig
    config_instance = TitanConfig()

    # Assert that the resulting config is the default Pydantic model
    assert config_instance.config == TitanConfigModel()
    assert config_instance.project_config == {}
    assert config_instance.global_config == {}

def test_config_loads_global_config(tmp_path: Path):
    """
    Test that TitanConfig correctly loads a global config file.
    """
    # Create a mock global config file
    global_config_dir = tmp_path / ".titan"
    global_config_dir.mkdir()
    global_config_path = global_config_dir / "config.toml"
    global_config_data = {
        "core": {"project_root": str(tmp_path)},
        "ai": {"provider": "openai", "model": "gpt-4"}
    }
    with open(global_config_path, "wb") as f:
        tomli_w.dump(global_config_data, f)
    
    # Patch the GLOBAL_CONFIG path to point to our mock file
    # and disable project config finding
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(TitanConfig, "GLOBAL_CONFIG", global_config_path)
    monkeypatch.setattr(TitanConfig, "_find_project_config", lambda self, path: None)

    config_instance = TitanConfig()

    assert config_instance.global_config["core"]["project_root"] == str(tmp_path)
    assert config_instance.config.core.project_root == str(tmp_path)
    assert config_instance.config.ai.provider == "openai"
    assert config_instance.config.ai.model == "gpt-4"
    
    monkeypatch.undo()

def test_config_project_overrides_global(tmp_path: Path):
    """
    Test that project-specific config correctly overrides the global config.
    """
    # 1. Create a mock global config
    global_config_dir = tmp_path / "global" / ".titan"
    global_config_dir.mkdir(parents=True)
    global_config_path = global_config_dir / "config.toml"
    global_config_data = {
        "project": {"name": "Global Project"}, # This will be ignored due to project config
        "ai": {"provider": "anthropic"},
        "plugins": {
            "github": {"enabled": True, "config": {"org": "global-org"}},
            "jira": {"enabled": False}
        }
    }
    with open(global_config_path, "wb") as f:
        tomli_w.dump(global_config_data, f)

    # 2. Create a mock project config in a subdirectory
    project_dir = tmp_path / "my_project"
    project_titan_dir = project_dir / ".titan"
    project_titan_dir.mkdir(parents=True)
    project_config_path = project_titan_dir / "config.toml"
    project_config_data = {
        "project": {"name": "My Specific Project"},
        "ai": {"provider": "openai"}, # Override provider
        "plugins": {
            "github": {"config": {"org": "project-org"}}, # Override nested value
            "git": {"enabled": True} # Add a new plugin
        }
    }
    with open(project_config_path, "wb") as f:
        tomli_w.dump(project_config_data, f)
    
    # 3. Patch global config and initialize from the project directory
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(TitanConfig, "GLOBAL_CONFIG", global_config_path)
    
    config_instance = TitanConfig(project_path=project_dir)

    # 4. Assert that the merge was successful
    # Project name is from project config
    assert config_instance.config.project.name == "My Specific Project"
    # AI provider is overridden by project config
    assert config_instance.config.ai.provider == "openai"
    # Plugin configs are merged correctly
    assert config_instance.config.plugins["github"].enabled is True # from global
    assert config_instance.config.plugins["github"].config["org"] == "project-org" # from project
    assert config_instance.config.plugins["jira"].enabled is False # from global
    assert config_instance.config.plugins["git"].enabled is True # from project

    monkeypatch.undo()

def test_find_project_config_walks_up_tree(tmp_path: Path):
    """
    Test that _find_project_config correctly finds config in parent directory.
    """
    # Create project root and config
    project_root = tmp_path / "my_real_project"
    project_titan_dir = project_root / ".titan"
    project_titan_dir.mkdir(parents=True)
    config_path = project_titan_dir / "config.toml"
    config_path.touch()

    # Create a deep subdirectory to start the search from
    deep_subdir = project_root / "src" / "app" / "components"
    deep_subdir.mkdir(parents=True)

    # Initialize TitanConfig without patching _find_project_config
    # but patch the global config to isolate the test
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(TitanConfig, "GLOBAL_CONFIG", Path("/nonexistent/config.toml"))

    config_instance = TitanConfig(project_path=deep_subdir)
    
    # Assert that it found the correct config file
    assert config_instance.project_config_path == config_path

    monkeypatch.undo()
