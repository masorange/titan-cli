"""Operations for public plugin step documentation inventory."""

from __future__ import annotations

import importlib
import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any


OFFICIAL_PLUGIN_REFS = {
    "git": {
        "package_dir": "plugins/titan-plugin-git",
        "plugin_ref": "titan_plugin_git.plugin:GitPlugin",
    },
    "github": {
        "package_dir": "plugins/titan-plugin-github",
        "plugin_ref": "titan_plugin_github.plugin:GitHubPlugin",
    },
    "jira": {
        "package_dir": "plugins/titan-plugin-jira",
        "plugin_ref": "titan_plugin_jira.plugin:JiraPlugin",
    },
}

SECTION_HEADERS = [
    "Requires:",
    "Inputs (from ctx.data):",
    "Outputs (saved to ctx.data):",
    "Returns:",
]


def ensure_plugin_import_paths(repo_root: Path) -> None:
    """Add repo and official plugin packages to ``sys.path``."""
    candidate_paths = [repo_root] + [repo_root / ref["package_dir"] for ref in OFFICIAL_PLUGIN_REFS.values()]
    for path in reversed(candidate_paths):
        resolved = str(path)
        if resolved not in sys.path:
            sys.path.insert(0, resolved)


def load_grouping_metadata(repo_root: Path, plugin_name: str) -> dict[str, Any]:
    """Load the editorial grouping metadata for a plugin step reference page."""
    meta_path = repo_root / "docs" / "plugins" / "_meta" / f"{plugin_name}-step-groups.json"
    return json.loads(meta_path.read_text(encoding="utf-8"))


def load_public_plugin_steps(plugin_name: str) -> dict[str, Any]:
    """Load the public workflow steps exposed by an official plugin."""
    plugin_ref = OFFICIAL_PLUGIN_REFS[plugin_name]["plugin_ref"]
    module_name, class_name = plugin_ref.split(":", 1)
    module = importlib.import_module(module_name)
    plugin_cls = getattr(module, class_name)
    plugin = plugin_cls()
    return plugin.get_steps()


def extract_docstring_summary(docstring: str) -> str:
    """Return the first non-empty line from a docstring."""
    for line in inspect.cleandoc(docstring).splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def parse_docstring_sections(docstring: str) -> dict[str, list[str]]:
    """Parse the canonical public-step docstring sections."""
    cleaned = inspect.cleandoc(docstring)
    sections: dict[str, list[str]] = {header[:-1]: [] for header in SECTION_HEADERS}
    current_header: str | None = None

    for raw_line in cleaned.splitlines():
        line = raw_line.rstrip()
        if line in SECTION_HEADERS:
            current_header = line[:-1]
            continue
        if current_header and line:
            sections[current_header].append(line)

    return sections


def collect_plugin_workflow_usage(repo_root: Path, plugin_name: str) -> dict[str, list[str]]:
    """Map public step names to built-in workflow files that use them."""
    workflow_dir = repo_root / OFFICIAL_PLUGIN_REFS[plugin_name]["package_dir"] / f"titan_plugin_{plugin_name}" / "workflows"
    usage: dict[str, list[str]] = {}

    plugin_pattern = re.compile(r"^\s*plugin:\s*([A-Za-z0-9_\-]+)\s*$")
    step_pattern = re.compile(r"^\s*step:\s*([A-Za-z0-9_\-]+)\s*$")

    for workflow_path in sorted(workflow_dir.glob("*.yaml")):
        current_plugin: str | None = None
        for line in workflow_path.read_text(encoding="utf-8").splitlines():
            plugin_match = plugin_pattern.match(line)
            if plugin_match:
                current_plugin = plugin_match.group(1)
                continue

            step_match = step_pattern.match(line)
            if step_match:
                step_name = step_match.group(1)
                if current_plugin == plugin_name:
                    usage.setdefault(step_name, []).append(workflow_path.stem)
                current_plugin = None

    return {step_name: sorted(set(workflows)) for step_name, workflows in usage.items()}


def build_plugin_inventory(repo_root: Path, plugin_name: str) -> tuple[dict[str, Any], list[str]]:
    """Build structured inventory data and consistency errors for one plugin."""
    ensure_plugin_import_paths(repo_root)
    metadata = load_grouping_metadata(repo_root, plugin_name)
    public_steps = load_public_plugin_steps(plugin_name)
    workflow_usage = collect_plugin_workflow_usage(repo_root, plugin_name)

    grouped_steps: dict[str, str] = {}
    errors: list[str] = []
    for group in metadata["groups"]:
        for step in group["steps"]:
            step_name = step["name"]
            if step_name in grouped_steps:
                errors.append(f"step '{step_name}' appears in multiple groups")
            grouped_steps[step_name] = group["name"]

    for step_name in sorted(public_steps):
        if step_name not in grouped_steps:
            errors.append(f"public step '{step_name}' is missing from grouping metadata")

    for step_name in sorted(grouped_steps):
        if step_name not in public_steps:
            errors.append(f"grouping metadata references unknown public step '{step_name}'")

    steps_payload: list[dict[str, Any]] = []
    for step_name, step_fn in sorted(public_steps.items()):
        docstring = inspect.getdoc(step_fn) or ""
        sections = parse_docstring_sections(docstring)
        if not docstring:
            errors.append(f"public step '{step_name}' is missing a docstring")
        if not sections["Returns"]:
            errors.append(f"public step '{step_name}' is missing a Returns section")

        steps_payload.append(
            {
                "name": step_name,
                "group": grouped_steps.get(step_name),
                "module": step_fn.__module__,
                "function": step_fn.__name__,
                "summary": extract_docstring_summary(docstring),
                "docstring_sections": sections,
                "used_by_workflows": workflow_usage.get(step_name, []),
            }
        )

    return {
        "plugin": plugin_name,
        "groups": metadata["groups"],
        "steps": steps_payload,
    }, errors


def build_all_plugin_inventories(repo_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Build inventories and aggregate consistency errors for all official plugins."""
    inventories: list[dict[str, Any]] = []
    errors: list[str] = []

    for plugin_name in sorted(OFFICIAL_PLUGIN_REFS):
        inventory, plugin_errors = build_plugin_inventory(repo_root, plugin_name)
        inventories.append(inventory)
        errors.extend(f"{plugin_name}: {error}" for error in plugin_errors)

    return inventories, errors


def inventory_output_path(repo_root: Path, plugin_name: str) -> Path:
    """Return the generated JSON output path for a plugin inventory."""
    return repo_root / "docs" / "plugins" / "_generated" / f"{plugin_name}-step-inventory.json"


def write_plugin_inventories(repo_root: Path, inventories: list[dict[str, Any]]) -> list[Path]:
    """Write generated inventory JSON files to the docs tree."""
    output_dir = repo_root / "docs" / "plugins" / "_generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for inventory in inventories:
        output_path = inventory_output_path(repo_root, inventory["plugin"])
        output_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
        paths.append(output_path)
    return paths


def validate_generated_inventories(repo_root: Path, inventories: list[dict[str, Any]]) -> list[str]:
    """Validate that generated inventory files exist and match current computed output."""
    errors: list[str] = []

    for inventory in inventories:
        expected = json.dumps(inventory, indent=2) + "\n"
        output_path = inventory_output_path(repo_root, inventory["plugin"])
        if not output_path.exists():
            errors.append(f"missing generated inventory: {output_path.relative_to(repo_root)}")
            continue

        current = output_path.read_text(encoding="utf-8")
        if current != expected:
            errors.append(f"stale generated inventory: {output_path.relative_to(repo_root)}")

    return errors


__all__ = [
    "OFFICIAL_PLUGIN_REFS",
    "build_all_plugin_inventories",
    "build_plugin_inventory",
    "extract_docstring_summary",
    "inventory_output_path",
    "parse_docstring_sections",
    "validate_generated_inventories",
    "write_plugin_inventories",
]
