"""Auto-update utility for Titan CLI."""

import sys
import subprocess
from typing import Dict, Optional
from pathlib import Path

from titan_cli import __version__


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

    except ImportError:
        result["error"] = "Missing dependencies (requests, packaging)"
    except Exception as e:
        result["error"] = str(e)

    return result


def perform_update() -> Dict[str, any]:
    """
    Perform auto-update using pipx or pip.

    Both the core CLI and injected plugins must update successfully.

    Returns:
        Dictionary with update result:
        {
            "success": bool,           # True only if core AND plugins updated
            "method": str,             # "pipx" or "pip"
            "installed_version": Optional[str],
            "error": Optional[str],    # Core update error
            "plugins_error": Optional[str]  # Plugin update error (pipx only)
        }
    """
    result = {
        "success": False,
        "method": None,
        "installed_version": None,
        "error": None,
        "plugins_error": None,
    }

    # Try pipx first (recommended)
    try:
        # Step 1: force-upgrade titan-cli core (without --include-injected to avoid
        # pip resolving plugin constraints and skipping the core upgrade)
        proc = subprocess.run(
            ["pipx", "upgrade", "--force", "titan-cli"],
            capture_output=True,
            text=True,
            timeout=60
        )

        if proc.returncode != 0:
            pass  # Fall through to pip fallback
        else:
            result["method"] = "pipx"

            # Step 2: upgrade injected plugins to match new core
            proc2 = subprocess.run(
                ["pipx", "upgrade", "--include-injected", "titan-cli"],
                capture_output=True,
                text=True,
                timeout=60
            )

            installed_version = _get_installed_version_pipx()
            result["installed_version"] = installed_version

            if not installed_version:
                result["error"] = "Could not verify installed version"
                return result

            if proc2.returncode != 0:
                result["plugins_error"] = proc2.stderr.strip() or "Plugin upgrade failed"
                return result

            result["success"] = True
            return result

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # Try pip as fallback

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
                return result
            else:
                result["error"] = "Could not verify installed version"
                return result
        else:
            result["error"] = f"Update failed: {proc.stderr}"
            return result
    except subprocess.TimeoutExpired:
        result["error"] = "Update timed out"
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
