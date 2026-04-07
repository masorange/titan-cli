# tests/core/test_config.py
import os
import subprocess
import tomli_w
from pathlib import Path
from titan_cli.core.config import TitanConfig


def _git_init(path: Path) -> None:
    """Initialize a git repository at the given path."""
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)

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


def test_config_uses_git_root_as_project_root(tmp_path: Path, monkeypatch, mocker):
    """
    Monorepo scenario: when running from a subdirectory, project_root should be
    the git root, not the current working directory.
    """
    mocker.patch('titan_cli.core.config.PluginRegistry')

    # Setup: git repo at tmp_path/monorepo, .titan config at monorepo root
    git_root = tmp_path / "monorepo"
    git_root.mkdir()
    _git_init(git_root)

    titan_dir = git_root / ".titan"
    titan_dir.mkdir()
    project_config_path = titan_dir / "config.toml"
    project_config_data = {"project": {"name": "My Monorepo"}}
    with open(project_config_path, "wb") as f:
        tomli_w.dump(project_config_data, f)

    # Global config (empty)
    global_config_path = tmp_path / "home" / ".titan" / "config.toml"
    global_config_path.parent.mkdir(parents=True)
    with open(global_config_path, "wb") as f:
        tomli_w.dump({}, f)

    monkeypatch.setattr(TitanConfig, "GLOBAL_CONFIG", global_config_path)

    # Run from a subdirectory (simulating working in /monorepo/app)
    app_dir = git_root / "app"
    app_dir.mkdir()

    original_cwd = os.getcwd()
    try:
        os.chdir(app_dir)
        config_instance = TitanConfig()

        assert config_instance.project_root == git_root.resolve()
        assert config_instance.config.project.name == "My Monorepo"
    finally:
        os.chdir(original_cwd)


def test_config_uses_cwd_as_project_root_when_no_git(tmp_path: Path, monkeypatch, mocker):
    """
    When not inside a git repo, project_root falls back to the current
    working directory.
    """
    mocker.patch('titan_cli.core.config.PluginRegistry')

    project_dir = tmp_path / "my_project"
    project_dir.mkdir()
    titan_dir = project_dir / ".titan"
    titan_dir.mkdir()
    project_config_path = titan_dir / "config.toml"
    with open(project_config_path, "wb") as f:
        tomli_w.dump({"project": {"name": "No Git Project"}}, f)

    global_config_path = tmp_path / "home" / ".titan" / "config.toml"
    global_config_path.parent.mkdir(parents=True)
    with open(global_config_path, "wb") as f:
        tomli_w.dump({}, f)

    monkeypatch.setattr(TitanConfig, "GLOBAL_CONFIG", global_config_path)

    original_cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        config_instance = TitanConfig()

        assert config_instance.project_root == project_dir.resolve()
        assert config_instance.config.project.name == "No Git Project"
    finally:
        os.chdir(original_cwd)


def test_config_finds_titan_at_git_root_not_subdir(tmp_path: Path, monkeypatch, mocker):
    """
    When running from /monorepo/app with .titan only at /monorepo,
    the wizard should NOT trigger (config is found at git root).
    """
    mocker.patch('titan_cli.core.config.PluginRegistry')

    git_root = tmp_path / "monorepo"
    git_root.mkdir()
    _git_init(git_root)

    titan_dir = git_root / ".titan"
    titan_dir.mkdir()
    with open(titan_dir / "config.toml", "wb") as f:
        tomli_w.dump({"project": {"name": "Monorepo"}}, f)

    global_config_path = tmp_path / "home" / ".titan" / "config.toml"
    global_config_path.parent.mkdir(parents=True)
    with open(global_config_path, "wb") as f:
        tomli_w.dump({}, f)

    monkeypatch.setattr(TitanConfig, "GLOBAL_CONFIG", global_config_path)

    # Running from a nested package dir — no .titan here
    pkg_dir = git_root / "packages" / "backend"
    pkg_dir.mkdir(parents=True)

    original_cwd = os.getcwd()
    try:
        os.chdir(pkg_dir)
        config_instance = TitanConfig()

        # Config should be found — no wizard needed
        assert config_instance.project_config_path == titan_dir / "config.toml"
        assert config_instance.config.project.name == "Monorepo"
    finally:
        os.chdir(original_cwd)


def test_config_no_titan_in_subdir_triggers_wizard_scenario(tmp_path: Path, monkeypatch, mocker):
    """
    .titan only exists in a subdirectory (/monorepo/app/.titan) but NOT at git root (/monorepo).
    Running from /monorepo/app should NOT find the config — project_root is the git root,
    and _find_project_config searches from there upward, missing the subdir config.
    This documents the intentional behavior: configs must live at the git root.
    """
    mocker.patch('titan_cli.core.config.PluginRegistry')

    git_root = tmp_path / "monorepo"
    git_root.mkdir()
    _git_init(git_root)

    # .titan is in the app subdir, NOT at git root
    app_dir = git_root / "app"
    app_dir.mkdir()
    app_titan_dir = app_dir / ".titan"
    app_titan_dir.mkdir()
    with open(app_titan_dir / "config.toml", "wb") as f:
        tomli_w.dump({"project": {"name": "App Only"}}, f)

    global_config_path = tmp_path / "home" / ".titan" / "config.toml"
    global_config_path.parent.mkdir(parents=True)
    with open(global_config_path, "wb") as f:
        tomli_w.dump({}, f)

    monkeypatch.setattr(TitanConfig, "GLOBAL_CONFIG", global_config_path)

    original_cwd = os.getcwd()
    try:
        os.chdir(app_dir)
        config_instance = TitanConfig()

        # Config at subdir is NOT found — project_root is git root, not app_dir
        assert config_instance.project_root == git_root.resolve()
        assert config_instance.project_config_path is None
    finally:
        os.chdir(original_cwd)


def test_config_workflow_registry_uses_git_root(tmp_path: Path, monkeypatch, mocker):
    """
    WorkflowRegistry should be initialized with the git root as project_root,
    so workflows defined at the monorepo level are discoverable from any subdirectory.
    """
    mocker.patch('titan_cli.core.config.PluginRegistry')
    mock_registry_cls = mocker.patch('titan_cli.core.config.WorkflowRegistry')

    git_root = tmp_path / "monorepo"
    git_root.mkdir()
    _git_init(git_root)

    titan_dir = git_root / ".titan"
    titan_dir.mkdir()
    with open(titan_dir / "config.toml", "wb") as f:
        tomli_w.dump({"project": {"name": "Monorepo"}}, f)

    global_config_path = tmp_path / "home" / ".titan" / "config.toml"
    global_config_path.parent.mkdir(parents=True)
    with open(global_config_path, "wb") as f:
        tomli_w.dump({}, f)

    monkeypatch.setattr(TitanConfig, "GLOBAL_CONFIG", global_config_path)

    app_dir = git_root / "app"
    app_dir.mkdir()

    original_cwd = os.getcwd()
    try:
        os.chdir(app_dir)
        TitanConfig()

        # WorkflowRegistry must be initialized with git root, not app_dir
        call_kwargs = mock_registry_cls.call_args
        assert call_kwargs.kwargs["project_root"] == git_root.resolve()
    finally:
        os.chdir(original_cwd)


def test_get_plugin_source_defaults_to_stable_and_no_path(mocker, monkeypatch):
    """
    Plugins without an explicit source override should use the stable channel.
    """
    mocker.patch('titan_cli.core.config.PluginRegistry')
    monkeypatch.setattr(TitanConfig, "GLOBAL_CONFIG", Path("/nonexistent/config.toml"))
    monkeypatch.setattr(TitanConfig, "_find_project_config", lambda self, path: None)

    config_instance = TitanConfig()

    assert config_instance.get_plugin_source_channel("github") == "stable"
    assert config_instance.get_plugin_source_path("github") is None


def test_get_plugin_source_reads_project_override(tmp_path: Path, monkeypatch, mocker):
    """
    Source override metadata should be available through TitanConfig helpers.
    """
    mocker.patch('titan_cli.core.config.PluginRegistry')

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    titan_dir = project_dir / ".titan"
    titan_dir.mkdir()

    plugin_repo = tmp_path / "plugins" / "local-github"
    plugin_repo.mkdir(parents=True)

    with open(titan_dir / "config.toml", "wb") as f:
        tomli_w.dump(
            {
                "project": {"name": "Project"},
                "plugins": {
                    "github": {
                        "enabled": True,
                        "source": {
                            "channel": "dev_local",
                            "path": str(plugin_repo),
                        },
                    }
                },
            },
            f,
        )

    global_config_path = tmp_path / "home" / ".titan" / "config.toml"
    global_config_path.parent.mkdir(parents=True)
    with open(global_config_path, "wb") as f:
        tomli_w.dump({}, f)

    monkeypatch.setattr(TitanConfig, "GLOBAL_CONFIG", global_config_path)

    original_cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        config_instance = TitanConfig()

        assert config_instance.get_plugin_source_channel("github") == "dev_local"
        assert config_instance.get_plugin_source_path("github") == plugin_repo.resolve()
    finally:
        os.chdir(original_cwd)
