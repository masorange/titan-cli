"""
Credentials management for App Store Connect plugin.
"""

import json
from pathlib import Path
from typing import Dict, Optional, Tuple


class CredentialsManager:
    """
    Manage App Store Connect credentials from project configuration.

    Credentials are stored in plugins/titan-plugin-appstore/.appstoreconnect/credentials.json
    """

    CREDENTIALS_DIR = "plugins/titan-plugin-appstore/.appstoreconnect"
    CREDENTIALS_FILE = "credentials.json"

    @classmethod
    def _find_project_root(cls) -> Path:
        """
        Find project root by searching for .titan directory.

        Returns:
            Path to project root
        """
        current = Path.cwd()

        for parent in [current] + list(current.parents):
            if (parent / ".titan").exists():
                return parent

        return current

    @classmethod
    def get_credentials_path(cls) -> Path:
        """Get path to credentials file in plugins/titan-plugin-appstore/.appstoreconnect/"""
        project_root = cls._find_project_root()
        return project_root / cls.CREDENTIALS_DIR / cls.CREDENTIALS_FILE

    @classmethod
    def load_credentials(cls) -> Optional[Dict[str, str]]:
        """
        Load credentials from file.

        Returns:
            Credentials dict or None if not configured
        """
        credentials_file = cls.get_credentials_path()

        if not credentials_file.exists():
            return None

        try:
            with open(credentials_file, "r") as f:
                credentials = json.load(f)

            # Validate required fields
            required = ["key_id", "private_key_path"]
            if not all(field in credentials for field in required):
                return None

            # Ensure issuer_id exists (can be empty for Individual Keys)
            if "issuer_id" not in credentials:
                credentials["issuer_id"] = ""

            # Ensure vendor_number exists (can be empty if not using Sales Reports)
            if "vendor_number" not in credentials:
                credentials["vendor_number"] = ""

            return credentials

        except (json.JSONDecodeError, IOError):
            return None

    @classmethod
    def is_configured(cls) -> bool:
        """Check if credentials exist and are valid."""
        return cls.load_credentials() is not None

    @classmethod
    def get_client_credentials(cls) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get credentials for AppStoreConnectClient.

        Returns:
            Tuple of (issuer_id, key_id, private_key_path)
        """
        credentials = cls.load_credentials()

        if not credentials:
            return None, None, None

        project_root = cls._find_project_root()
        private_key_path = project_root / credentials["private_key_path"]

        if not private_key_path.exists():
            return None, None, None

        return (
            credentials.get("issuer_id") or None,
            credentials["key_id"],
            str(private_key_path),
        )

    @classmethod
    def get_vendor_number(cls) -> Optional[str]:
        """
        Get vendor number for Sales Reports.

        Returns:
            Vendor number or None if not configured
        """
        credentials = cls.load_credentials()

        if not credentials:
            return None

        vendor_number = credentials.get("vendor_number", "")
        return vendor_number if vendor_number else None

    @classmethod
    def save_credentials(
        cls,
        key_id: str,
        issuer_id: Optional[str],
        private_key_path: str,
        vendor_number: Optional[str] = None
    ) -> None:
        """
        Save credentials to file.

        Args:
            key_id: Key ID
            issuer_id: Issuer ID (can be None for Individual Keys)
            private_key_path: Path to .p8 file (relative to project root)
            vendor_number: Vendor number for Sales Reports (optional)
        """
        credentials_file = cls.get_credentials_path()
        credentials_file.parent.mkdir(parents=True, exist_ok=True)

        credentials = {
            "issuer_id": issuer_id or "",
            "key_id": key_id,
            "private_key_path": private_key_path,
            "vendor_number": vendor_number or "",
        }

        with open(credentials_file, "w") as f:
            json.dump(credentials, f, indent=2)
