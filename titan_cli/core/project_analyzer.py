"""
Project structure analyzer for Titan CLI.

Detects project types and standard file/directory locations automatically.
"""

import re
from pathlib import Path
from typing import Optional, Dict, List
from enum import Enum


class ProjectType(Enum):
    """Supported project types."""

    IOS = "ios"
    ANDROID = "android"
    FLUTTER = "flutter"
    REACT_NATIVE = "react-native"
    PYTHON = "python"
    NODEJS = "nodejs"
    UNKNOWN = "unknown"


class ProjectStructure:
    """Detected project structure and locations."""

    def __init__(
        self,
        project_type: ProjectType,
        root_path: Path,
        release_notes_dir: Optional[Path] = None,
        docs_dir: Optional[Path] = None,
        metadata: Optional[Dict[str, any]] = None,
    ):
        self.project_type = project_type
        self.root_path = root_path
        self.release_notes_dir = release_notes_dir
        self.docs_dir = docs_dir
        self.metadata = metadata or {}

    def __repr__(self):
        return (
            f"ProjectStructure("
            f"type={self.project_type.value}, "
            f"root={self.root_path}, "
            f"release_notes={self.release_notes_dir})"
        )


class ProjectAnalyzer:
    """
    Analyzes project structure to detect type and standard locations.

    Detects:
    - Project type (iOS, Android, Flutter, etc.)
    - Release notes directory (preferred location)
    - Documentation directory
    - Additional metadata (app name, module structure, etc.)

    Usage:
        analyzer = ProjectAnalyzer(Path.cwd())
        structure = analyzer.analyze()
        print(f"Project type: {structure.project_type}")
        print(f"Release notes dir: {structure.release_notes_dir}")
    """

    # Patterns for detecting project types
    IOS_PATTERNS = [
        "*.xcodeproj",
        "*.xcworkspace",
        "Podfile",
        "Package.swift",
        "Cartfile",
    ]

    ANDROID_PATTERNS = [
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "settings.gradle.kts",
        "gradlew",
        "app/build.gradle",
    ]

    FLUTTER_PATTERNS = [
        "pubspec.yaml",
        "lib/main.dart",
    ]

    REACT_NATIVE_PATTERNS = [
        "app.json",
        "metro.config.js",
        "ios/*.xcodeproj",
        "android/build.gradle",
    ]

    PYTHON_PATTERNS = [
        "setup.py",
        "pyproject.toml",
        "requirements.txt",
        "Pipfile",
    ]

    NODEJS_PATTERNS = [
        "package.json",
        "yarn.lock",
        "pnpm-lock.yaml",
    ]

    # Common release notes directory names (in priority order)
    RELEASE_NOTES_DIRS = [
        "ReleaseNotes",
        "release-notes",
        "RELEASE_NOTES",
        "docs/release-notes",
        "docs/releases",
        "documentation/releases",
        "CHANGELOG",
        "changelogs",
    ]

    # Common docs directory names
    DOCS_DIRS = [
        "docs",
        "documentation",
        "Documentation",
        "DOCS",
    ]

    def __init__(self, root_path: Path):
        """
        Initialize analyzer.

        Args:
            root_path: Root directory of the project to analyze
        """
        self.root_path = Path(root_path).resolve()

    def analyze(self) -> ProjectStructure:
        """
        Analyze project structure.

        Returns:
            ProjectStructure with detected information
        """
        project_type = self._detect_project_type()
        release_notes_dir = self._find_release_notes_dir()
        docs_dir = self._find_docs_dir()
        metadata = self._extract_metadata(project_type)

        return ProjectStructure(
            project_type=project_type,
            root_path=self.root_path,
            release_notes_dir=release_notes_dir,
            docs_dir=docs_dir,
            metadata=metadata,
        )

    def _detect_project_type(self) -> ProjectType:
        """
        Detect project type by looking for characteristic files.

        Returns:
            Detected ProjectType
        """
        # Check for Flutter first (can have iOS/Android subdirs)
        if self._has_patterns(self.FLUTTER_PATTERNS):
            return ProjectType.FLUTTER

        # Check for React Native (has both iOS and Android)
        if self._has_patterns(self.REACT_NATIVE_PATTERNS):
            return ProjectType.REACT_NATIVE

        # Check for iOS
        if self._has_patterns(self.IOS_PATTERNS):
            return ProjectType.IOS

        # Check for Android
        if self._has_patterns(self.ANDROID_PATTERNS):
            return ProjectType.ANDROID

        # Check for Python
        if self._has_patterns(self.PYTHON_PATTERNS):
            return ProjectType.PYTHON

        # Check for Node.js
        if self._has_patterns(self.NODEJS_PATTERNS):
            return ProjectType.NODEJS

        return ProjectType.UNKNOWN

    def _has_patterns(self, patterns: List[str]) -> bool:
        """
        Check if any of the patterns exist in the project.

        Args:
            patterns: List of glob patterns to search

        Returns:
            True if any pattern matches
        """
        for pattern in patterns:
            if list(self.root_path.glob(pattern)):
                return True
        return False

    def _find_release_notes_dir(self) -> Optional[Path]:
        """
        Find the release notes directory.

        Searches for common directory names and returns the first match.
        If none found, returns None.

        Returns:
            Path to release notes directory, or None
        """
        # First, check if any standard directory exists
        for dir_name in self.RELEASE_NOTES_DIRS:
            dir_path = self.root_path / dir_name
            if dir_path.exists() and dir_path.is_dir():
                return dir_path

        # If no existing directory, check for files that indicate location
        # Look for existing release notes files
        for pattern in ["**/release*.md", "**/CHANGELOG*.md", "**/RELEASE*.md"]:
            matches = list(self.root_path.glob(pattern))
            if matches:
                # Return the directory containing the file
                return matches[0].parent

        return None

    def _find_docs_dir(self) -> Optional[Path]:
        """
        Find the documentation directory.

        Returns:
            Path to docs directory, or None
        """
        for dir_name in self.DOCS_DIRS:
            dir_path = self.root_path / dir_name
            if dir_path.exists() and dir_path.is_dir():
                return dir_path

        return None

    def _extract_metadata(self, project_type: ProjectType) -> Dict[str, any]:
        """
        Extract additional metadata based on project type.

        Args:
            project_type: Detected project type

        Returns:
            Dictionary with metadata
        """
        metadata = {}

        if project_type == ProjectType.IOS:
            metadata.update(self._extract_ios_metadata())
        elif project_type == ProjectType.ANDROID:
            metadata.update(self._extract_android_metadata())
        elif project_type == ProjectType.FLUTTER:
            metadata.update(self._extract_flutter_metadata())

        return metadata

    def _extract_ios_metadata(self) -> Dict[str, any]:
        """Extract iOS-specific metadata."""
        metadata = {}

        # Find .xcodeproj
        xcodeproj_files = list(self.root_path.glob("*.xcodeproj"))
        if xcodeproj_files:
            metadata["xcodeproj"] = xcodeproj_files[0].name
            # App name is usually the xcodeproj name without extension
            metadata["app_name"] = xcodeproj_files[0].stem

        # Check for workspace
        xcworkspace_files = list(self.root_path.glob("*.xcworkspace"))
        if xcworkspace_files:
            metadata["xcworkspace"] = xcworkspace_files[0].name

        # Check for Podfile
        podfile = self.root_path / "Podfile"
        if podfile.exists():
            metadata["uses_cocoapods"] = True

        return metadata

    def _extract_android_metadata(self) -> Dict[str, any]:
        """Extract Android-specific metadata."""
        metadata = {}

        # Read settings.gradle to get app name
        settings_gradle = self.root_path / "settings.gradle"
        if settings_gradle.exists():
            content = settings_gradle.read_text()
            # Look for rootProject.name
            match = re.search(r"rootProject\.name\s*=\s*['\"](.+?)['\"]", content)
            if match:
                metadata["app_name"] = match.group(1)

        # Check for Kotlin
        if list(self.root_path.glob("**/*.kt")):
            metadata["uses_kotlin"] = True

        # Find app module
        app_dir = self.root_path / "app"
        if app_dir.exists():
            metadata["app_module"] = "app"

        return metadata

    def _extract_flutter_metadata(self) -> Dict[str, any]:
        """Extract Flutter-specific metadata."""
        metadata = {}

        # Read pubspec.yaml
        pubspec = self.root_path / "pubspec.yaml"
        if pubspec.exists():
            content = pubspec.read_text()
            # Look for name
            match = re.search(r"name:\s*(.+)", content)
            if match:
                metadata["app_name"] = match.group(1).strip()

        return metadata

    def get_preferred_release_notes_dir(
        self, platform: Optional[str] = None
    ) -> Path:
        """
        Get the preferred release notes directory for this project.

        If a release notes directory exists, returns it.
        Otherwise, returns a sensible default based on project type.

        Args:
            platform: Optional platform filter (e.g., "iOS", "Android")

        Returns:
            Path to preferred release notes directory
        """
        # Analyze project first
        structure = self.analyze()

        # If we found an existing directory, use it directly
        # iOS and Android projects don't use platform subdirectories
        if structure.release_notes_dir:
            return structure.release_notes_dir

        # For iOS projects, default to ReleaseNotes (no platform subdirs)
        if structure.project_type == ProjectType.IOS:
            return self.root_path / "ReleaseNotes"
        # For Android projects, default to docs/release-notes (no platform subdirs)
        elif structure.project_type == ProjectType.ANDROID:
            return self.root_path / "docs" / "release-notes"
        # For other projects, use docs/release-notes
        else:
            base_dir = self.root_path / "docs" / "release-notes"
            # Generic projects may use platform subdirectories
            if platform:
                return base_dir / platform.lower()
            return base_dir


def analyze_project(root_path: Optional[Path] = None) -> ProjectStructure:
    """
    Convenience function to analyze a project.

    Args:
        root_path: Project root path (defaults to current directory)

    Returns:
        ProjectStructure with detected information
    """
    if root_path is None:
        root_path = Path.cwd()

    analyzer = ProjectAnalyzer(root_path)
    return analyzer.analyze()


__all__ = [
    "ProjectType",
    "ProjectStructure",
    "ProjectAnalyzer",
    "analyze_project",
]
