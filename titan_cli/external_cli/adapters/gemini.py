"""
Headless adapter for Gemini CLI (gemini).

Gemini CLI does not have an official non-interactive flag as of 2026-03.
This adapter closes stdin to signal non-interactive mode and passes the
prompt via -i. Update the command construction here when Gemini adds
an official --print / --headless flag.
"""

import re
import shutil
import subprocess
from typing import Optional

from .base import HeadlessResponse, SupportedCLI

_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class GeminiHeadlessAdapter:
    """
    Runs Gemini CLI in headless mode.

    Passes the prompt via `-i <prompt>` and closes stdin so the CLI
    does not wait for interactive input.
    """

    @property
    def cli_name(self) -> SupportedCLI:
        return SupportedCLI.GEMINI

    def is_available(self) -> bool:
        return shutil.which("gemini") is not None

    def execute(
        self,
        prompt: str,
        cwd: Optional[str] = None,
        timeout: int = 60,
    ) -> HeadlessResponse:
        cmd = ["gemini", "-i", prompt]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                cwd=cwd,
                timeout=timeout,
            )
            return HeadlessResponse(
                stdout=self._sanitize(result.stdout),
                stderr=result.stderr.strip(),
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return HeadlessResponse(
                stdout="",
                stderr=f"Gemini CLI timed out after {timeout}s",
                exit_code=124,
            )
        except FileNotFoundError:
            return HeadlessResponse(
                stdout="",
                stderr="gemini command not found",
                exit_code=127,
            )

    def _sanitize(self, text: str) -> str:
        """Strip ANSI escape codes and trailing whitespace."""
        return _ANSI_ESCAPE.sub("", text).strip()
