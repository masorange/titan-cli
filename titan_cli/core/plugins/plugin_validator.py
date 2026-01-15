"""
Plugin validator for marketplace plugins.

Validates plugin metadata, structure, and compatibility.
"""

import json
from pathlib import Path
from typing import Dict, Any

from .exceptions import PluginValidationError
from titan_cli.messages import msg


class PluginValidator:
    """
    Validates plugin metadata and structure.

    Ensures plugins meet Titan CLI requirements before installation.
    """

    # Required fields in plugin.json
    REQUIRED_FIELDS = {
        "name",
        "display_name",
        "version",
        "description",
        "author",
        "license",
        "min_titan_version",
        "entry_point",
        "category",
    }

    # Optional fields
    OPTIONAL_FIELDS = {
        "homepage",
        "repository",
        "dependencies",
        "python_dependencies",
        "keywords",
        "verified",
        "external_tools",
        "features",
    }

    def __init__(self, titan_version: str = "1.0.0"):
        """
        Initialize validator.

        Args:
            titan_version: Current Titan CLI version for compatibility checks
        """
        self.titan_version = titan_version

    def validate_plugin(self, plugin_path: Path) -> Dict[str, Any]:
        """
        Validate plugin directory structure and metadata.

        Args:
            plugin_path: Path to plugin directory

        Returns:
            Validated plugin metadata

        Raises:
            PluginValidationError: If validation fails
        """
        if not plugin_path.exists():
            raise PluginValidationError(
                msg.PluginValidator.PATH_NOT_EXISTS.format(path=plugin_path)
            )

        if not plugin_path.is_dir():
            raise PluginValidationError(
                msg.PluginValidator.PATH_NOT_DIR.format(path=plugin_path)
            )

        # Validate plugin.json
        metadata = self.validate_metadata(plugin_path)

        # Validate entry point
        self.validate_entry_point(plugin_path, metadata["entry_point"])

        # Check compatibility
        self.validate_compatibility(metadata)

        return metadata

    def validate_metadata(self, plugin_path: Path) -> Dict[str, Any]:
        """
        Validate plugin.json metadata file.

        Args:
            plugin_path: Path to plugin directory

        Returns:
            Parsed metadata dictionary

        Raises:
            PluginValidationError: If metadata is invalid
        """
        metadata_path = plugin_path / "plugin.json"

        if not metadata_path.exists():
            raise PluginValidationError(
                msg.PluginValidator.MISSING_METADATA.format(name=plugin_path.name)
            )

        try:
            with open(metadata_path) as f:
                metadata = json.load(f)
        except json.JSONDecodeError as e:
            raise PluginValidationError(
                msg.PluginValidator.INVALID_JSON.format(error=e)
            ) from e
        except Exception as e:
            raise PluginValidationError(
                msg.PluginValidator.READ_ERROR.format(error=e)
            ) from e

        # Check required fields
        missing_fields = self.REQUIRED_FIELDS - set(metadata.keys())
        if missing_fields:
            raise PluginValidationError(
                msg.PluginValidator.MISSING_FIELDS.format(fields=", ".join(missing_fields))
            )

        # Validate field types
        self._validate_field_types(metadata)

        return metadata

    def _validate_field_types(self, metadata: Dict[str, Any]) -> None:
        """
        Validate field types in metadata.

        Args:
            metadata: Plugin metadata dictionary

        Raises:
            PluginValidationError: If field types are invalid
        """
        # String fields
        string_fields = [
            "name", "display_name", "version", "description",
            "author", "license", "min_titan_version", "entry_point", "category"
        ]
        for field in string_fields:
            if field in metadata and not isinstance(metadata[field], str):
                raise PluginValidationError(
                    msg.PluginValidator.INVALID_FIELD_TYPE.format(field=field, field_type="string")
                )

        # List fields
        list_fields = ["dependencies", "python_dependencies", "keywords", "features", "external_tools"]
        for field in list_fields:
            if field in metadata and not isinstance(metadata[field], list):
                raise PluginValidationError(
                    msg.PluginValidator.INVALID_FIELD_TYPE.format(field=field, field_type="list")
                )

        # Boolean fields
        if "verified" in metadata and not isinstance(metadata["verified"], bool):
            raise PluginValidationError(
                msg.PluginValidator.INVALID_FIELD_TYPE.format(field="verified", field_type="boolean")
            )

        # Category validation
        valid_categories = ["official", "community"]
        if metadata.get("category") not in valid_categories:
            raise PluginValidationError(
                msg.PluginValidator.INVALID_CATEGORY.format(categories=", ".join(valid_categories))
            )

    def validate_entry_point(self, plugin_path: Path, entry_point: str) -> None:
        """
        Validate plugin entry point exists and is importable.

        Args:
            plugin_path: Path to plugin directory
            entry_point: Entry point string (e.g., "titan_plugin_git.plugin:GitPlugin")

        Raises:
            PluginValidationError: If entry point is invalid
        """
        if ":" not in entry_point:
            raise PluginValidationError(
                msg.PluginValidator.INVALID_ENTRY_POINT.format(entry_point=entry_point)
            )

        module_path, class_name = entry_point.split(":", 1)

        # Check if module file exists
        module_file = plugin_path / (module_path.replace(".", "/") + ".py")

        if not module_file.exists():
            raise PluginValidationError(
                msg.PluginValidator.ENTRY_POINT_NOT_FOUND.format(module_file=module_file)
            )

        # Verify class exists in module (basic check - don't import to avoid side effects)
        try:
            content = module_file.read_text()
            if f"class {class_name}" not in content:
                raise PluginValidationError(
                    msg.PluginValidator.CLASS_NOT_FOUND.format(
                        class_name=class_name,
                        file=module_file.name
                    )
                )
        except Exception as e:
            raise PluginValidationError(
                msg.PluginValidator.ENTRY_POINT_ERROR.format(error=e)
            ) from e

    def validate_compatibility(self, metadata: Dict[str, Any]) -> None:
        """
        Validate plugin compatibility with current Titan version.

        Args:
            metadata: Plugin metadata dictionary

        Raises:
            PluginValidationError: If plugin is incompatible
        """
        min_version = metadata.get("min_titan_version")

        if not min_version:
            return  # No minimum version specified

        # Simple version comparison (semantic versioning)
        if not self._is_version_compatible(min_version, self.titan_version):
            raise PluginValidationError(
                msg.PluginValidator.INCOMPATIBLE_VERSION.format(
                    min_version=min_version,
                    current_version=self.titan_version
                )
            )

    def _is_version_compatible(self, min_version: str, current_version: str) -> bool:
        """
        Check if current version meets minimum version requirement.

        Args:
            min_version: Minimum required version
            current_version: Current Titan version

        Returns:
            True if compatible, False otherwise
        """
        try:
            min_parts = [int(x) for x in min_version.split(".")]
            current_parts = [int(x) for x in current_version.split(".")]

            # Pad shorter version with zeros
            max_len = max(len(min_parts), len(current_parts))
            min_parts += [0] * (max_len - len(min_parts))
            current_parts += [0] * (max_len - len(current_parts))

            # Compare versions
            return current_parts >= min_parts

        except (ValueError, AttributeError):
            # If version parsing fails, assume compatible
            return True

    def validate_dependencies(
        self,
        metadata: Dict[str, Any],
        installed_plugins: list[str]
    ) -> list[str]:
        """
        Validate plugin dependencies are met.

        Args:
            metadata: Plugin metadata dictionary
            installed_plugins: List of installed plugin names

        Returns:
            List of missing dependencies

        Raises:
            PluginValidationError: If dependencies check fails
        """
        dependencies = metadata.get("dependencies", [])

        if not isinstance(dependencies, list):
            raise PluginValidationError(msg.PluginValidator.INVALID_DEPENDENCIES)

        missing = []
        for dep in dependencies:
            if dep not in installed_plugins:
                missing.append(dep)

        return missing
