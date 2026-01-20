"""
Tests for project analyzer.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from titan_cli.core.project_analyzer import (
    ProjectAnalyzer,
    ProjectType,
    ProjectStructure,
    analyze_project,
)


class TestProjectAnalyzer:
    """Tests for ProjectAnalyzer."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir)

    def test_detect_ios_project_xcodeproj(self, temp_project):
        """Test iOS project detection with .xcodeproj."""
        # Create .xcodeproj directory
        xcodeproj = temp_project / "MyApp.xcodeproj"
        xcodeproj.mkdir()

        analyzer = ProjectAnalyzer(temp_project)
        structure = analyzer.analyze()

        assert structure.project_type == ProjectType.IOS
        assert structure.metadata.get("xcodeproj") == "MyApp.xcodeproj"
        assert structure.metadata.get("app_name") == "MyApp"

    def test_detect_ios_project_podfile(self, temp_project):
        """Test iOS project detection with Podfile."""
        # Create Podfile
        podfile = temp_project / "Podfile"
        podfile.write_text("platform :ios, '13.0'")

        analyzer = ProjectAnalyzer(temp_project)
        structure = analyzer.analyze()

        assert structure.project_type == ProjectType.IOS
        assert structure.metadata.get("uses_cocoapods") is True

    def test_detect_android_project_gradle(self, temp_project):
        """Test Android project detection with build.gradle."""
        # Create build.gradle
        build_gradle = temp_project / "build.gradle"
        build_gradle.write_text("// Android project")

        # Create settings.gradle with app name
        settings_gradle = temp_project / "settings.gradle"
        settings_gradle.write_text('rootProject.name = "MyAndroidApp"')

        analyzer = ProjectAnalyzer(temp_project)
        structure = analyzer.analyze()

        assert structure.project_type == ProjectType.ANDROID
        assert structure.metadata.get("app_name") == "MyAndroidApp"

    def test_detect_android_project_with_kotlin(self, temp_project):
        """Test Android project detection with Kotlin files."""
        # Create build.gradle
        build_gradle = temp_project / "build.gradle"
        build_gradle.write_text("// Android project")

        # Create Kotlin file
        kotlin_dir = temp_project / "app" / "src"
        kotlin_dir.mkdir(parents=True)
        kotlin_file = kotlin_dir / "MainActivity.kt"
        kotlin_file.write_text("class MainActivity")

        analyzer = ProjectAnalyzer(temp_project)
        structure = analyzer.analyze()

        assert structure.project_type == ProjectType.ANDROID
        assert structure.metadata.get("uses_kotlin") is True

    def test_detect_flutter_project(self, temp_project):
        """Test Flutter project detection."""
        # Create pubspec.yaml
        pubspec = temp_project / "pubspec.yaml"
        pubspec.write_text("name: my_flutter_app\n")

        # Create lib/main.dart
        lib_dir = temp_project / "lib"
        lib_dir.mkdir()
        main_dart = lib_dir / "main.dart"
        main_dart.write_text("void main() {}")

        analyzer = ProjectAnalyzer(temp_project)
        structure = analyzer.analyze()

        assert structure.project_type == ProjectType.FLUTTER
        assert structure.metadata.get("app_name") == "my_flutter_app"

    def test_detect_python_project_pyproject_toml(self, temp_project):
        """Test Python project detection with pyproject.toml."""
        # Create pyproject.toml
        pyproject = temp_project / "pyproject.toml"
        pyproject.write_text("[tool.poetry]\nname = 'my-python-app'")

        analyzer = ProjectAnalyzer(temp_project)
        structure = analyzer.analyze()

        assert structure.project_type == ProjectType.PYTHON

    def test_detect_python_project_requirements_txt(self, temp_project):
        """Test Python project detection with requirements.txt."""
        # Create requirements.txt
        requirements = temp_project / "requirements.txt"
        requirements.write_text("requests==2.28.0")

        analyzer = ProjectAnalyzer(temp_project)
        structure = analyzer.analyze()

        assert structure.project_type == ProjectType.PYTHON

    def test_detect_nodejs_project_package_json(self, temp_project):
        """Test Node.js project detection."""
        # Create package.json
        package_json = temp_project / "package.json"
        package_json.write_text('{"name": "my-node-app"}')

        analyzer = ProjectAnalyzer(temp_project)
        structure = analyzer.analyze()

        assert structure.project_type == ProjectType.NODEJS

    def test_detect_unknown_project(self, temp_project):
        """Test unknown project type."""
        analyzer = ProjectAnalyzer(temp_project)
        structure = analyzer.analyze()

        assert structure.project_type == ProjectType.UNKNOWN

    def test_find_existing_release_notes_dir(self, temp_project):
        """Test finding existing ReleaseNotes directory."""
        # Create ReleaseNotes directory
        release_notes = temp_project / "ReleaseNotes"
        release_notes.mkdir()

        analyzer = ProjectAnalyzer(temp_project)
        structure = analyzer.analyze()

        assert structure.release_notes_dir.resolve() == release_notes.resolve()

    def test_find_existing_docs_release_notes_dir(self, temp_project):
        """Test finding existing docs/release-notes directory."""
        # Create docs/release-notes directory
        docs_release = temp_project / "docs" / "release-notes"
        docs_release.mkdir(parents=True)

        analyzer = ProjectAnalyzer(temp_project)
        structure = analyzer.analyze()

        assert structure.release_notes_dir.resolve() == docs_release.resolve()

    def test_find_release_notes_from_files(self, temp_project):
        """Test finding release notes directory from existing files."""
        # Create a release notes file
        custom_dir = temp_project / "documentation" / "releases"
        custom_dir.mkdir(parents=True)
        release_file = custom_dir / "release-notes-1.0.md"
        release_file.write_text("# Release 1.0")

        analyzer = ProjectAnalyzer(temp_project)
        structure = analyzer.analyze()

        assert structure.release_notes_dir.resolve() == custom_dir.resolve()

    def test_find_docs_directory(self, temp_project):
        """Test finding docs directory."""
        # Create docs directory
        docs = temp_project / "docs"
        docs.mkdir()

        analyzer = ProjectAnalyzer(temp_project)
        structure = analyzer.analyze()

        assert structure.docs_dir.resolve() == docs.resolve()

    def test_get_preferred_release_notes_dir_ios(self, temp_project):
        """Test preferred directory for iOS project."""
        # Create iOS project
        xcodeproj = temp_project / "MyApp.xcodeproj"
        xcodeproj.mkdir()

        analyzer = ProjectAnalyzer(temp_project)
        preferred = analyzer.get_preferred_release_notes_dir(platform="iOS")

        # Should default to ReleaseNotes for iOS (no platform subdir)
        expected = (temp_project / "ReleaseNotes").resolve()
        assert preferred.resolve() == expected

    def test_get_preferred_release_notes_dir_android(self, temp_project):
        """Test preferred directory for Android project."""
        # Create Android project
        build_gradle = temp_project / "build.gradle"
        build_gradle.write_text("// Android")

        analyzer = ProjectAnalyzer(temp_project)
        preferred = analyzer.get_preferred_release_notes_dir(platform="Android")

        # Should default to docs/release-notes for Android (no platform subdir)
        expected = (temp_project / "docs" / "release-notes").resolve()
        assert preferred.resolve() == expected

    def test_get_preferred_release_notes_dir_existing(self, temp_project):
        """Test preferred directory uses existing if found."""
        # Create existing ReleaseNotes directory
        release_notes = temp_project / "ReleaseNotes"
        release_notes.mkdir()

        # Create iOS project
        xcodeproj = temp_project / "MyApp.xcodeproj"
        xcodeproj.mkdir()

        analyzer = ProjectAnalyzer(temp_project)
        preferred = analyzer.get_preferred_release_notes_dir(platform="iOS")

        # Should use existing directory directly (iOS doesn't use platform subdirs)
        expected = release_notes.resolve()
        assert preferred.resolve() == expected

    def test_analyze_project_convenience_function(self, temp_project):
        """Test analyze_project convenience function."""
        # Create iOS project
        xcodeproj = temp_project / "MyApp.xcodeproj"
        xcodeproj.mkdir()

        # Change to temp directory
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)
            structure = analyze_project()

            assert structure.project_type == ProjectType.IOS
            assert structure.root_path.resolve() == temp_project.resolve()
        finally:
            os.chdir(original_cwd)

    def test_analyze_project_with_path(self, temp_project):
        """Test analyze_project with explicit path."""
        # Create Android project
        build_gradle = temp_project / "build.gradle"
        build_gradle.write_text("// Android")

        structure = analyze_project(temp_project)

        assert structure.project_type == ProjectType.ANDROID
        assert structure.root_path.resolve() == temp_project.resolve()

    def test_project_structure_repr(self, temp_project):
        """Test ProjectStructure __repr__."""
        structure = ProjectStructure(
            project_type=ProjectType.IOS,
            root_path=temp_project,
            release_notes_dir=temp_project / "ReleaseNotes",
        )

        repr_str = repr(structure)

        assert "ProjectStructure" in repr_str
        assert "ios" in repr_str
        assert "ReleaseNotes" in repr_str
