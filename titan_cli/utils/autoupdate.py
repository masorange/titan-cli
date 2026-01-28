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

    Returns:
        Dictionary with update result:
        {
            "success": bool,
            "method": str,  # "pipx" or "pip"
            "error": Optional[str]
        }
    """
    result = {
        "success": False,
        "method": None,
        "error": None
    }

    # Try pipx first (recommended)
    try:
        subprocess.check_call(
            ["pipx", "upgrade", "--force", "titan-cli"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        result["success"] = True
        result["method"] = "pipx"
        return result
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass  # Try pip as fallback

    # Fallback to pip
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "titan-cli"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        result["success"] = True
        result["method"] = "pip"
        return result
    except subprocess.CalledProcessError as e:
        result["error"] = f"Update failed: {e}"
        return result


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
