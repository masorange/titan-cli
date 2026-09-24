"""
Headless adapter for Antigravity CLI (agy).

Uses `agy --input-format stream-json --output-format stream-json` with the prompt on
stdin for non-interactive execution, plus `--json-schema` when a structured response is
required.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from .base import (
    CliModel,
    CliUsage,
    HeadlessResponse,
    SupportedCLI,
    _as_int,
    model_listing_lines,
)

_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

_SETTINGS_PATH = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"

_HEADLESS_PREAMBLE = (
    "Headless session constraints: shell commands, terminal tools, and file edits are "
    "unavailable here — any attempt is silently denied and ends the run without an "
    "answer. Do not run git or any other command. Work only with file reading, "
    "directory listing, and code search tools, and always finish by writing the final "
    "answer to the request.\n\n"
)
"""Prepended to every prompt because agy cannot be told which tools its session lacks.

Unlike Claude's --disallowedTools there is no flag that removes tools from the model's
view, so the model plans command runs, gets auto-denied, and terminates with narration
but no answer (observed live: review batches ended exactly at "I will run git status").
Telling it up front is the only available lever.
"""

_READ_ONLY_PERMISSIONS = ["read_file(*)"]
"""Allow-rules provisioned into agy's settings so headless runs can read the repo.

One rule covers all read-shaped work: agy gates listing, code search, and file
reads behind the single "read_file" permission (verified live — with only this
rule, list/search/read tools all run), and it prunes rule names it does not
recognize from the file on exit, so provisioning anything else would just be
re-added and re-pruned on every run. Read-only on purpose: write and command
tools stay unlisted, so agy keeps auto-denying them (or containing them to its
scratch sandbox) while unattended.
"""


class AntigravityHeadlessAdapter:
    """
    Runs Antigravity CLI in headless mode via `agy [flags] --print <prompt>`.

    `--print` runs a single prompt non-interactively and writes the response
    to stdout. With `--output-format json --json-schema <schema>`, agy returns
    a JSON envelope whose `structured_output` field is the schema-validated
    answer.
    """

    @property
    def cli_name(self) -> SupportedCLI:
        return SupportedCLI.ANTIGRAVITY

    @property
    def supports_structured_output(self) -> bool:
        return True

    @property
    def supports_tool_restriction(self) -> bool:
        # agy has no per-invocation tool denylist flag. Headless runs are
        # still contained: tools needing a permission it cannot prompt for
        # are auto-denied unless allowed in its own settings.
        return False

    @property
    def supports_effort_control(self) -> bool:
        return True

    @property
    def supports_model_selection(self) -> bool:
        return True

    def is_available(self) -> bool:
        return shutil.which("agy") is not None

    def list_models(self) -> list[CliModel]:
        """`agy models` prints `id<TAB>Human label` per model.

        Lines without a tab are progress chatter, not models, so they are dropped.
        """
        models: list[CliModel] = []
        for line in model_listing_lines(["agy", "models"]):
            if "\t" not in line:
                continue
            identifier, _, label = line.partition("\t")
            models.append(CliModel(identifier.strip(), label.strip()))
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
        self._ensure_read_permissions()
        # stream-json on both sides, on EVERY call. Input: agy's text mode only takes the
        # prompt as the `--print` argument, and Linux caps one argv string at 131,072
        # bytes (MAX_ARG_STRLEN) -- a deep-review prompt runs ~115k characters and fails
        # with E2BIG once it carries non-ASCII text. stream-json reads it from stdin
        # instead. Output: its final `result` event is the same envelope `--output-format
        # json` prints (response, structured_output, status, usage), and the envelope is
        # the only place agy reports `usage`. Verified live 2026-09-24.
        cmd = ["agy", "--input-format", "stream-json", "--output-format", "stream-json"]
        if json_schema is not None:
            cmd += ["--json-schema", json.dumps(json_schema)]
        if effort is not None:
            cmd += ["--effort", effort]
        if model is not None:
            cmd += ["--model", model]
        stream_input = json.dumps(
            {"event": "user", "message": {"content": _HEADLESS_PREAMBLE + prompt}}
        )
        try:
            result = subprocess.run(
                cmd,
                input=stream_input + "\n",
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return HeadlessResponse(
                stdout="",
                stderr=f"Antigravity CLI timed out after {timeout}s",
                exit_code=124,
            )
        except FileNotFoundError:
            return HeadlessResponse(
                stdout="",
                stderr="agy command not found",
                exit_code=127,
            )

        return self._parse_envelope(result, expect_structured=json_schema is not None)

    def _ensure_read_permissions(self) -> None:
        """Provision read-only allow-rules into agy's settings before each run.

        Headless agy auto-denies any tool that would need an interactive permission
        prompt — read_file included, and reading the repo is the reason a CLI is worth
        routing to at all. Its only unattended-safe switch is `permissions.allow` in its
        settings file (the alternative, --dangerously-skip-permissions, would also
        approve shell and writes). Idempotent: existing rules and unrelated settings are
        preserved, and nothing is written when the rules are already there. Best-effort:
        an unreadable or malformed file is left alone — the run then surfaces agy's own
        permission-denial message instead of this method guessing at repairs.
        """
        try:
            settings: dict[str, Any] = {}
            if _SETTINGS_PATH.exists():
                loaded = json.loads(_SETTINGS_PATH.read_text())
                if not isinstance(loaded, dict):
                    return
                settings = loaded

            permissions = settings.get("permissions")
            if not isinstance(permissions, dict):
                permissions = {}
                settings["permissions"] = permissions
            allow = permissions.get("allow")
            if not isinstance(allow, list):
                allow = []
                permissions["allow"] = allow

            missing = [rule for rule in _READ_ONLY_PERMISSIONS if rule not in allow]
            if not missing:
                return

            allow.extend(missing)
            _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            _SETTINGS_PATH.write_text(json.dumps(settings, indent=2) + "\n")
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return

    def _parse_envelope(
        self, result: subprocess.CompletedProcess, *, expect_structured: bool
    ) -> HeadlessResponse:
        """Unwrap the result envelope, which every call now receives.

        With a schema the validated answer is under `structured_output` and becomes
        stdout as compact JSON so downstream parsing sees no surrounding prose; it falls
        back to the envelope's `response` text when no structured output was produced.
        Without a schema, `response` IS the answer.

        The envelope is also the only place agy reports `usage`, so it is read even on
        the error path - a failed turn still consumed tokens.
        """
        stderr = result.stderr.strip()
        envelope = _result_envelope(result.stdout)

        if not isinstance(envelope, dict):
            # An agy old enough not to emit an envelope, or a failure that printed
            # prose. Whatever reached stdout is still the answer; `usage=None` says
            # honestly that nothing was reported.
            return HeadlessResponse(
                stdout=self._sanitize(result.stdout), stderr=stderr, exit_code=result.returncode
            )

        usage = self._usage_from_envelope(envelope)

        if envelope.get("status") not in (None, "SUCCESS"):
            # The envelope's `response` may be empty on hard failures (e.g. quota
            # exhaustion), where the cause lives in an error-ish field instead. Surface
            # whatever the envelope carries before falling back to a generic message.
            detail = (
                envelope.get("error")
                or envelope.get("error_message")
                or envelope.get("response")
                or stderr
                or f"Antigravity CLI reported an error (status: {envelope.get('status')})"
            )
            return HeadlessResponse(
                stdout="",
                stderr=str(detail),
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
            stdout=self._sanitize(str(envelope.get("response", ""))),
            stderr=stderr,
            exit_code=result.returncode,
            usage=usage,
        )

    def _usage_from_envelope(self, envelope: dict) -> Optional[CliUsage]:
        """Read the envelope's `usage` block.

        agy reports counts but no price, so `cost_usd` stays None rather than being
        derived from a token table that would go stale without anyone noticing. Its
        `thinking_tokens` maps to `reasoning_tokens`, the name the other CLIs use for
        the same thing.
        """
        usage = envelope.get("usage")
        if not isinstance(usage, dict):
            return None
        return CliUsage(
            input_tokens=_as_int(usage.get("input_tokens")),
            output_tokens=_as_int(usage.get("output_tokens")),
            cache_read_tokens=_as_int(usage.get("cache_read_tokens")),
            reasoning_tokens=_as_int(usage.get("thinking_tokens")),
            reported_total_tokens=_as_int(usage.get("total_tokens")),
            source="agy_envelope",
        )

    def _sanitize(self, text: str) -> str:
        """Strip ANSI escape codes and trailing whitespace."""
        return _ANSI_ESCAPE.sub("", text).strip()


def _result_envelope(stdout: str) -> Optional[dict]:
    """The envelope from agy's output: the `result` event of a stream, or a JSON object.

    A stream is one event per line and the envelope is the payload of the LAST `result`
    event. A whole-stdout JSON object is what `--output-format json` prints, accepted too
    so a run captured in that format still parses.
    """
    try:
        whole = json.loads(stdout)
    except json.JSONDecodeError:
        whole = None
    if isinstance(whole, dict):
        if whole.get("event") == "result" and isinstance(whole.get("result"), dict):
            return whole["result"]
        return whole

    envelope = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("event") == "result" and isinstance(event.get("result"), dict):
            envelope = event["result"]
    return envelope
