"""
Base protocol and models for headless CLI adapters.

Each CLI (Claude, Gemini, etc.) implements HeadlessCliAdapter
to abstract away CLI-specific flags and output parsing.
Titan interacts only with this generic interface.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Optional
from typing import Protocol, runtime_checkable


class SupportedCLI(StrEnum):
    """
    Enum of CLIs with a registered headless adapter.

    Values match the CLI command name and the keys in configs.CLI_REGISTRY,
    so string literals like "claude" remain compatible.
    """
    CLAUDE = "claude"
    GEMINI = "gemini"


@dataclass
class HeadlessResponse:
    """Result of a headless CLI execution."""
    stdout: str
    stderr: str
    exit_code: int

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0


@runtime_checkable
class HeadlessCliAdapter(Protocol):
    """
    Generic interface for running a CLI tool in headless (non-interactive) mode.

    Each CLI has a concrete adapter that knows:
    - Which flags to use for non-interactive execution
    - How to sanitize/parse the output
    - How to handle CLI-specific quirks

    Analogous to AIProvider in the AI layer.
    """

    @property
    def cli_name(self) -> SupportedCLI:
        """The CLI identifier."""
        ...

    def is_available(self) -> bool:
        """Return True if the CLI is installed and reachable."""
        ...

    def execute(
        self,
        prompt: str,
        cwd: Optional[str] = None,
        timeout: int = 60,
    ) -> HeadlessResponse:
        """
        Run the CLI with the given prompt in headless mode.

        Args:
            prompt: The prompt to send to the CLI.
            cwd: Working directory for the subprocess.
            timeout: Seconds before the subprocess is killed.

        Returns:
            HeadlessResponse with stdout, stderr, and exit_code.
        """
        ...
