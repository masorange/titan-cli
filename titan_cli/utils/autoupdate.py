"""Auto-update utility for Titan CLI."""

import os
import sys
import subprocess
from datetime import datetime, timezone
from typing import Dict, Optional
from pathlib import Path

from titan_cli import __version__

UPDATE_CHECK_COOLDOWN_HOURS = 24
_TIMESTAMP_FILE = Path.home() / ".titan" / ".update_check"


def _get_last_check_timestamp() -> Optional[datetime]:
    """Read the last update check timestamp from disk."""
    try:
        if _TIMESTAMP_FILE.exists():
            ts = float(_TIMESTAMP_FILE.read_text().strip())
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, OSError):
        pass
    return None


def _save_check_timestamp() -> None:
    """Save the current time as the last update check timestamp."""
    try:
        _TIMESTAMP_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TIMESTAMP_FILE.write_text(str(datetime.now(tz=timezone.utc).timestamp()))
    except OSError:
        pass


def _is_check_due() -> bool:
    """Return True if enough time has passed since the last update check."""
    last_check = _get_last_check_timestamp()
    if last_check is None:
        return True
    now = datetime.now(tz=timezone.utc)
    hours_since_check = (now - last_check).total_seconds() / 3600
    return hours_since_check < UPDATE_CHECK_COOLDOWN_HOURS


def is_dev_install() -> bool:
    """
    Check if this is an editable/development installation.

    Returns:
        True if installed in development mode, False if from PyPI
    """
    import titan_cli

    # Check if titan_cli is installed in site-packages or in a local directory
    titan_path = Path(titan_cli.__file__).resolve().parent

    # If the path contains 'site-packages', it's a production install
    # If it's in a git repo or contains pyproject.toml nearby, it's dev
    if 'site-packages' in str(titan_path):
        return False

    # Check for development indicators
    parent = titan_path.parent
    return (parent / 'pyproject.toml').exists() or (parent / '.git').exists()


def check_for_updates() -> Dict[str, any]:
    """
    Check PyPI for newer version.

    Returns:
        Dictionary with update information:
        {
            "update_available": bool,
            "current_version": str,
            "latest_version": Optional[str],
            "is_dev_install": bool,
            "error": Optional[str]
        }
    """
    # Mock support: TITAN_MOCK_UPDATE=0.1.15 simulates an update available
    mock_version = os.environ.get("TITAN_MOCK_UPDATE")
    if mock_version:
        return {
            "update_available": True,
            "current_version": __version__,
            "latest_version": mock_version,
            "is_dev_install": False,
            "error": None,
        }

    result = {
        "update_available": False,
        "current_version": __version__,
        "latest_version": None,
        "is_dev_install": is_dev_install(),
        "error": None
    }

    # Skip check for dev installations
    if result["is_dev_install"]:
        return result

    # Skip check if we checked recently (cooldown)
    if not _is_check_due():
        return result

    try:
        import requests

        response = requests.get(
            "https://pypi.org/pypi/titan-cli/json",
            timeout=3
        )

        if response.status_code != 200:
            result["error"] = f"PyPI returned status {response.status_code}"
            return result

        data = response.json()
        latest_version = data["info"]["version"]
        result["latest_version"] = latest_version

        # Simple version comparison (assumes semantic versioning)
        from packaging import version
        current = version.parse(__version__)
        latest = version.parse(latest_version)

        result["update_available"] = latest > current
        _save_check_timestamp()

    except ImportError:
        result["error"] = "Missing dependencies (requests, packaging)"
    except Exception as e:
        result["error"] = str(e)

    return result


def update_core() -> Dict[str, any]:
    """
    Upgrade the titan-cli core package.

    Returns:
        {
            "success": bool,
            "method": str,        # "pipx" or "pip"
            "installed_version": Optional[str],
            "error": Optional[str]
        }
    """
    # Mock support: TITAN_MOCK_CORE_FAIL=1 simulates a core update failure
    mock_version = os.environ.get("TITAN_MOCK_UPDATE")
    if mock_version:
        if os.environ.get("TITAN_MOCK_CORE_FAIL"):
            return {"success": False, "method": None, "installed_version": None, "error": "Mock core failure"}
        return {"success": True, "method": "pipx", "installed_version": mock_version, "error": None}

    result = {
        "success": False,
        "method": None,
        "installed_version": None,
        "error": None,
    }

    # Try pipx first (without --include-injected to avoid pip resolving plugin
    # constraints and skipping the core upgrade)
    try:
        proc = subprocess.run(
            ["pipx", "upgrade", "--force", "titan-cli"],
            capture_output=True,
            text=True,
            timeout=60
        )

        if proc.returncode == 0:
            installed_version = _get_installed_version_pipx()
            if installed_version:
                result["success"] = True
                result["method"] = "pipx"
                result["installed_version"] = installed_version
            else:
                result["error"] = "Could not verify installed version"
            return result

    except FileNotFoundError:
        pass  # pipx not installed, fall through to pip
    except subprocess.TimeoutExpired:
        result["error"] = "Update timed out"
        return result

    # Fallback to pip
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "titan-cli"],
            capture_output=True,
            text=True,
            timeout=60
        )

        if proc.returncode == 0:
            installed_version = _get_installed_version_pip()
            if installed_version:
                result["success"] = True
                result["method"] = "pip"
                result["installed_version"] = installed_version
            else:
                result["error"] = "Could not verify installed version"
        else:
            result["error"] = proc.stderr.strip() or "Core upgrade failed"
        return result

    except subprocess.TimeoutExpired:
        result["error"] = "Update timed out"
        return result


def update_plugins() -> Dict[str, any]:
    """
    Upgrade injected plugins via pipx.

    Only applicable when using pipx. pip users don't have injected plugins.

    Returns:
        {
            "success": bool,
            "skipped": bool,   # True if pipx not available (pip users)
            "error": Optional[str]
        }
    """
    # Mock support: TITAN_MOCK_PLUGINS_FAIL=1 simulates a plugins update failure
    if os.environ.get("TITAN_MOCK_UPDATE"):
        if os.environ.get("TITAN_MOCK_PLUGINS_FAIL"):
            return {"success": False, "skipped": False, "error": "Mock plugins failure"}
        return {"success": True, "skipped": False, "error": None}

    result = {
        "success": False,
        "skipped": False,
        "error": None,
    }

    try:
        proc = subprocess.run(
            ["pipx", "upgrade", "--include-injected", "titan-cli"],
            capture_output=True,
            text=True,
            timeout=60
        )

        if proc.returncode == 0:
            result["success"] = True
        else:
            error_output = proc.stderr.strip() or proc.stdout.strip() or "Plugin upgrade failed"
            result["error"] = error_output
        return result

    except FileNotFoundError:
        # pipx not installed — no injected plugins to update
        result["success"] = True
        result["skipped"] = True
        return result
    except subprocess.TimeoutExpired:
        result["error"] = "Plugin update timed out"
        return result


def _get_installed_version_pipx() -> Optional[str]:
    """Get installed version of titan-cli from pipx."""
    try:
        proc = subprocess.run(
            ["pipx", "list", "--short"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if proc.returncode == 0:
            # Output format: "titan-cli 0.1.9"
            for line in proc.stdout.splitlines():
                if line.startswith("titan-cli"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1]
    except Exception:
        pass
    return None


def _get_installed_version_pip() -> Optional[str]:
    """Get installed version of titan-cli from pip."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "show", "titan-cli"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if proc.returncode == 0:
            # Look for "Version: 0.1.9"
            for line in proc.stdout.splitlines():
                if line.startswith("Version:"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return None


def get_update_message(update_info: Dict[str, any]) -> Optional[str]:
    """
    Generate user-friendly update message.

    Args:
        update_info: Result from check_for_updates()

    Returns:
        Formatted message string or None if no update needed
    """
    if not update_info["update_available"]:
        return None

    current = update_info["current_version"]
    latest = update_info["latest_version"]

    return (
        f"🔔 Update available: v{current} → v{latest}\n"
        f"   Run 'pipx upgrade titan-cli' to update"
    )
