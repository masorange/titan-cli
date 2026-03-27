"""
Headless adapter for Codex CLI.

Uses `codex exec <prompt>` for non-interactive execution.
"""

import re
import shutil
import subprocess
from typing import Optional

from .base import HeadlessResponse, SupportedCLI

_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class CodexHeadlessAdapter:
    """
    Runs Codex CLI in headless mode via `codex exec <prompt>`.

    The exec subcommand runs Codex non-interactively with the given prompt
    and exits immediately, returning the response to stdout.
    """

    @property
    def cli_name(self) -> SupportedCLI:
        return SupportedCLI.CODEX

    def is_available(self) -> bool:
        return shutil.which("codex") is not None

    def execute(
        self,
        prompt: str,
        cwd: Optional[str] = None,
        timeout: int = 60,
    ) -> HeadlessResponse:
        cmd = ["codex", "exec", prompt]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
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
                stderr=f"Codex CLI timed out after {timeout}s",
                exit_code=124,
            )
        except FileNotFoundError:
            return HeadlessResponse(
                stdout="",
                stderr="codex command not found",
                exit_code=127,
            )

    def _sanitize(self, text: str) -> str:
        """Strip ANSI escape codes and trailing whitespace."""
        return _ANSI_ESCAPE.sub("", text).strip()
