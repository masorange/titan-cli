"""
Headless adapter for Codex CLI.

Uses `codex exec --json -` with stdin for non-interactive execution.
Parses JSONL output to extract the agent's response.
"""

import json
import re
import shutil
import subprocess
from typing import Optional

from .base import HeadlessResponse, SupportedCLI

_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class CodexHeadlessAdapter:
    """
    Runs Codex CLI in headless mode via `codex exec --json --ephemeral <prompt>`.

    Uses flags for non-interactive execution:
    - --json: machine-readable JSONL output
    - --ephemeral: don't save session files to disk
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
        # Use flags for non-interactive headless execution:
        # - --json: machine-readable JSONL output
        # - --ephemeral: don't save session to disk
        cmd = ["codex", "exec", "--json", "--ephemeral", prompt]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
            )
            return HeadlessResponse(
                stdout=self._parse_json_output(result.stdout),
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

    def _parse_json_output(self, jsonl_output: str) -> str:
        """
        Parse JSONL output from `codex exec --json --ephemeral`.

        Extracts the agent's response from JSON events.
        Looks for: item.completed events with type="agent_message".
        """
        if not jsonl_output or not jsonl_output.strip():
            return ""

        agent_messages = []
        for line in jsonl_output.strip().split("\n"):
            if not line:
                continue
            try:
                event = json.loads(line)

                # Extract from item.completed events with agent_message type
                if event.get("type") == "item.completed":
                    item = event.get("item", {})
                    if item.get("type") == "agent_message":
                        text = item.get("text", "")
                        if text:
                            agent_messages.append(text)

            except json.JSONDecodeError:
                # Skip unparseable lines
                continue

        return "\n".join(agent_messages).strip()
