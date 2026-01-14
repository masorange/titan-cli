"""
Tests for PluginValidator module.
"""

import json
import pytest

from titan_cli.core.plugins.plugin_validator import PluginValidator
from titan_cli.core.plugins.exceptions import PluginValidationError


@pytest.fixture
def temp_plugin_dir(tmp_path):
    """Create temporary plugin directory."""
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()
    return plugin_dir


@pytest.fixture
def valid_metadata():
    """Valid plugin metadata."""
    return {
        "name": "test-plugin",
        "display_name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "author": "Test Author",
        "license": "MIT",
        "min_titan_version": "1.0.0",
        "entry_point": "test_plugin.plugin:TestPlugin",
        "category": "official",
        "dependencies": [],
        "python_dependencies": [],
        "keywords": ["test"],
        "verified": True
    }


@pytest.fixture
def validator():
    """Create PluginValidator instance."""
    return PluginValidator(titan_version="1.0.0")


class TestPluginValidator:
    """Tests for PluginValidator class."""

    def test_init_with_default_version(self):
        """Test validator initialization with default version."""
        validator = PluginValidator()
        assert validator.titan_version == "1.0.0"

    def test_init_with_custom_version(self):
        """Test validator initialization with custom version."""
        validator = PluginValidator(titan_version="2.5.1")
        assert validator.titan_version == "2.5.1"

    def test_validate_plugin_success(self, validator, temp_plugin_dir, valid_metadata):
        """Test successful plugin validation."""
        # Create plugin.json
        plugin_json = temp_plugin_dir / "plugin.json"
        plugin_json.write_text(json.dumps(valid_metadata))

        # Create entry point file
        entry_point_file = temp_plugin_dir / "test_plugin" / "plugin.py"
        entry_point_file.parent.mkdir(parents=True)
        entry_point_file.write_text("class TestPlugin:\n    pass\n")

        metadata = validator.validate_plugin(temp_plugin_dir)

        assert metadata["name"] == "test-plugin"
        assert metadata["version"] == "1.0.0"

    def test_validate_plugin_directory_not_exists(self, validator, tmp_path):
        """Test validation with non-existent directory."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate_plugin(nonexistent)

        assert "does not exist" in str(exc_info.value)

    def test_validate_plugin_not_directory(self, validator, tmp_path):
        """Test validation with file instead of directory."""
        file_path = tmp_path / "file.txt"
        file_path.touch()

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate_plugin(file_path)

        assert "not a directory" in str(exc_info.value)

    def test_validate_metadata_success(self, validator, temp_plugin_dir, valid_metadata):
        """Test successful metadata validation."""
        plugin_json = temp_plugin_dir / "plugin.json"
        plugin_json.write_text(json.dumps(valid_metadata))

        metadata = validator.validate_metadata(temp_plugin_dir)

        assert metadata == valid_metadata

    def test_validate_metadata_missing_file(self, validator, temp_plugin_dir):
        """Test validation with missing plugin.json."""
        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate_metadata(temp_plugin_dir)

        assert "Missing plugin.json" in str(exc_info.value)

    def test_validate_metadata_invalid_json(self, validator, temp_plugin_dir):
        """Test validation with invalid JSON."""
        plugin_json = temp_plugin_dir / "plugin.json"
        plugin_json.write_text("{ invalid json }")

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate_metadata(temp_plugin_dir)

        assert "Invalid JSON" in str(exc_info.value)

    def test_validate_metadata_missing_required_fields(self, validator, temp_plugin_dir):
        """Test validation with missing required fields."""
        incomplete_metadata = {
            "name": "test-plugin",
            "version": "1.0.0"
        }

        plugin_json = temp_plugin_dir / "plugin.json"
        plugin_json.write_text(json.dumps(incomplete_metadata))

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate_metadata(temp_plugin_dir)

        assert "Missing required fields" in str(exc_info.value)

    def test_validate_field_types_string_fields(self, validator, temp_plugin_dir, valid_metadata):
        """Test validation of string field types."""
        # Make version a number instead of string
        invalid_metadata = valid_metadata.copy()
        invalid_metadata["version"] = 1.0

        plugin_json = temp_plugin_dir / "plugin.json"
        plugin_json.write_text(json.dumps(invalid_metadata))

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate_metadata(temp_plugin_dir)

        assert "must be a string" in str(exc_info.value)

    def test_validate_field_types_list_fields(self, validator, temp_plugin_dir, valid_metadata):
        """Test validation of list field types."""
        # Make dependencies a string instead of list
        invalid_metadata = valid_metadata.copy()
        invalid_metadata["dependencies"] = "not-a-list"

        plugin_json = temp_plugin_dir / "plugin.json"
        plugin_json.write_text(json.dumps(invalid_metadata))

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate_metadata(temp_plugin_dir)

        assert "must be a list" in str(exc_info.value)

    def test_validate_field_types_boolean_fields(self, validator, temp_plugin_dir, valid_metadata):
        """Test validation of boolean field types."""
        # Make verified a string instead of boolean
        invalid_metadata = valid_metadata.copy()
        invalid_metadata["verified"] = "true"

        plugin_json = temp_plugin_dir / "plugin.json"
        plugin_json.write_text(json.dumps(invalid_metadata))

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate_metadata(temp_plugin_dir)

        assert "must be a boolean" in str(exc_info.value)

    def test_validate_category_invalid(self, validator, temp_plugin_dir, valid_metadata):
        """Test validation with invalid category."""
        invalid_metadata = valid_metadata.copy()
        invalid_metadata["category"] = "invalid-category"

        plugin_json = temp_plugin_dir / "plugin.json"
        plugin_json.write_text(json.dumps(invalid_metadata))

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate_metadata(temp_plugin_dir)

        assert "must be one of" in str(exc_info.value)

    def test_validate_category_official(self, validator, temp_plugin_dir, valid_metadata):
        """Test validation with official category."""
        valid_metadata["category"] = "official"

        plugin_json = temp_plugin_dir / "plugin.json"
        plugin_json.write_text(json.dumps(valid_metadata))

        metadata = validator.validate_metadata(temp_plugin_dir)
        assert metadata["category"] == "official"

    def test_validate_category_community(self, validator, temp_plugin_dir, valid_metadata):
        """Test validation with community category."""
        valid_metadata["category"] = "community"

        plugin_json = temp_plugin_dir / "plugin.json"
        plugin_json.write_text(json.dumps(valid_metadata))

        metadata = validator.validate_metadata(temp_plugin_dir)
        assert metadata["category"] == "community"

    def test_validate_entry_point_success(self, validator, temp_plugin_dir):
        """Test successful entry point validation."""
        # Create entry point file
        entry_point_file = temp_plugin_dir / "test_plugin" / "plugin.py"
        entry_point_file.parent.mkdir(parents=True)
        entry_point_file.write_text("class TestPlugin:\n    pass\n")

        # Should not raise
        validator.validate_entry_point(temp_plugin_dir, "test_plugin.plugin:TestPlugin")

    def test_validate_entry_point_invalid_format(self, validator, temp_plugin_dir):
        """Test entry point validation with invalid format."""
        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate_entry_point(temp_plugin_dir, "invalid_format")

        assert "Invalid entry point format" in str(exc_info.value)

    def test_validate_entry_point_module_not_found(self, validator, temp_plugin_dir):
        """Test entry point validation with missing module file."""
        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate_entry_point(temp_plugin_dir, "nonexistent.module:Class")

        assert "Entry point module not found" in str(exc_info.value)

    def test_validate_entry_point_class_not_found(self, validator, temp_plugin_dir):
        """Test entry point validation with missing class."""
        # Create entry point file without the class
        entry_point_file = temp_plugin_dir / "test_plugin" / "plugin.py"
        entry_point_file.parent.mkdir(parents=True)
        entry_point_file.write_text("# No class here\n")

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate_entry_point(temp_plugin_dir, "test_plugin.plugin:TestPlugin")

        assert "Entry point class" in str(exc_info.value)
        assert "not found" in str(exc_info.value)

    def test_validate_compatibility_no_min_version(self, validator):
        """Test compatibility validation with no min_version specified."""
        metadata = {"name": "test"}

        # Should not raise
        validator.validate_compatibility(metadata)

    def test_validate_compatibility_compatible(self, validator, valid_metadata):
        """Test compatibility validation with compatible version."""
        valid_metadata["min_titan_version"] = "0.9.0"

        # Should not raise (1.0.0 >= 0.9.0)
        validator.validate_compatibility(valid_metadata)

    def test_validate_compatibility_exact_match(self, validator, valid_metadata):
        """Test compatibility validation with exact version match."""
        valid_metadata["min_titan_version"] = "1.0.0"

        # Should not raise (1.0.0 >= 1.0.0)
        validator.validate_compatibility(valid_metadata)

    def test_validate_compatibility_incompatible(self, valid_metadata):
        """Test compatibility validation with incompatible version."""
        validator = PluginValidator(titan_version="0.5.0")
        valid_metadata["min_titan_version"] = "1.0.0"

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate_compatibility(valid_metadata)

        assert "requires Titan CLI >=" in str(exc_info.value)
        assert "1.0.0" in str(exc_info.value)

    def test_is_version_compatible_simple(self, validator):
        """Test version compatibility with simple versions."""
        assert validator._is_version_compatible("1.0.0", "1.0.0")
        assert validator._is_version_compatible("1.0.0", "1.5.0")
        assert validator._is_version_compatible("1.0.0", "2.0.0")
        assert not validator._is_version_compatible("2.0.0", "1.0.0")

    def test_is_version_compatible_different_lengths(self, validator):
        """Test version compatibility with different version lengths."""
        assert validator._is_version_compatible("1.0", "1.0.0")
        assert validator._is_version_compatible("1.0.0", "1.0")
        assert validator._is_version_compatible("1", "1.0.0")

    def test_is_version_compatible_invalid_version(self, validator):
        """Test version compatibility with invalid version strings."""
        # Should return True if parsing fails (fail-safe)
        assert validator._is_version_compatible("invalid", "1.0.0")
        assert validator._is_version_compatible("1.0.0", "invalid")

    def test_validate_dependencies_no_dependencies(self, validator):
        """Test dependency validation with no dependencies."""
        metadata = {"dependencies": []}
        installed = ["git", "github"]

        missing = validator.validate_dependencies(metadata, installed)
        assert missing == []

    def test_validate_dependencies_all_installed(self, validator):
        """Test dependency validation with all dependencies installed."""
        metadata = {"dependencies": ["git", "github"]}
        installed = ["git", "github", "jira"]

        missing = validator.validate_dependencies(metadata, installed)
        assert missing == []

    def test_validate_dependencies_some_missing(self, validator):
        """Test dependency validation with missing dependencies."""
        metadata = {"dependencies": ["git", "github", "jira"]}
        installed = ["git"]

        missing = validator.validate_dependencies(metadata, installed)
        assert len(missing) == 2
        assert "github" in missing
        assert "jira" in missing

    def test_validate_dependencies_all_missing(self, validator):
        """Test dependency validation with all dependencies missing."""
        metadata = {"dependencies": ["git", "github"]}
        installed = []

        missing = validator.validate_dependencies(metadata, installed)
        assert len(missing) == 2
        assert "git" in missing
        assert "github" in missing

    def test_validate_dependencies_invalid_type(self, validator):
        """Test dependency validation with invalid dependencies type."""
        metadata = {"dependencies": "not-a-list"}
        installed = []

        with pytest.raises(PluginValidationError) as exc_info:
            validator.validate_dependencies(metadata, installed)

        assert "must be a list" in str(exc_info.value)

    def test_required_fields_constant(self):
        """Test that REQUIRED_FIELDS constant has expected fields."""
        required = PluginValidator.REQUIRED_FIELDS

        assert "name" in required
        assert "display_name" in required
        assert "version" in required
        assert "description" in required
        assert "author" in required
        assert "license" in required
        assert "min_titan_version" in required
        assert "entry_point" in required
        assert "category" in required

    def test_optional_fields_constant(self):
        """Test that OPTIONAL_FIELDS constant has expected fields."""
        optional = PluginValidator.OPTIONAL_FIELDS

        assert "homepage" in optional
        assert "repository" in optional
        assert "dependencies" in optional
        assert "python_dependencies" in optional
        assert "keywords" in optional
        assert "verified" in optional
