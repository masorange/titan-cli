"""Runtime management for project-pinned community plugins."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import mkdtemp
from urllib.parse import urlsplit, urlunsplit

from titan_cli.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class PluginRuntimePaths:
    """Filesystem paths for a prepared plugin runtime."""

    cache_dir: Path
    source_dir: Path
    venv_dir: Path
    site_packages: Path


class PluginRuntimeError(RuntimeError):
    """Raised when a plugin runtime cannot be prepared."""


class PluginRuntimeManager:
    """Prepare and reuse isolated runtimes for community plugins."""

    CACHE_ROOT = Path.home() / ".titan" / "plugin-cache"

    def __init__(
        self,
        cache_root: Path | None = None,
        python_executable: str | None = None,
    ) -> None:
        self.cache_root = (cache_root or self.CACHE_ROOT).expanduser().resolve()
        self.python_executable = python_executable or sys.executable

    def get_runtime_paths(self, plugin_name: str, resolved_commit: str) -> PluginRuntimePaths:
        """Return the cache layout for a plugin runtime."""
        cache_dir = self.cache_root / plugin_name / resolved_commit
        source_dir = cache_dir / "src"
        venv_dir = cache_dir / "venv"
        return PluginRuntimePaths(
            cache_dir=cache_dir,
            source_dir=source_dir,
            venv_dir=venv_dir,
            site_packages=self._get_site_packages_path(venv_dir),
        )

    def ensure_stable_runtime(
        self,
        plugin_name: str,
        repo_url: str,
        resolved_commit: str,
        token: str | None = None,
    ) -> PluginRuntimePaths:
        """Ensure a stable plugin runtime exists and return its paths."""
        paths = self.get_runtime_paths(plugin_name, resolved_commit)
        if self._is_runtime_ready(paths):
            return paths

        paths.cache_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(mkdtemp(prefix=f"{plugin_name}-", dir=str(paths.cache_dir.parent)))
        temp_paths = PluginRuntimePaths(
            cache_dir=temp_dir,
            source_dir=temp_dir / "src",
            venv_dir=temp_dir / "venv",
            site_packages=self._get_site_packages_path(temp_dir / "venv"),
        )

        try:
            self._prepare_runtime(temp_paths, repo_url, resolved_commit, token)
            if paths.cache_dir.exists():
                shutil.rmtree(paths.cache_dir)
            temp_dir.replace(paths.cache_dir)
            return self.get_runtime_paths(plugin_name, resolved_commit)
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise PluginRuntimeError(str(e)) from e

    def _prepare_runtime(
        self,
        paths: PluginRuntimePaths,
        repo_url: str,
        resolved_commit: str,
        token: str | None,
    ) -> None:
        paths.cache_dir.mkdir(parents=True, exist_ok=True)
        self._checkout_source(repo_url, resolved_commit, paths.source_dir, token)
        self._create_virtualenv(paths.venv_dir)
        self._install_plugin(paths.venv_dir, paths.source_dir)

    def _checkout_source(
        self,
        repo_url: str,
        resolved_commit: str,
        source_dir: Path,
        token: str | None,
    ) -> None:
        auth_url = self._build_authenticated_repo_url(repo_url, token)
        self._run_git(["init", str(source_dir)])
        self._run_git(["-C", str(source_dir), "remote", "add", "origin", auth_url])
        self._run_git(["-C", str(source_dir), "fetch", "--depth", "1", "origin", resolved_commit])
        self._run_git(["-C", str(source_dir), "checkout", "--detach", "FETCH_HEAD"])

    def _create_virtualenv(self, venv_dir: Path) -> None:
        self._run_checked([self.python_executable, "-m", "venv", str(venv_dir)], "create plugin virtualenv")

    def _install_plugin(self, venv_dir: Path, source_dir: Path) -> None:
        pip_executable = self._get_venv_executable(venv_dir, "pip")
        self._run_checked([str(pip_executable), "install", str(source_dir)], "install plugin runtime")

    def _is_runtime_ready(self, paths: PluginRuntimePaths) -> bool:
        pip_executable = self._get_venv_executable(paths.venv_dir, "pip")
        return paths.source_dir.is_dir() and paths.site_packages.is_dir() and pip_executable.exists()

    def _get_site_packages_path(self, venv_dir: Path) -> Path:
        if sys.platform == "win32":
            return venv_dir / "Lib" / "site-packages"

        lib_dir = venv_dir / "lib"
        matches = sorted(lib_dir.glob("python*/site-packages"))
        if matches:
            return matches[0]

        version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        return lib_dir / version / "site-packages"

    def _get_venv_executable(self, venv_dir: Path, name: str) -> Path:
        if sys.platform == "win32":
            return venv_dir / "Scripts" / f"{name}.exe"
        return venv_dir / "bin" / name

    def _build_authenticated_repo_url(self, repo_url: str, token: str | None) -> str:
        if not token:
            return repo_url

        parsed = urlsplit(repo_url)
        netloc = f"{token}@{parsed.netloc}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))

    def _run_git(self, command: list[str]) -> None:
        self._run_checked(["git", *command], "prepare plugin source")

    def _run_checked(self, command: list[str], description: str) -> None:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(
                "plugin_runtime_command_failed",
                description=description,
                command=command,
                stdout=result.stdout,
                stderr=result.stderr,
            )
            output = result.stderr or result.stdout or "Unknown error"
            raise PluginRuntimeError(f"Failed to {description}: {output.strip()}")
