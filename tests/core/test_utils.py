# tests/core/test_utils.py
import os
import subprocess
from pathlib import Path


from titan_cli.core.utils import find_git_root, find_project_root


def _git_init(path: Path) -> None:
    """Initialize a git repository at the given path."""
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)


class TestFindGitRoot:
    def test_returns_root_when_at_git_root(self, tmp_path):
        _git_init(tmp_path)
        original = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = find_git_root()
            assert result == tmp_path.resolve()
        finally:
            os.chdir(original)

    def test_returns_root_when_in_subdirectory(self, tmp_path):
        """Monorepo scenario: running from a subdirectory should find the parent git root."""
        _git_init(tmp_path)
        subdir = tmp_path / "app" / "src"
        subdir.mkdir(parents=True)

        original = os.getcwd()
        try:
            os.chdir(subdir)
            result = find_git_root()
            assert result == tmp_path.resolve()
        finally:
            os.chdir(original)

    def test_returns_none_when_no_git_repo(self, tmp_path):
        original = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = find_git_root()
            assert result is None
        finally:
            os.chdir(original)

    def test_returns_none_when_git_not_available(self, tmp_path, monkeypatch):
        """Handles environments where git is not installed."""
        import subprocess as sp

        def raise_file_not_found(*args, **kwargs):
            raise FileNotFoundError("git not found")

        monkeypatch.setattr(sp, "run", raise_file_not_found)

        original = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = find_git_root()
            assert result is None
        finally:
            os.chdir(original)


class TestFindProjectRoot:
    def test_returns_git_root_inside_repo(self, tmp_path):
        _git_init(tmp_path)
        subdir = tmp_path / "packages" / "web"
        subdir.mkdir(parents=True)

        original = os.getcwd()
        try:
            os.chdir(subdir)
            result = find_project_root()
            assert result == tmp_path.resolve()
        finally:
            os.chdir(original)

    def test_returns_cwd_when_no_git_repo(self, tmp_path):
        original = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = find_project_root()
            assert result == tmp_path.resolve()
        finally:
            os.chdir(original)

    def test_returns_git_root_not_subdir_when_in_monorepo(self, tmp_path):
        """
        Explicit monorepo test: git root is /global, running from /global/app
        should return /global, not /global/app.
        """
        git_root = tmp_path / "global"
        git_root.mkdir()
        _git_init(git_root)

        app_dir = git_root / "app"
        app_dir.mkdir()

        original = os.getcwd()
        try:
            os.chdir(app_dir)
            result = find_project_root()
            assert result == git_root.resolve()
            assert result != app_dir.resolve()
        finally:
            os.chdir(original)
