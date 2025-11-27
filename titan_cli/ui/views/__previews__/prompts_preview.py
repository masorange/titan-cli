"""
Prompts Component Preview

A non-interactive script to show what the PromptsRenderer components look like.
"""

from titan_cli.ui.components.typography import TextRenderer
from titan_cli.ui.components.panel import PanelRenderer
from titan_cli.ui.components.spacer import SpacerRenderer

def preview_all():
    """Showcases the appearance of various prompts."""
    text = TextRenderer()
    panel = PanelRenderer()
    spacer = SpacerRenderer()

    text.title("Prompts Component Preview", justify="center")
    text.subtitle("A non-interactive demonstration of what prompts look like.", justify="center")
    text.divider()

    # 1. Text Prompt
    text.title("1. Text Prompt (ask_text)")
    text.body("Renders a question with an optional default value.")
    panel.print("What is your name? [default: Titan User]: ", panel_type="info")
    spacer.line()

    # 2. Confirm Prompt
    text.title("2. Confirmation Prompt (ask_confirm)")
    text.body("Renders a Yes/No question with a default.")
    panel.print("Do you want to continue? [Y/n]: ", panel_type="info")
    spacer.line()

    # 3. Choice Prompt
    text.title("3. Choice Prompt (ask_choice)")
    text.body("Renders a question with a list of choices and a default.")
    panel.print(
        "Choose your favorite color\n"
        "Choices: [red, green, blue]\n"
        "Default: blue\n"
        "[blue]: ",
        panel_type="info"
    )
    spacer.line()

    # 4. Integer Prompt
    text.title("4. Integer Prompt (ask_int)")
    text.body("Renders a question that only accepts an integer within a range.")
    panel.print("How old are you? [1-120]: ", panel_type="info")
    spacer.line()

    # 5. Menu Prompt
    text.title("5. Menu Prompt (ask_menu)")
    text.body("Renders a numbered menu for selection.")
    menu_content = (
        "Select an action to perform:\n\n"
        "  1. 🚀 Launch rocket\n"
        "  2. 🔧 Build module\n"
        "  3. 🛰️ Deploy satellite\n\n"
        "Choose option (1-3): "
    )
    panel.print(menu_content, panel_type="info")
    spacer.line()

    text.success("Prompts Preview Complete")

if __name__ == "__main__":
    preview_all()