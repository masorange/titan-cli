"""Dependency helpers for AI providers and gateways."""

from __future__ import annotations

import importlib
import subprocess
import sys
from dataclasses import dataclass

from titan_cli.core.plugins.community import is_running_in_pipx


@dataclass(frozen=True)
class DependencySpec:
    source_name: str
    modules: tuple[str, ...]
    packages: tuple[str, ...]


AI_DEPENDENCIES: dict[str, DependencySpec] = {
    "anthropic": DependencySpec(
        source_name="anthropic",
        modules=("anthropic",),
        packages=("anthropic",),
    ),
    "gemini": DependencySpec(
        source_name="gemini",
        modules=("google.genai", "google.auth"),
        packages=("google-genai", "google-auth"),
    ),
    "openai": DependencySpec(
        source_name="openai",
        modules=("openai",),
        packages=("openai",),
    ),
    "openai_compatible": DependencySpec(
        source_name="openai_compatible",
        modules=("openai",),
        packages=("openai",),
    ),
}


def find_missing_modules(source_name: str) -> list[str]:
    """Return required modules that are not importable."""
    spec = AI_DEPENDENCIES.get(source_name)
    if not spec:
        return []

    missing = []
    for module_name in spec.modules:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(module_name)
    return missing


def dependencies_available(source_name: str) -> bool:
    """Return True when all required modules are importable."""
    return not find_missing_modules(source_name)


def get_install_command(source_name: str) -> list[str] | None:
    """Return the install command for a source, or None if unknown."""
    spec = AI_DEPENDENCIES.get(source_name)
    if not spec:
        return None

    if is_running_in_pipx():
        return ["pipx", "inject", "titan-cli", *spec.packages]

    return [sys.executable, "-m", "pip", "install", *spec.packages]


def install_missing_dependencies(
    source_name: str,
) -> subprocess.CompletedProcess[str] | None:
    """Install dependencies for a source."""
    cmd = get_install_command(source_name)
    if not cmd:
        return None

    result = subprocess.run(cmd, capture_output=True, text=True)
    importlib.invalidate_caches()
    return result
