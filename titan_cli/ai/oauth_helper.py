"""
OAuth Helper for AI Providers

Handles OAuth authentication for providers that support it (e.g., Gemini with gcloud).
"""

import subprocess
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class OAuthStatus:
    """OAuth authentication status"""
    available: bool
    authenticated: bool
    account: Optional[str] = None
    error: Optional[str] = None


class OAuthHelper:
    """
    Helper for OAuth authentication with AI providers

    Currently supports:
    - Google Cloud OAuth (gcloud) for Gemini

    Examples:
        >>> helper = OAuthHelper()
        >>> status = helper.check_gcloud_auth()
        >>> if status.authenticated:
        ...     print(f"Authenticated as: {status.account}")
    """

    @staticmethod
    def check_gcloud_auth() -> OAuthStatus:
        """
        Check if Google Cloud CLI is installed and authenticated

        Returns:
            OAuthStatus with authentication information
        """
        try:
            # Check if gcloud is installed
            result = subprocess.run(
                ["gcloud", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return OAuthStatus(
                    available=False,
                    authenticated=False,
                    error="gcloud is installed but not working properly"
                )

            # Check authentication status
            auth_result = subprocess.run(
                ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if auth_result.returncode == 0:
                account = auth_result.stdout.strip()

                if account:
                    return OAuthStatus(
                        available=True,
                        authenticated=True,
                        account=account
                    )
                else:
                    return OAuthStatus(
                        available=True,
                        authenticated=False,
                        error="No active gcloud account found"
                    )

            return OAuthStatus(
                available=True,
                authenticated=False,
                error="Could not check gcloud authentication"
            )

        except FileNotFoundError:
            return OAuthStatus(
                available=False,
                authenticated=False,
                error="gcloud CLI not installed"
            )

        except subprocess.TimeoutExpired:
            return OAuthStatus(
                available=False,
                authenticated=False,
                error="gcloud command timed out"
            )

        except Exception as e:
            return OAuthStatus(
                available=False,
                authenticated=False,
                error=f"Unexpected error: {str(e)}"
            )

    @staticmethod
    def get_install_instructions() -> str:
        """
        Get installation instructions for gcloud CLI

        Returns:
            Formatted installation instructions
        """
        return """Install Google Cloud CLI:

1. Visit: https://cloud.google.com/sdk/docs/install
2. Download and install for your platform
3. Run: gcloud init
4. Run: gcloud auth application-default login

This will authenticate your Google account for use with Gemini."""

    @staticmethod
    def get_auth_instructions() -> str:
        """
        Get authentication instructions for gcloud

        Returns:
            Formatted authentication instructions
        """
        return """Authenticate with Google Cloud:

Run: gcloud auth application-default login

This will open your browser to sign in with your Google account."""

    @staticmethod
    def validate_gcloud_auth() -> Tuple[bool, Optional[str]]:
        """
        Validate that gcloud auth is properly configured

        Returns:
            Tuple of (is_valid, error_message)
        """
        status = OAuthHelper.check_gcloud_auth()

        if not status.available:
            return False, status.error

        if not status.authenticated:
            return False, "Not authenticated. Run: gcloud auth application-default login"

        return True, None
