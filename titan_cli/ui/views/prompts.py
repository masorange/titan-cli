"""
Prompts Component (View)

Class-based, theme-aware wrapper for rich.prompt. This is considered a 'view'
because it is a composite component that uses other components (like TextRenderer)
to display its own UI (e.g., error messages).
"""

from typing import Optional, List, Callable, Tuple
from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from ..console import get_console
from ..components.typography import TextRenderer
from ...messages import msg # Import messages

class PromptsRenderer:
    """
    Reusable wrapper for rich.prompt with theme-aware styling and validation.
    """

    def __init__(
        self,
        console: Optional[Console] = None,
        text_renderer: Optional[TextRenderer] = None,
    ):
        """
        Initializes the PromptsRenderer.

        Args:
            console: A Rich Console instance. If None, uses the global theme-aware console.
            text_renderer: An instance of TextRenderer for displaying messages.
                           If None, a default instance is created.
        """
        if console is None:
            console = get_console()
        self.console = console

        if text_renderer is None:
            text_renderer = TextRenderer(console=self.console)
        self.text = text_renderer


    def ask_text(
        self,
        prompt: str,
        default: str = "",
        password: bool = False,
        validator: Optional[Callable[[str], bool]] = None
    ) -> str:
        """
        Ask for text input.
        """
        while True:
            value = Prompt.ask(
                prompt,
                default=default if default else None,
                password=password,
                console=self.console
            )

            if validator and not validator(value):
                self.text.error(msg.Prompts.INVALID_INPUT, show_emoji=False)
                continue

            return value

    def ask_confirm(
        self,
        question: str,
        default: bool = False
    ) -> bool:
        """
        Ask for yes/no confirmation.
        """
        return Confirm.ask(question, default=default, console=self.console)

    def ask_choice(
        self,
        question: str,
        choices: List[str],
        default: Optional[str] = None
    ) -> str:
        """
        Ask user to choose from a list of options.
        """
        return Prompt.ask(
            question,
            choices=choices,
            default=default,
            console=self.console
        )

    def ask_int(
        self,
        question: str,
        default: Optional[int] = None,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None
    ) -> int:
        """
        Ask for integer input.
        """
        while True:
            # IntPrompt itself handles non-integer input by re-prompting.
            # The TypeError occurred if the user just hits Enter with no default.
            value = IntPrompt.ask(question, default=default, console=self.console)
            
            # Handle case where user hits Enter without input and no default is set
            if value is None:
                self.text.error(msg.Prompts.MISSING_VALUE, show_emoji=False)
                continue

            if min_value is not None and value < min_value:
                self.text.error(msg.Prompts.VALUE_TOO_LOW.format(min=min_value), show_emoji=False)
                continue

            if max_value is not None and value > max_value:
                self.text.error(msg.Prompts.VALUE_TOO_HIGH.format(max=max_value), show_emoji=False)
                continue

            return value

    def ask_menu(
        self,
        question: str,
        options: List[Tuple[str, str]],
        allow_quit: bool = True
    ) -> Optional[str]:
        """
        Ask user to choose from a numbered menu.
        """
        self.text.title(question, justify="center")

        menu_options = list(options)
        if allow_quit:
            menu_options.append(("🛑 Quit", "quit"))

        for i, (label, _) in enumerate(menu_options, 1):
            self.text.body(f"  {i}. {label}")
        
        self.text.line()

        while True:
            try:
                # Use our own ask_text to handle prompt style if needed, or stick to Prompt.ask
                choice_str = Prompt.ask(
                    f"Choose option (1-{len(menu_options)})",
                    console=self.console
                )
                if not choice_str:
                    self.text.error(msg.Prompts.MISSING_VALUE, show_emoji=False)
                    continue

                choice = int(choice_str)

                if 1 <= choice <= len(menu_options):
                    _, value = menu_options[choice - 1]
                    if value == "quit":
                        return None
                    return value
                else:
                    self.text.error(msg.Prompts.INVALID_INPUT, show_emoji=False)
            except ValueError:
                self.text.error(msg.Prompts.NOT_A_NUMBER, show_emoji=False)
