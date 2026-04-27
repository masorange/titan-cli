"""Base interaction contracts for workflow execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import nullcontext
from typing import Any


class InteractionPort(ABC):
    """Abstract interaction surface consumed by workflow steps."""

    @abstractmethod
    def info(self, message: str) -> None:
        """Emit a neutral informational message."""

    @abstractmethod
    def warning(self, message: str) -> None:
        """Emit a warning message."""

    @abstractmethod
    def error(self, message: str) -> None:
        """Emit an error message."""

    @abstractmethod
    def step_output(self, text: str) -> None:
        """Emit step output content."""

    def text(self, message: str) -> None:
        """Legacy-compatible alias for plain text output."""
        self.step_output(message)

    def dim_text(self, message: str) -> None:
        """Legacy-compatible alias for low-emphasis text."""
        self.info(message)

    def success_text(self, message: str) -> None:
        """Legacy-compatible alias for success text."""
        self.info(message)

    def error_text(self, message: str) -> None:
        """Legacy-compatible alias for error text."""
        self.error(message)

    def warning_text(self, message: str) -> None:
        """Legacy-compatible alias for warning text."""
        self.warning(message)

    def bold_text(self, message: str) -> None:
        """Legacy-compatible alias for emphasized text output."""
        self.step_output(message)

    def bold_primary_text(self, message: str) -> None:
        """Legacy-compatible alias for emphasized primary text output."""
        self.step_output(message)

    def primary_text(self, message: str) -> None:
        """Legacy-compatible alias for primary text output."""
        self.step_output(message)

    def markdown(self, markdown_text: str) -> None:
        """Render markdown-capable output in the current UI."""
        self.step_output(markdown_text)

    def begin_step(self, step_name: str) -> None:
        """Hook called when a step starts."""

    def end_step(self, result_type: str) -> None:
        """Hook called when a step ends."""

    def confirm(self, prompt_id: str, message: str, default: bool = False) -> bool:
        """Request a confirmation from the current UI client."""
        raise NotImplementedError("confirm is not implemented for this interaction port")

    def input_text(
        self,
        prompt_id: str,
        message: str,
        default: str | None = None,
    ) -> str:
        """Request text input from the current UI client."""
        raise NotImplementedError("input_text is not implemented for this interaction port")

    def multiline_text(
        self,
        prompt_id: str,
        message: str,
        default: str | None = None,
    ) -> str:
        """Request multiline input from the current UI client."""
        return self.input_text(prompt_id=prompt_id, message=message, default=default)

    def ask_confirm(self, message: str, default: bool = False) -> bool:
        """Legacy-compatible confirmation API."""
        return self.confirm(prompt_id="confirm", message=message, default=default)

    def ask_text(self, message: str, default: str = "") -> str:
        """Legacy-compatible single-line prompt API."""
        return self.input_text(prompt_id="text", message=message, default=default)

    def ask_multiline(self, message: str, default: str = "") -> str:
        """Legacy-compatible multiline prompt API."""
        return self.multiline_text(prompt_id="multiline", message=message, default=default)

    def ask_multiselect(self, message: str, options: list[Any]) -> list[Any]:
        """Legacy-compatible multiselect API.

        Headless execution cannot display an interactive picker, so default to the
        options already marked as selected. If the option shape is unknown, use
        its value when present and otherwise the option itself.
        """
        selected: list[Any] = []
        for option in options:
            if getattr(option, "selected", False):
                selected.append(getattr(option, "value", option))
        if selected:
            return selected
        return [getattr(option, "value", option) for option in options]

    def show_diff_stat(
        self,
        formatted_files: list[str],
        formatted_summary: list[str],
        title: str,
        use_panel: bool = False,
    ) -> None:
        """Legacy-compatible diff renderer for non-Textual execution."""
        self.step_output(title)
        for line in formatted_files:
            self.step_output(line)
        for line in formatted_summary:
            self.step_output(line)

    def loading(self, message: str):
        """Legacy-compatible loading context manager."""
        self.info(message)
        return nullcontext()

    def select_one(
        self,
        prompt_id: str,
        message: str,
        options: list[dict[str, Any]],
    ) -> str:
        """Request a single-choice selection from the current UI client."""
        raise NotImplementedError("select_one is not implemented for this interaction port")
