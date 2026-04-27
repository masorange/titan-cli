"""UI-agnostic interaction ports for workflow execution."""

from .base import InteractionPort
from .cli import CLIInteractionPort
from .headless import HeadlessInteractionPort
from .textual import TextualInteractionPort

__all__ = [
    "CLIInteractionPort",
    "HeadlessInteractionPort",
    "InteractionPort",
    "TextualInteractionPort",
]

