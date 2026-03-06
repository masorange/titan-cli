"""
Community Plugin Manager

Business logic for installing, tracking, and uninstalling community plugins
from user-provided git repositories.

Community plugins are tracked in ~/.titan/community_plugins.toml.
Installation always uses `pipx inject` to maintain isolation.
"""

import os
import sys
import subprocess
from dataclasses import dataclass, asdict
from enum import StrEnum
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import tomli
import tomli_w

from titan_cli.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMMUNITY_PLUGINS_FILE = Path.home() / ".titan" / "community_plugins.toml"

# Raw pyproject.toml URL templates per host (use .format(path=..., version=...))
_RAW_URL_GITHUB    = "https://raw.githubusercontent.com/{path}/{version}/pyproject.toml"
_RAW_URL_GITLAB    = "https://gitlab.com/{path}/-/raw/{version}/pyproject.toml"
_RAW_URL_BITBUCKET = "https://bitbucket.org/{path}/raw/{version}/pyproject.toml"

# Base URL prefixes used to strip host when building the path fragment
_BASE_GITHUB    = "https://github.com/"
_BASE_GITLAB    = "https://gitlab.com/"
_BASE_BITBUCKET = "https://bitbucket.org/"

# pipx command
_PIPX_CMD = "pipx"
_TITAN_PACKAGE = "titan-cli"

# HTTP fetch timeout (seconds)
_FETCH_TIMEOUT = 10


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PluginHost(StrEnum):
    """Supported git hosting providers for community plugin preview."""
    GITHUB    = "github"
    GITLAB    = "gitlab"
    BITBUCKET = "bitbucket"
    UNKNOWN   = "unknown"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CommunityPluginRecord:
    """Record of an installed community plugin."""

    repo_url: str           # Base URL without @version
    version: str            # Tag or commit SHA
    package_name: str       # Python package name from pyproject.toml
    titan_plugin_name: str  # Key registered under titan.plugins entry point
    installed_at: str       # ISO 8601 datetime


# ---------------------------------------------------------------------------
# URL parsing and validation
# ---------------------------------------------------------------------------

def parse_repo_url(raw_url: str) -> tuple[str, str]:
    """
    Split a URL+version string into (base_url, version).

    Args:
        raw_url: e.g. "https://github.com/user/plugin@v1.2.0"

    Returns:
        Tuple of (base_url, version)

    Raises:
        ValueError: if no @version suffix is present
    """
    raw_url = raw_url.strip()
    if "@" not in raw_url:
        raise ValueError(
            "No version specified. Include a version tag or commit SHA, "
            "e.g. https://github.com/user/plugin@v1.0.0"
        )
    idx = raw_url.rfind("@")
    base_url = raw_url[:idx]
    version = raw_url[idx + 1:]
    if not version:
        raise ValueError(
            "Version is empty. Include a version tag or commit SHA, "
            "e.g. https://github.com/user/plugin@v1.0.0"
        )
    return base_url, version


def validate_url(raw_url: str) -> None:
    """
    Validate that raw_url is well-formed and includes a version.

    Raises:
        ValueError: with a user-friendly message describing the problem
    """
    raw_url = raw_url.strip()
    if not raw_url:
        raise ValueError("URL cannot be empty.")
    if not raw_url.startswith("https://"):
        raise ValueError("URL must start with https://")
    base_url, _ = parse_repo_url(raw_url)
    if not base_url.startswith("https://"):
        raise ValueError("Repository URL must start with https://")


# ---------------------------------------------------------------------------
# Host detection and raw URL building
# ---------------------------------------------------------------------------

def detect_host(base_url: str) -> PluginHost:
    """Detect the git hosting provider from the base URL."""
    if _BASE_GITHUB in base_url:
        return PluginHost.GITHUB
    if _BASE_GITLAB in base_url:
        return PluginHost.GITLAB
    if _BASE_BITBUCKET in base_url:
        return PluginHost.BITBUCKET
    return PluginHost.UNKNOWN


def build_raw_pyproject_url(base_url: str, version: str, host: PluginHost) -> Optional[str]:
    """
    Build the raw URL to fetch pyproject.toml from a known hosting provider.

    Returns None for unknown hosts.
    """
    clean = base_url.rstrip("/").removesuffix(".git")

    match host:
        case PluginHost.GITHUB:
            path = clean.removeprefix(_BASE_GITHUB)
            return _RAW_URL_GITHUB.format(path=path, version=version)
        case PluginHost.GITLAB:
            path = clean.removeprefix(_BASE_GITLAB)
            return _RAW_URL_GITLAB.format(path=path, version=version)
        case PluginHost.BITBUCKET:
            path = clean.removeprefix(_BASE_BITBUCKET)
            return _RAW_URL_BITBUCKET.format(path=path, version=version)
        case PluginHost.UNKNOWN:
            return None


# ---------------------------------------------------------------------------
# pyproject.toml fetching and parsing
# ---------------------------------------------------------------------------

def fetch_pyproject_toml(raw_url: str) -> tuple[Optional[str], Optional[str]]:
    """
    Fetch the pyproject.toml content from a raw URL.

    Returns:
        (content, error) — one of them will be None.
        On success:      (content_str, None)
        On 404:          (None, "not_found")
        On network error:(None, "network_error")
    """
    try:
        with urlopen(raw_url, timeout=_FETCH_TIMEOUT) as resp:
            return resp.read().decode("utf-8"), None
    except HTTPError as e:
        if e.code == 404:
            return None, "not_found"
        return None, "network_error"
    except (URLError, OSError):
        return None, "network_error"


def parse_plugin_metadata(toml_content: str) -> dict:
    """
    Parse pyproject.toml content and extract plugin-relevant metadata.

    Returns a dict with keys:
        name, version, description, authors,
        titan_entry_points (dict), python_deps (list), parse_error (bool)
    """
    try:
        data = tomli.loads(toml_content)
    except Exception:
        return {
            "name": None, "version": None, "description": None,
            "authors": [], "titan_entry_points": {}, "python_deps": [],
            "parse_error": True,
        }

    # Support both [project] (PEP 621) and [tool.poetry] layouts
    project = data.get("project", {})
    poetry  = data.get("tool", {}).get("poetry", {})

    name        = project.get("name")        or poetry.get("name")
    version     = project.get("version")     or poetry.get("version")
    description = project.get("description") or poetry.get("description")

    # Authors: PEP 621 → list of dicts; Poetry → list of strings
    pep_authors = project.get("authors", [])
    if pep_authors and isinstance(pep_authors[0], dict):
        authors = [a.get("name", "") for a in pep_authors]
    else:
        authors = pep_authors or poetry.get("authors", [])

    # Titan entry points
    pep_eps    = project.get("entry-points", {}).get("titan.plugins", {})
    poetry_eps = poetry.get("plugins", {}).get("titan.plugins", {})
    titan_entry_points = pep_eps or poetry_eps

    # Dependency names (strip version specifiers)
    pep_deps    = project.get("dependencies", [])
    poetry_deps = list(poetry.get("dependencies", {}).keys())
    if pep_deps:
        dep_names = []
        for dep in pep_deps:
            for sep in [">=", "<=", "!=", "~=", "==", ">"]:
                dep = dep.split(sep)[0]
            dep_names.append(dep.strip())
        python_deps = dep_names
    else:
        python_deps = [d for d in poetry_deps if d.lower() != "python"]

    return {
        "name": name, "version": version, "description": description,
        "authors": authors, "titan_entry_points": titan_entry_points,
        "python_deps": python_deps, "parse_error": False,
    }


# ---------------------------------------------------------------------------
# pipx environment detection
# ---------------------------------------------------------------------------

def is_running_in_pipx() -> bool:
    """Detect whether Titan is currently running inside a pipx-managed venv."""
    executable = sys.executable
    if "pipx" in executable:
        return True
    if os.environ.get("PIPX_HOME"):
        return True
    pipx_default = Path.home() / ".local" / "pipx" / "venvs"
    try:
        Path(executable).relative_to(pipx_default)
        return True
    except ValueError:
        pass
    return False


# ---------------------------------------------------------------------------
# pipx install / uninstall
# ---------------------------------------------------------------------------

def build_pipx_spec(base_url: str, version: str) -> str:
    """
    Build the pip/pipx package spec for a git repo URL.

    e.g. git+https://github.com/user/plugin.git@v1.0.0
    """
    clean = base_url.rstrip("/")
    if not clean.endswith(".git"):
        clean = clean + ".git"
    return f"git+{clean}@{version}"


def install_community_plugin(base_url: str, version: str) -> subprocess.CompletedProcess:
    """
    Run `pipx inject titan-cli <spec>` to install a community plugin.

    Returns the CompletedProcess — caller must check returncode.
    """
    spec = build_pipx_spec(base_url, version)
    logger.info("community_plugin_install", spec=spec)
    return subprocess.run(
        [_PIPX_CMD, "inject", _TITAN_PACKAGE, spec],
        capture_output=True,
        text=True,
    )


def uninstall_community_plugin(package_name: str) -> subprocess.CompletedProcess:
    """
    Run `pipx runpip titan-cli uninstall -y <package>` to remove a community plugin.

    Returns the CompletedProcess — caller must check returncode.
    """
    logger.info("community_plugin_uninstall", package=package_name)
    return subprocess.run(
        [_PIPX_CMD, "runpip", _TITAN_PACKAGE, "uninstall", "-y", package_name],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Community plugin tracking (~/.titan/community_plugins.toml)
# ---------------------------------------------------------------------------

def get_community_plugins_path() -> Path:
    return COMMUNITY_PLUGINS_FILE


def load_community_plugins() -> list[CommunityPluginRecord]:
    """
    Load installed community plugins from ~/.titan/community_plugins.toml.

    Returns an empty list if the file does not exist.
    """
    path = get_community_plugins_path()
    if not path.exists():
        return []
    try:
        with open(path, "rb") as f:
            data = tomli.load(f)
        return [CommunityPluginRecord(**item) for item in data.get("plugins", [])]
    except Exception:
        logger.exception("community_plugins_load_failed")
        return []


def save_community_plugin(record: CommunityPluginRecord) -> None:
    """
    Append a community plugin record to ~/.titan/community_plugins.toml.
    Creates the file and parent directory if they don't exist.
    """
    path = get_community_plugins_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        with open(path, "rb") as f:
            data = tomli.load(f)
    else:
        data = {"plugins": []}

    data.setdefault("plugins", [])
    data["plugins"].append(asdict(record))

    with open(path, "wb") as f:
        tomli_w.dump(data, f)


def remove_community_plugin(package_name: str) -> None:
    """Remove a community plugin record by package name."""
    path = get_community_plugins_path()
    if not path.exists():
        return

    with open(path, "rb") as f:
        data = tomli.load(f)

    data["plugins"] = [
        p for p in data.get("plugins", [])
        if p.get("package_name") != package_name
    ]

    with open(path, "wb") as f:
        tomli_w.dump(data, f)


def get_community_plugin_names() -> set[str]:
    """Return the set of titan_plugin_names for all installed community plugins."""
    return {r.titan_plugin_name for r in load_community_plugins()}


def get_community_plugin_by_titan_name(titan_name: str) -> Optional[CommunityPluginRecord]:
    """Return the community plugin record for a given titan plugin name, or None."""
    for record in load_community_plugins():
        if record.titan_plugin_name == titan_name:
            return record
    return None
