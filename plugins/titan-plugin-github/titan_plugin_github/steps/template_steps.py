from pathlib import Path
from typing import List, Optional
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import WorkflowResult, Success, Skip, Error


def _find_template_files() -> List[Path]:
    """
    Find all issue template files in the repository.

    Returns:
        List of template file paths
    """
    templates = []

    # Check for single template files
    single_template_paths = [
        Path(".github/ISSUE_TEMPLATE.md"),
        Path(".github/issue_template.md"),
    ]

    for path in single_template_paths:
        if path.exists() and path.is_file():
            templates.append(path)

    # Check for multiple templates in ISSUE_TEMPLATE directory
    template_dir = Path(".github/ISSUE_TEMPLATE")
    if template_dir.exists() and template_dir.is_dir():
        # Find all .md and .yml files
        for ext in ["*.md", "*.yml", "*.yaml"]:
            templates.extend(template_dir.glob(ext))

    # Remove config.yml if present (it's not a template)
    templates = [t for t in templates if t.name.lower() not in ["config.yml", "config.yaml"]]

    return sorted(templates)


def _read_template_file(path: Path) -> Optional[str]:
    """
    Read a template file and return its content.

    Args:
        path: Path to the template file

    Returns:
        Template content or None if failed to read
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, IOError):
        return None


def find_issue_template_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Find and select a GitHub issue template.

    Searches for templates in:
    - .github/ISSUE_TEMPLATE.md
    - .github/issue_template.md
    - .github/ISSUE_TEMPLATE/*.md
    - .github/ISSUE_TEMPLATE/*.yml

    If multiple templates are found, prompts the user to choose one.
    """
    templates = _find_template_files()

    if not templates:
        return Skip("No issue template found")

    # If only one template, use it automatically
    if len(templates) == 1:
        template_content = _read_template_file(templates[0])
        if template_content:
            ctx.set("issue_template", template_content)
            return Success(f"Issue template found: {templates[0].name}")
        else:
            return Skip(f"Failed to read issue template: {templates[0]}")

    # Multiple templates found - let user choose
    if not ctx.views:
        # If no UI available, just use the first one
        template_content = _read_template_file(templates[0])
        if template_content:
            ctx.set("issue_template", template_content)
            return Success(f"Using first available template: {templates[0].name}")
        else:
            return Skip(f"Failed to read issue template: {templates[0]}")

    try:
        # Display template choices
        template_names = [t.name for t in templates]
        template_names.append("None (skip template)")

        if ctx.ui:
            ctx.ui.text.info(f"Found {len(templates)} issue templates:")

        choice_index = ctx.views.prompts.ask_choice(
            "Select an issue template:",
            choices=template_names,
            default=0
        )

        # If user chose "None", skip
        if choice_index == len(templates):
            return Skip("User skipped template selection")

        # Read selected template
        selected_template = templates[choice_index]
        template_content = _read_template_file(selected_template)

        if template_content:
            ctx.set("issue_template", template_content)
            return Success(f"Selected template: {selected_template.name}")
        else:
            return Error(f"Failed to read selected template: {selected_template}")

    except (KeyboardInterrupt, EOFError):
        return Skip("User cancelled template selection")
    except Exception as e:
        return Error(f"Failed to select template: {e}")
