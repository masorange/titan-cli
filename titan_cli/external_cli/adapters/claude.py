"""
Headless adapter for Claude CLI (claude).

Uses `claude --print <prompt>` for non-interactive execution.
"""

import json
import re
import shutil
import subprocess
from typing import Any, Optional

from .base import CliModel, HeadlessResponse, SupportedCLI, usage_from_result_envelope

_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class ClaudeHeadlessAdapter:
    """
    Runs Claude CLI in headless mode via `claude --print <prompt>`.

    The --print flag makes Claude write the response to stdout
    and exit immediately, without starting an interactive session.
    """

    @property
    def cli_name(self) -> SupportedCLI:
        return SupportedCLI.CLAUDE

    @property
    def supports_structured_output(self) -> bool:
        return True

    @property
    def supports_tool_restriction(self) -> bool:
        return True

    @property
    def supports_effort_control(self) -> bool:
        return True

    @property
    def supports_model_selection(self) -> bool:
        return True

    def is_available(self) -> bool:
        return shutil.which("claude") is not None

    def list_models(self) -> list[CliModel]:
        """Claude has no listing subcommand; its own --help publishes the aliases.

        Aliases rather than versioned ids on purpose: `claude --help` documents them as
        "an alias for the latest model", so they keep pointing at the current release
        instead of pinning whatever was current when this adapter was written. A full
        name still works - the caller can always type one.
        """
        return [
            CliModel("opus", "Opus - most capable"),
            CliModel("sonnet", "Sonnet - balanced"),
            CliModel("haiku", "Haiku - fastest"),
            CliModel("fable", "Fable"),
        ]

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
        # --output-format json on EVERY call, not just the structured ones. The envelope
        # is the only place claude reports `usage` and `total_cost_usd`, and it also names
        # the model that actually ran (`modelUsage`) — so asking for it only when a schema
        # is passed left every plain-text call with no cost figure at all. Verified
        # 2026-09-22 that the envelope is emitted without `--json-schema`.
        cmd = ["claude", "--print", "--output-format", "json"]
        if json_schema is not None:
            cmd += ["--json-schema", json.dumps(json_schema)]
        if disallowed_tools:
            # --disallowedTools is a variadic flag with no natural terminator: passed as
            # separate argv tokens, it keeps consuming words until the next recognized flag,
            # swallowing the trailing prompt argument as if it were another tool name. A
            # single comma-joined token avoids that ambiguity.
            cmd += [f"--disallowedTools={','.join(disallowed_tools)}"]
        if effort is not None:
            cmd += ["--effort", effort]
        if model is not None:
            cmd += ["--model", model]
        cmd.append(prompt)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return HeadlessResponse(
                stdout="",
                stderr=f"Claude CLI timed out after {timeout}s",
                exit_code=124,
            )
        except FileNotFoundError:
            return HeadlessResponse(
                stdout="",
                stderr="claude command not found",
                exit_code=127,
            )

        return self._parse_envelope(result, expect_structured=json_schema is not None)

    def _parse_envelope(
        self, result: subprocess.CompletedProcess, *, expect_structured: bool
    ) -> HeadlessResponse:
        """Unwrap the `--output-format json` envelope, which every call now receives.

        With a schema, the model's validated answer is under `structured_output` and
        becomes stdout as compact JSON so downstream parsing sees no surrounding prose;
        it falls back to the envelope's `result` text when the model didn't call the
        structured-output tool (e.g. it judged the request ambiguous). Without a schema,
        `result` IS the answer.

        Either way the envelope is also where `usage`, `total_cost_usd` and the model
        that actually ran are reported, so it is read even on the error path — a call
        that failed still cost money, and hiding that would understate every review
        that had a retry in it.
        """
        stderr = result.stderr.strip()
        try:
            envelope = json.loads(result.stdout)
        except json.JSONDecodeError:
            envelope = None

        if not isinstance(envelope, dict):
            # A claude old enough not to emit an envelope, or a failure that printed
            # prose instead of JSON. Whatever reached stdout is still the answer; there
            # is simply no usage to report, which `usage=None` says honestly.
            return HeadlessResponse(
                stdout=self._sanitize(result.stdout), stderr=stderr, exit_code=result.returncode
            )

        usage = usage_from_result_envelope(envelope, source="claude_result_envelope")

        if envelope.get("is_error"):
            return HeadlessResponse(
                stdout="",
                stderr=str(envelope.get("result") or stderr or "Claude CLI reported an error"),
                exit_code=result.returncode or 1,
                usage=usage,
            )

        if expect_structured:
            structured_output = envelope.get("structured_output")
            if structured_output is not None:
                return HeadlessResponse(
                    stdout=json.dumps(structured_output),
                    stderr=stderr,
                    exit_code=result.returncode,
                    usage=usage,
                )

        return HeadlessResponse(
            stdout=self._sanitize(str(envelope.get("result", ""))),
            stderr=stderr,
            exit_code=result.returncode,
            usage=usage,
        )

    def _sanitize(self, text: str) -> str:
        """Strip ANSI escape codes and trailing whitespace."""
        return _ANSI_ESCAPE.sub("", text).strip()
