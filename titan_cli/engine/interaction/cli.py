"""CLI/stdout-backed interaction port."""

from __future__ import annotations

from .base import InteractionPort


class CLIInteractionPort(InteractionPort):
    """Minimal terminal interaction adapter for non-Textual execution."""

    def info(self, message: str) -> None:
        print(message)

    def warning(self, message: str) -> None:
        print(message)

    def error(self, message: str) -> None:
        print(message)

    def step_output(self, text: str) -> None:
        print(text)

    def success_text(self, message: str) -> None:
        print(message)

    def begin_step(self, step_name: str) -> None:
        print(f"[{step_name}]")

    def confirm(self, prompt_id: str, message: str, default: bool = False) -> bool:
        suffix = " [Y/n]" if default else " [y/N]"
        raw = input(f"{message}{suffix} ").strip().lower()
        if not raw:
            return default
        return raw in {"y", "yes"}

    def input_text(
        self,
        prompt_id: str,
        message: str,
        default: str | None = None,
    ) -> str:
        suffix = f" [{default}]" if default else ""
        raw = input(f"{message}{suffix} ")
        return raw if raw else (default or "")
