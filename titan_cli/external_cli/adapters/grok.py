"""
Headless adapter for Grok Build CLI (grok).

Uses `grok -p <prompt> --output-format streaming-messages-json` for
non-interactive execution.
"""

import json
import re
import shutil
import subprocess
from typing import Any, Optional

from .base import HeadlessResponse, SupportedCLI

_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

_PERMISSION_MODE = "dontAsk"
"""Permission mode every headless run is pinned to.

grok's default mode is "ask", which cannot work without a TTY: the run would
stall or die on the first tool call needing approval, the exact failure already
observed live with opencode and agy. "dontAsk" denies anything that would have
prompted instead of asking, while grok's read-only tools (file read, directory
list, code search) never prompt and keep working — which is the whole reason a
CLI is worth routing to. The alternative, always-approve/bypassPermissions,
would let an unattended run edit the repo and execute commands.
"""

_DENY_RULES = {
    "Bash": "Bash(*)",
    "Edit": "Edit(**)",
    "Write": "Write(**)",
    # grok has no notebook-specific rule; notebook writes go through Edit/Write.
    "NotebookEdit": "Edit(**)",
    "WebFetch": "WebFetch(*)",
    "WebSearch": "WebSearch(*)",
}
"""Titan tool name → grok permission rule.

Tool restriction is expressed as `--deny` rules rather than `--disallowed-tools`
because the denylist flag takes grok's internal tool ids (`run_terminal_cmd` and
friends), while permission rules use the same tool names Titan already passes.
Deny beats every other rule and applies even under always-approve, so a denied
tool cannot come back through a user's own config. Unmapped names are dropped:
an unrecognized rule is skipped by grok with a warning anyway.

"Agent" is absent on purpose — subagents are switched off with `--no-subagents`.
"""

_HEADLESS_PREAMBLE = (
    "Headless session constraints: file edits, shell commands, and network access "
    "are unavailable here — any attempt is denied and the run continues without it. "
    "Work with file reading, directory listing, and code search only, and always "
    "finish by writing the final answer to the request.\n\n"
)
"""Prepended to every prompt so the model plans around the tools it cannot use.

Precautionary, following the same pattern as the opencode and agy adapters: on
both of those, a model that discovered a denial only after committing to a plan
ended the run narrating instead of answering. grok reports denials back to the
model rather than aborting, so this is cheaper insurance here, not a fix for an
observed failure.
"""


class GrokHeadlessAdapter:
    """
    Runs Grok Build CLI in headless mode via `grok -p <prompt>`.

    `-p` (`--single`) runs one prompt non-interactively and exits.
    `--output-format streaming-messages-json` emits one JSON object per line
    and closes with a `result` line carrying the final answer alone — which
    `--output-format json` does not: its `text` field is every assistant turn
    concatenated, narration included ("I'll read the adapter first." glued
    straight onto the commit message it was asked for, observed live).

    This targets xAI's official CLI (`curl -fsSL https://x.ai/cli/install.sh | bash`),
    not the unaffiliated superagent-ai/grok-cli, which installs under the same
    command name but takes different flags.
    """

    @property
    def cli_name(self) -> SupportedCLI:
        return SupportedCLI.GROK

    @property
    def supports_structured_output(self) -> bool:
        # grok has --json-schema, but it constrains the model's *first* text output
        # and ends the run there: verified live on 1.0.25, a schema'd request came
        # back as num_turns=1 with the narration coerced into the schema
        # ("summary": "Reading the adapter registry module to produce a summary…")
        # and no file ever read — with or without an explicit do-not-narrate
        # instruction. Prompt-level JSON instructions keep the agentic turns and
        # produce the real answer, so Titan uses those instead.
        return False

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
        return shutil.which("grok") is not None

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
        cmd = [
            "grok",
            # Update checks write to stderr and can pause an automated run; grok's
            # own automation guidance is to disable them on every invocation.
            # Hidden flag: accepted since 1.0.25 but absent from --help.
            "--no-auto-update",
            "--output-format",
            "streaming-messages-json",
            "--permission-mode",
            _PERMISSION_MODE,
        ]
        for rule in self._deny_rules(disallowed_tools):
            cmd += ["--deny", rule]
        if disallowed_tools and "Agent" in disallowed_tools:
            cmd.append("--no-subagents")
        if effort is not None:
            cmd += ["--effort", effort]
        if model is not None:
            cmd += ["-m", model]
        cmd += ["-p", _HEADLESS_PREAMBLE + prompt]

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
                stderr=f"Grok CLI timed out after {timeout}s",
                exit_code=124,
            )
        except FileNotFoundError:
            return HeadlessResponse(
                stdout="",
                stderr="grok command not found",
                exit_code=127,
            )

        return self._parse_stream(result)

    def _deny_rules(self, disallowed_tools: Optional[list[str]]) -> list[str]:
        """Map Titan tool names to grok deny rules, preserving order without repeats.

        NotebookEdit and Edit collapse onto the same rule, so duplicates are dropped
        rather than passed twice.
        """
        rules: list[str] = []
        for tool in disallowed_tools or []:
            rule = _DENY_RULES.get(tool)
            if rule is not None and rule not in rules:
                rules.append(rule)
        return rules

    def _parse_stream(self, result: subprocess.CompletedProcess) -> HeadlessResponse:
        """Extract the final answer from the NDJSON message stream.

        The run closes with a `result` line whose `result` field is the final
        answer on its own — the narration and tool traffic that precede it stay
        in the `assistant` lines and are dropped here.

        A failed run closes with `is_error: true` and an `errors` array, or with
        a bare `{"type": "error"}` line. grok can exit 0 on those, so the error
        flag — not the exit code — is what decides failure here.
        """
        stderr = result.stderr.strip()
        final: Optional[dict] = None
        last_assistant_text = ""

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue

            event_type = event.get("type")
            if event_type in ("result", "error"):
                final = event
            elif event_type == "assistant":
                text = self._assistant_text(event)
                if text:
                    last_assistant_text = text

        if final is None:
            # No terminal line: the process died mid-stream (killed, crashed) or a
            # future version renamed it. The last assistant message is the best
            # remaining answer; raw stdout is the last resort so the caller's
            # contract check sees real content instead of an empty success.
            return HeadlessResponse(
                stdout=last_assistant_text or self._sanitize(result.stdout),
                stderr=stderr,
                exit_code=result.returncode,
            )

        if final.get("type") == "error" or final.get("is_error"):
            errors = final.get("errors")
            detail = (
                "; ".join(str(e) for e in errors)
                if isinstance(errors, list) and errors
                else final.get("message") or final.get("result") or stderr
            )
            return HeadlessResponse(
                stdout="",
                stderr=str(detail or "Grok CLI reported an error"),
                exit_code=result.returncode or 1,
            )

        return HeadlessResponse(
            stdout=self._sanitize(str(final.get("result", "") or last_assistant_text)),
            stderr=stderr,
            exit_code=result.returncode,
        )

    def _assistant_text(self, event: dict) -> str:
        """Join the text blocks of one assistant message, ignoring thinking blocks."""
        message = event.get("message")
        if not isinstance(message, dict):
            return ""
        content = message.get("content")
        if not isinstance(content, list):
            return ""
        return "\n".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
        ).strip()

    def _sanitize(self, text: str) -> str:
        """Strip ANSI escape codes and trailing whitespace."""
        return _ANSI_ESCAPE.sub("", text).strip()
