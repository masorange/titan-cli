"""
Headless adapter for Codex CLI.

Uses `codex exec --json -` with stdin for non-interactive execution.
Parses JSONL output to extract the agent's response.
"""

import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Optional

from .base import CliModel, HeadlessResponse, SupportedCLI

_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Codex fetches and etags its own model catalogue into this file. Resolved through a
# function rather than a constant so the home directory is read at call time, not at
# import time.
def codex_models_cache_path() -> Path:
    """Where Codex CLI keeps the catalogue it maintains for itself."""
    return Path.home() / ".codex" / "models_cache.json"


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

    @property
    def supports_structured_output(self) -> bool:
        return False

    @property
    def supports_tool_restriction(self) -> bool:
        return False

    @property
    def supports_effort_control(self) -> bool:
        return False

    @property
    def supports_model_selection(self) -> bool:
        return True

    def is_available(self) -> bool:
        return shutil.which("codex") is not None

    def list_models(self) -> list[CliModel]:
        """Codex's own catalogue, read from the cache it maintains.

        There is no listing subcommand - `codex --help` shows none and documents
        `-m/--model` as a free-form string - but codex fetches its catalogue into
        `~/.codex/models_cache.json` and keeps it etagged. Reading that is better than a
        list hardcoded from the published docs, which pins whatever was current when this
        adapter was written: the docs' `gpt-5.3-codex` was already absent from the install
        this was written against, whose codex offered the `gpt-5.6-*` family instead.

        `visibility` is honored: codex marks its internal models (`codex-auto-review`,
        `gpt-reserve`) as `hide`, and offering those as a choice would be wrong.

        The file is codex's private format, not a contract, so every failure - missing,
        unreadable, malformed, or an entry of an unexpected shape - degrades to offering
        nothing. That is the behaviour this adapter had before, and the modal always lets
        the user type an identifier, so a codex that has never run costs nothing.
        """
        try:
            payload = json.loads(codex_models_cache_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

        entries = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            return []

        models = []
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("visibility") != "list":
                continue
            slug = entry.get("slug")
            if not slug:
                continue
            label = entry.get("description") or entry.get("display_name") or ""
            models.append(CliModel(slug, label))
        return models

    def execute(
        self,
        prompt: str,
        cwd: Optional[str] = None,
        timeout: int = 60,
        json_schema: Optional[dict[str, Any]] = None,
        disallowed_tools: Optional[list[str]] = None,
        effort: Optional[str] = None,
        model: Optional[str] = None,
    ) -> HeadlessResponse:
        # Use flags for non-interactive headless execution:
        # - --json: machine-readable JSONL output
        # - --ephemeral: don't save session to disk
        cmd = ["codex", "exec", "--json", "--ephemeral"]
        if model is not None:
            cmd += ["-m", model]
        cmd.append(prompt)
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
