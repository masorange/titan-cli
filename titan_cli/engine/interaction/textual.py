"""Textual-backed interaction adapter."""

from __future__ import annotations

from .base import InteractionPort


class TextualInteractionPort(InteractionPort):
    """Adapter that exposes Textual components through the generic interaction port."""

    def __init__(self, textual_components) -> None:
        self.legacy = textual_components

    def __getattr__(self, name: str):
        return getattr(self.legacy, name)

    def info(self, message: str) -> None:
        self.legacy.text(message)

    def warning(self, message: str) -> None:
        self.legacy.warning_text(message)

    def error(self, message: str) -> None:
        self.legacy.error_text(message)

    def step_output(self, text: str) -> None:
        self.legacy.text(text)

    def confirm(self, prompt_id: str, message: str, default: bool = False) -> bool:
        return self.legacy.ask_confirm(message, default=default)

    def input_text(
        self,
        prompt_id: str,
        message: str,
        default: str | None = None,
    ) -> str:
        return self.legacy.ask_text(message, default=default or "")

    def multiline_text(
        self,
        prompt_id: str,
        message: str,
        default: str | None = None,
    ) -> str:
        return self.legacy.ask_multiline(message, default=default or "")
