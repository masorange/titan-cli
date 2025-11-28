# core/project_init.py
from pathlib import Path
import tomli_w

from ..ui.components.typography import TextRenderer
from ..ui.views.prompts import PromptsRenderer
from ..core.errors import ConfigWriteError

def initialize_project(project_path: Path) -> bool:
    """
    Interactively initializes a new Titan project in the specified directory.

    This function will prompt the user for project details (name, type)
    and create a .titan/config.toml file.

    Args:
        project_path: The absolute path to the project directory.

    Returns:
        True if initialization was successful, False otherwise.
    """
    text = TextRenderer()
    prompts = PromptsRenderer(text_renderer=text)

    text.title(f"Initializing Titan Project: [primary]{project_path.name}[/primary]")
    text.line()

    try:
        # Prompt for Project Name
        project_name = prompts.ask_text(
            "Enter a name for the project",
            default=project_path.name
        )

        # Prompt for Project Type
        project_type_choices = ["frontend", "backend", "fullstack", "library", "generic", "other"]
        project_type = prompts.ask_choice(
            "Select a project type",
            choices=project_type_choices,
            default="generic"
        )
        if project_type == "other":
            project_type = prompts.ask_text("Enter custom project type")

        # Prepare config structure
        config_data = {
            "project": {
                "name": project_name,
                "type": project_type
            }
        }

        # Create .titan directory and config file
        titan_dir = project_path / ".titan"
        titan_dir.mkdir(exist_ok=True)
        config_path = titan_dir / "config.toml"

        with open(config_path, "wb") as f:
            tomli_w.dump(config_data, f)

        text.success(f"Project '{project_name}' initialized successfully at: {config_path}")
        return True

    except (EOFError, KeyboardInterrupt):
        text.warning("Project initialization cancelled.")
        return False
    except (OSError, PermissionError) as e:
        error = ConfigWriteError(file_path=str(config_path), original_exception=e)
        text.error(str(error))
        return False
