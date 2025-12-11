"""
Loader Component

Animated loading spinner for long-running operations (e.g., AI generation).
"""

from typing import Optional, Literal
from rich.console import Console
from rich.spinner import Spinner
from ..console import get_console
from ...messages import msg


class LoaderRenderer:
    """
    Wrapper for rich.spinner.Spinner with theme-aware styling.

    Displays an animated spinner while operations are running,
    with provider-specific emojis for AI operations.

    Usage:
        # As context manager (recommended)
        with loader.spin("Generating commit message...", provider="claude"):
            result = generate_commit()

        # Manual control
        loader.start("Analyzing code...")
        result = analyze()
        loader.stop()
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize LoaderRenderer.

        Args:
            console: Rich console instance (uses default if None)
        """
        if console is None:
            console = get_console()
        self.console = console
        self._status = None

    def spin(
        self,
        text: str,
        provider: Optional[Literal["claude", "gemini", "ai"]] = None,
        spinner: str = "dots"
    ):
        """
        Context manager for animated loading spinner.

        Args:
            text: Message to display while loading
            provider: AI provider to show emoji for ("claude", "gemini", "ai", or None)
            spinner: Spinner style (default: "dots")
                    Options: "dots", "line", "arc", "arrow", "bounce", "circle", etc.

        Returns:
            Context manager that shows spinner while in context

        Examples:
            >>> # Simple spinner
            >>> with loader.spin("Processing..."):
            >>>     time.sleep(2)

            >>> # With Claude emoji
            >>> with loader.spin("Generating PR description...", provider="claude"):
            >>>     result = ai.generate(...)

            >>> # With Gemini emoji
            >>> with loader.spin("Analyzing code...", provider="gemini"):
            >>>     analysis = ai.analyze(...)
        """
        # Add emoji prefix if provider specified
        if provider:
            emoji_map = {
                "claude": msg.EMOJI.CLAUDE,
                "gemini": msg.EMOJI.GEMINI,
                "ai": msg.EMOJI.AI
            }
            emoji = emoji_map.get(provider, "")
            text = f"{emoji} {text}"

        return self.console.status(text, spinner=spinner)

    def start(
        self,
        text: str,
        provider: Optional[Literal["claude", "gemini", "ai"]] = None,
        spinner: str = "dots"
    ) -> None:
        """
        Start the spinner manually (remember to call stop()).

        Args:
            text: Message to display
            provider: AI provider emoji
            spinner: Spinner style

        Examples:
            >>> loader.start("Processing...")
            >>> do_work()
            >>> loader.stop()
        """
        if self._status is not None:
            self.stop()  # Stop any existing spinner

        # Add emoji prefix if provider specified
        if provider:
            emoji_map = {
                "claude": msg.EMOJI.CLAUDE,
                "gemini": msg.EMOJI.GEMINI,
                "ai": msg.EMOJI.AI
            }
            emoji = emoji_map.get(provider, "")
            text = f"{emoji} {text}"

        self._status = self.console.status(text, spinner=spinner)
        self._status.start()

    def stop(self) -> None:
        """
        Stop the currently running spinner.

        Examples:
            >>> loader.start("Working...")
            >>> do_work()
            >>> loader.stop()
        """
        if self._status is not None:
            self._status.stop()
            self._status = None

    def update(
        self,
        text: str,
        provider: Optional[Literal["claude", "gemini", "ai"]] = None
    ) -> None:
        """
        Update the text of a running spinner.

        Args:
            text: New message to display
            provider: AI provider emoji (updates emoji too)

        Examples:
            >>> loader.start("Step 1...")
            >>> do_step_1()
            >>> loader.update("Step 2...")
            >>> do_step_2()
            >>> loader.stop()
        """
        if self._status is None:
            raise RuntimeError("Loader not started. Call start() first.")

        # Add emoji prefix if provider specified
        if provider:
            emoji_map = {
                "claude": msg.EMOJI.CLAUDE,
                "gemini": msg.EMOJI.GEMINI,
                "ai": msg.EMOJI.AI
            }
            emoji = emoji_map.get(provider, "")
            text = f"{emoji} {text}"

        self._status.update(text)
