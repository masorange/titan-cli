"""
StyledOptionList Widget

Custom OptionList that renders options with bold titles and dim descriptions.
Uses the same styling as BoldText and DimText components.
"""

from typing import List
from dataclasses import dataclass
from textual.widgets import OptionList
from textual.widgets.option_list import Option


@dataclass
class StyledOption:
    """
    Option with styled title and description.

    Attributes:
        id: Unique identifier for the option
        title: Title text (rendered with bold styling)
        description: Description text (rendered with dim styling)
        disabled: Whether the option is disabled
    """
    id: str
    title: str
    description: str = ""
    disabled: bool = False


class StyledOptionList(OptionList):
    """
    OptionList that renders options with bold titles and dim descriptions.

    This widget provides a consistent way to display lists of options across
    the application, using BoldText and DimText styling patterns.

    Usage:
        from titan_cli.ui.tui.widgets import StyledOptionList, StyledOption

        options = [
            StyledOption(
                id="workflow1",
                title="Release Notes",
                description="Generate multi-brand weekly release notes"
            ),
            StyledOption(
                id="workflow2",
                title="Create PR",
                description="Create a pull request with AI-generated description"
            ),
        ]

        option_list = StyledOptionList(*options)
    """

    def __init__(self, *options: StyledOption, **kwargs):
        """
        Initialize StyledOptionList with styled options.

        Args:
            *options: StyledOption instances to display
            **kwargs: Additional arguments passed to OptionList
        """
        # Convert StyledOptions to Option objects with markup
        option_objects = []
        for opt in options:
            if opt.description:
                # Title in bold, description in dim, separated by newline
                prompt = f"[bold]{opt.title}[/bold]\n[dim]{opt.description}[/dim]"
            else:
                # Just title in bold
                prompt = f"[bold]{opt.title}[/bold]"

            option_objects.append(
                Option(prompt, id=opt.id, disabled=opt.disabled)
            )

        super().__init__(*option_objects, **kwargs)

    def add_styled_option(self, option: StyledOption) -> None:
        """
        Add a new styled option to the list.

        Args:
            option: StyledOption to add
        """
        if option.description:
            prompt = f"[bold]{option.title}[/bold]\n[dim]{option.description}[/dim]"
        else:
            prompt = f"[bold]{option.title}[/bold]"

        self.add_option(Option(prompt, id=option.id, disabled=option.disabled))

    def set_styled_options(self, options: List[StyledOption]) -> None:
        """
        Replace all options with new styled options.

        Args:
            options: List of StyledOption instances
        """
        # Clear existing options
        self.clear_options()

        # Add new options
        for opt in options:
            self.add_styled_option(opt)
