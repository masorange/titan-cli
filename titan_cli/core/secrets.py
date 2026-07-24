from __future__ import annotations

# titan_cli/core/secrets.py
from collections.abc import Iterable
import os
from dataclasses import dataclass
import keyring
from pathlib import Path
import threading
from typing import Literal, Optional

from dotenv import dotenv_values, load_dotenv

ScopeType = Literal["env", "project", "user"]

_PROJECT_ENV_KEYS_LOCK = threading.Lock()
_PROJECT_ENV_KEYS_BY_PATH: dict[Path, set[str]] = {}


@dataclass(frozen=True)
class ResolvedSecret:
    """Secret value plus the scope that supplied it."""

    value: str
    scope: ScopeType


class SecretManager:
    """
    Manages secrets with a 3-level cascade:

    1. Environment variables (HIGHEST - CI/CD)
    2. Project secrets (.titan/secrets.env - team-shared)
    3. System keyring (USER - personal credentials)
    """

    def __init__(self, project_path: Optional[Path] = None):
        self.project_path = (project_path or Path.cwd()).expanduser().resolve(
            strict=False
        )
        self._project_secret_values: dict[str, str] = {}
        self._project_env_keys = self._shared_project_env_keys(self.project_path)
        self._load_project_secrets()

    def _load_project_secrets(self):
        """Load secrets from .titan/secrets.env"""
        secrets_file = self.project_path / ".titan" / "secrets.env"
        if secrets_file.exists():
            self._project_secret_values = self._read_project_secrets_file()
            self._mark_project_env_keys(
                key for key in self._project_secret_values if key not in os.environ
            )
            load_dotenv(secrets_file)

    def get(self, key: str, namespace: str = "titan") -> Optional[str]:
        """
        Get secret with cascading priority

        Priority:
        1. Environment variable (e.g., GITHUB_TOKEN, includes project secrets loaded at init)
        2. System keyring (user-level)
        3. None

        Note: Project secrets (.titan/secrets.env) are loaded
        into environment on init, so they are checked in step 1.
        """
        resolved = self.get_with_scope(key, namespace=namespace)
        return resolved.value if resolved else None

    def get_with_scope(
        self,
        key: str,
        namespace: str = "titan",
    ) -> Optional[ResolvedSecret]:
        """Get a secret with the scope that supplied the winning value."""
        env_key = key.upper()
        self._refresh_project_secret_values()
        env_value = os.environ.get(env_key)
        project_value = self._project_secret_values.get(env_key)

        if env_value is not None:
            if self._is_project_env_key(env_key) and project_value is not None:
                if env_value != project_value:
                    os.environ[env_key] = project_value
                return ResolvedSecret(project_value, "project")
            return ResolvedSecret(env_value, "env")

        if project_value is not None:
            return ResolvedSecret(project_value, "project")

        try:
            value = keyring.get_password(namespace, key)
            if value:
                return ResolvedSecret(value, "user")
        except Exception:
            pass  # Keyring might not be available

        return None

    def set(
        self, key: str, value: str, namespace: str = "titan", scope: ScopeType = "user"
    ):
        """
        Set secret

        Args:
            key: Secret key (e.g., "anthropic_api_key")
            value: Secret value
            namespace: Keyring namespace
            scope: Where to store:
                - "env": Current environment only (temporary)
                - "project": .titan/secrets.env (team-shared)
                - "user": System keyring (personal, secure)
        """
        if scope == "env":
            # Set in current environment only
            env_key = key.upper()
            os.environ[env_key] = value
            self._discard_project_env_key(env_key)

        elif scope == "user":
            # Store in system keyring (most secure)
            keyring.set_password(namespace, key, value)

        elif scope == "project":
            # Store in .titan/secrets.env
            secrets_file = self.project_path / ".titan" / "secrets.env"
            secrets_file.parent.mkdir(parents=True, exist_ok=True)
            key_upper = key.upper()
            self._refresh_project_secret_values()
            should_update_env = (
                self._is_project_env_key(key_upper) or key_upper not in os.environ
            )

            # Read existing content
            existing_lines = []
            if secrets_file.exists():
                with open(secrets_file, "r") as f:
                    existing_lines = f.readlines()

            # Update or append
            updated = False
            for i, line in enumerate(existing_lines):
                if line.startswith(f"{key_upper}="):
                    existing_lines[i] = f"{key_upper}='{value}'\n"
                    updated = True
                    break

            if not updated:
                existing_lines.append(f"{key_upper}='{value}'\n")

            # Write back
            with open(secrets_file, "w") as f:
                f.writelines(existing_lines)
            self._project_secret_values[key_upper] = value
            if should_update_env:
                os.environ[key_upper] = value
                self._mark_project_env_key(key_upper)

    def delete(self, key: str, namespace: str = "titan", scope: ScopeType = "user"):
        """Delete secret from specified scope"""
        if scope == "env":
            env_key = key.upper()
            os.environ.pop(env_key, None)
            self._discard_project_env_key(env_key)

        elif scope == "user":
            try:
                keyring.delete_password(namespace, key)
            except Exception:
                pass  # Keyring might not be available

        elif scope == "project":
            secrets_file = self.project_path / ".titan" / "secrets.env"
            if not secrets_file.exists():
                return
            key_upper = key.upper()
            self._project_secret_values.pop(key_upper, None)

            # Read and filter
            with open(secrets_file, "r") as f:
                lines = f.readlines()

            filtered = [line for line in lines if not line.startswith(f"{key_upper}=")]

            # Write back
            with open(secrets_file, "w") as f:
                f.writelines(filtered)
            if self._is_project_env_key(key_upper):
                os.environ.pop(key_upper, None)
                self._discard_project_env_key(key_upper)

    def _read_project_secrets_file(self) -> dict[str, str]:
        """Read project secrets without consulting process environment."""
        secrets_file = self.project_path / ".titan" / "secrets.env"
        if not secrets_file.exists():
            return {}
        values = dotenv_values(secrets_file)
        return {
            key.upper(): value for key, value in values.items() if value is not None
        }

    @staticmethod
    def _shared_project_env_keys(project_path: Path) -> set[str]:
        """Return the process-wide project-injected env key set for a project."""
        with _PROJECT_ENV_KEYS_LOCK:
            return _PROJECT_ENV_KEYS_BY_PATH.setdefault(project_path, set())

    def _refresh_project_secret_values(self) -> None:
        """Refresh project secret values from disk without mutating env."""
        self._project_secret_values = self._read_project_secrets_file()

    def _is_project_env_key(self, key: str) -> bool:
        with _PROJECT_ENV_KEYS_LOCK:
            return key in self._project_env_keys

    def _mark_project_env_key(self, key: str) -> None:
        with _PROJECT_ENV_KEYS_LOCK:
            self._project_env_keys.add(key)

    def _mark_project_env_keys(self, keys: Iterable[str]) -> None:
        with _PROJECT_ENV_KEYS_LOCK:
            self._project_env_keys.update(keys)

    def _discard_project_env_key(self, key: str) -> None:
        with _PROJECT_ENV_KEYS_LOCK:
            self._project_env_keys.discard(key)
