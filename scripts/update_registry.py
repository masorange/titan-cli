#!/usr/bin/env python3
"""
Script to automatically update registry.json from plugin tags.

This script is typically run by GitHub Actions when a plugin tag is pushed.
It reads plugin metadata from pyproject.toml and updates registry.json.

Usage:
    python scripts/update_registry.py --plugin titan-plugin-git --version 1.0.0
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any
import tomllib  # Python 3.11+ stdlib


def load_pyproject(plugin_path: Path) -> Dict[str, Any]:
    """Load and parse pyproject.toml for a plugin"""
    pyproject_file = plugin_path / "pyproject.toml"

    if not pyproject_file.exists():
        raise FileNotFoundError(f"No pyproject.toml found at {pyproject_file}")

    try:
        with open(pyproject_file, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse {pyproject_file}: {e}")


def extract_plugin_metadata(
    plugin_name: str, version: str, pyproject: Dict[str, Any]
) -> Dict[str, Any]:
    """Extract plugin metadata from pyproject.toml"""

    project = pyproject.get("project", {})
    tool_poetry = pyproject.get("tool", {}).get("poetry", {})

    # Prefer project.dependencies over poetry dependencies
    dependencies = []
    if "dependencies" in project:
        deps = project["dependencies"]
        if isinstance(deps, list):
            dependencies = deps
        elif isinstance(deps, dict):
            dependencies = list(deps.keys())

    if not dependencies and "dependencies" in tool_poetry:
        dependencies = list(tool_poetry["dependencies"].keys())

    # Extract titan version requirement from dependencies
    min_titan_version = "1.0.0"
    for dep in dependencies:
        if isinstance(dep, str) and dep.startswith("titan-cli"):
            # Parse version from "titan-cli>=1.0.0"
            if ">=" in dep:
                min_titan_version = dep.split(">=")[1].strip()
            break

    # Extract plugin ID from name
    plugin_id = plugin_name.replace("titan-plugin-", "")

    return {
        "id": plugin_id,
        "name": project.get("name", plugin_name),
        "package": plugin_name,
        "version": version,
        "description": project.get("description", ""),
        "category": "official",
        "verified": True,
        "author": (project.get("authors") or [{}])[0].get("name", "MasMovil Titan Team"),
        "license": project.get("license", "MIT"),
        "min_titan_version": min_titan_version,
        "dependencies": extract_plugin_dependencies(plugin_id, dependencies),
        "python_dependencies": extract_python_dependencies(dependencies),
        "keywords": project.get("keywords", []),
        "homepage": project.get("homepage"),
        "repository": project.get("repository")
    }


def extract_plugin_dependencies(plugin_id: str, dependencies: list) -> list:
    """Extract Titan plugin dependencies from dependency list"""
    plugin_deps = []
    for dep in dependencies:
        if isinstance(dep, str) and dep.startswith("titan-plugin-"):
            dep_id = dep.split("[")[0].replace("titan-plugin-", "").split(">=")[0].split("<")[0]
            if dep_id and dep_id not in plugin_deps:
                plugin_deps.append(dep_id)
    return plugin_deps


def extract_python_dependencies(dependencies: list) -> list:
    """Extract Python package dependencies (excluding titan packages)"""
    python_deps = []
    for dep in dependencies:
        if isinstance(dep, str):
            # Skip titan packages and normalize version specifiers
            if not (dep.startswith("titan-cli") or dep.startswith("titan-plugin-")):
                # Extract package name and version spec
                dep_str = dep.split("[")[0].strip()  # Remove extras
                if dep_str:
                    python_deps.append(dep_str)
    return python_deps


def update_registry(plugin_name: str, version: str, registry_file: Path):
    """Update registry.json with new plugin version"""

    # Validate inputs
    if not plugin_name.startswith("titan-plugin-"):
        print(f"Error: Plugin name must start with 'titan-plugin-', got '{plugin_name}'")
        sys.exit(1)

    if not registry_file.exists():
        print(f"Error: Registry file not found at {registry_file}")
        sys.exit(1)

    # Find plugin directory
    plugin_dir = Path("plugins") / plugin_name
    if not plugin_dir.exists():
        print(f"Error: Plugin directory not found at {plugin_dir}")
        sys.exit(1)

    # Load plugin metadata
    try:
        pyproject = load_pyproject(plugin_dir)
        metadata = extract_plugin_metadata(plugin_name, version, pyproject)
    except Exception as e:
        print(f"Error: Failed to extract plugin metadata: {e}")
        sys.exit(1)

    # Load current registry
    try:
        with open(registry_file) as f:
            registry = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in registry file: {e}")
        sys.exit(1)

    # Update plugin in registry
    plugin_id = metadata["id"]
    registry["plugins"][plugin_id] = metadata

    # Update last_updated timestamp
    from datetime import datetime
    registry["last_updated"] = datetime.utcnow().isoformat() + "Z"

    # Write updated registry
    try:
        with open(registry_file, "w") as f:
            json.dump(registry, f, indent=2)
            f.write("\n")  # Add trailing newline
        print(f"✓ Updated {plugin_id} to version {version}")
        print(f"✓ Registry updated: {registry_file}")
    except Exception as e:
        print(f"Error: Failed to write registry file: {e}")
        sys.exit(1)


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Update registry.json with new plugin version"
    )
    parser.add_argument(
        "--plugin",
        required=True,
        help="Plugin name (e.g., titan-plugin-git)"
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Plugin version (e.g., 1.0.0)"
    )
    parser.add_argument(
        "--registry",
        default="registry.json",
        help="Path to registry.json (default: ./registry.json)"
    )

    args = parser.parse_args()
    registry_file = Path(args.registry)

    try:
        update_registry(args.plugin, args.version, registry_file)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
