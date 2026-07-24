"""Google Cloud ADC helpers for the Firebase plugin."""

from __future__ import annotations

import subprocess
from typing import Optional


ADC_LOGIN_COMMAND = "gcloud auth application-default login"


def is_gcloud_installed() -> bool:
    """Return whether the gcloud CLI is installed and runnable."""
    try:
        result = subprocess.run(
            ["gcloud", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

    return result.returncode == 0


def get_active_account() -> Optional[str]:
    """Return the active gcloud account email, if one is configured."""
    try:
        result = subprocess.run(
            [
                "gcloud",
                "auth",
                "list",
                "--filter=status:ACTIVE",
                "--format=value(account)",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    account = result.stdout.strip()
    return account or None


def get_adc_access_token() -> Optional[str]:
    """Return an ADC access token from gcloud, if the user is logged in."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    token = result.stdout.strip()
    return token or None


def adc_login_hint() -> str:
    """Return the command users should run to create a personal ADC session."""
    return ADC_LOGIN_COMMAND
