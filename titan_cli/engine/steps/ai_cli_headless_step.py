"""
AI CLI Headless Step

Generic step that runs a CLI AI assistant (Claude, Gemini, …) in headless
mode and stores the raw output in ctx.data for subsequent steps to consume.

Unlike ai_assistant_step, this step does NOT suspend the TUI or hand control
to an interactive session. It captures stdout/stderr and stores them under
configurable keys in ctx.data.

Typical usage — run AI analysis and pass the result to a parsing step:

    - id: ai-review
      plugin: core
      step: ai_cli_headless
      params:
        context_key: pr_context
        prompt_template: "Review this PR:\n{context}"
        cli_preference: auto
        timeout: 90
        output_key: review
      on_error: fail
"""

import json

from titan_cli.core.workflows.models import WorkflowStepModel
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Error, Skip, Success, WorkflowResult
from titan_cli.external_cli.adapters import HEADLESS_ADAPTER_REGISTRY, get_headless_adapter
from titan_cli.external_cli.adapters.base import SupportedCLI
from titan_cli.messages import msg

_VALID_CLI_PREFERENCES = {"auto"} | set(SupportedCLI)


def execute_ai_cli_headless_step(step: WorkflowStepModel, ctx: WorkflowContext) -> WorkflowResult:
    """
    Run a CLI AI assistant in headless mode.

    Parameters (in step.params):
        context_key (str, required):
            Key in ctx.data whose value is used as the {context} in the prompt.
        prompt_template (str, default "{context}"):
            Template string. Use {context} as the placeholder for context_key data.
        cli_preference (str, default "auto"):
            "auto" tries registered CLIs in order and uses the first available one.
            Any SupportedCLI value (e.g. "claude", "gemini") pins to that CLI.
        timeout (int, default 60):
            Seconds before the subprocess is killed.
        output_key (str, default "ai_cli"):
            Prefix for the keys written to ctx.data:
              <output_key>_stdout   — sanitized stdout
              <output_key>_stderr   — stderr
              <output_key>_exit_code — integer exit code
    """
    step_name = step.name or "AI CLI Headless"

    if ctx.textual:
        ctx.textual.begin_step(step_name)

    # ── params ──────────────────────────────────────────────────────────────
    context_key = step.params.get("context_key")
    prompt_template = step.params.get("prompt_template", "{context}")
    cli_preference = step.params.get("cli_preference", "auto")
    timeout = int(step.params.get("timeout", 60))
    output_key = step.params.get("output_key", "ai_cli")

    # ── validate cli_preference ─────────────────────────────────────────────
    if cli_preference not in _VALID_CLI_PREFERENCES:
        error_msg = msg.AICLIHeadless.UNKNOWN_CLI.format(
            cli_name=cli_preference,
            valid=", ".join(sorted(_VALID_CLI_PREFERENCES)),
        )
        return _fail(ctx, error_msg)

    # ── validate context_key ────────────────────────────────────────────────
    if not context_key:
        return _fail(ctx, msg.AICLIHeadless.CONTEXT_KEY_REQUIRED)

    context_data = ctx.data.get(context_key)
    if not context_data:
        skip_msg = msg.AICLIHeadless.NO_DATA_IN_CONTEXT.format(context_key=context_key)
        if ctx.textual:
            ctx.textual.dim_text(skip_msg)
            ctx.textual.end_step("skip")
        return Skip(skip_msg)

    # ── build prompt ────────────────────────────────────────────────────────
    try:
        context_str = context_data if isinstance(context_data, str) else json.dumps(context_data, indent=2)
        prompt = prompt_template.format(context=context_str)
    except KeyError as e:
        return _fail(ctx, msg.AICLIHeadless.INVALID_PROMPT_TEMPLATE.format(e=e))
    except Exception as e:
        return _fail(ctx, msg.AICLIHeadless.FAILED_TO_BUILD_PROMPT.format(e=e))

    # ── resolve adapter ─────────────────────────────────────────────────────
    adapter = None

    if cli_preference == "auto":
        for cli_name in HEADLESS_ADAPTER_REGISTRY:
            candidate = get_headless_adapter(cli_name)
            if candidate.is_available():
                adapter = candidate
                break
    else:
        try:
            candidate = get_headless_adapter(cli_preference)
        except ValueError as e:
            return _fail(ctx, str(e))

        if not candidate.is_available():
            return _fail(ctx, msg.AICLIHeadless.CLI_NOT_AVAILABLE.format(cli_name=cli_preference))

        adapter = candidate

    if adapter is None:
        return _fail(ctx, msg.AICLIHeadless.NO_ADAPTER_AVAILABLE)

    # ── execute ─────────────────────────────────────────────────────────────
    cli_display = adapter.cli_name.value.capitalize()

    if ctx.textual:
        ctx.textual.dim_text(msg.AICLIHeadless.RUNNING.format(cli_name=cli_display))

    project_root = ctx.get("project_root", None)
    response = adapter.execute(prompt, cwd=project_root, timeout=timeout)

    # ── store results in ctx.data ───────────────────────────────────────────
    ctx.data[f"{output_key}_stdout"] = response.stdout
    ctx.data[f"{output_key}_stderr"] = response.stderr
    ctx.data[f"{output_key}_exit_code"] = response.exit_code

    # ── handle failure ──────────────────────────────────────────────────────
    if not response.succeeded:
        error_msg = msg.AICLIHeadless.FAILED.format(
            cli_name=cli_display,
            exit_code=response.exit_code,
        )
        if ctx.textual:
            ctx.textual.error_text(error_msg)
            if response.stderr:
                ctx.textual.dim_text(response.stderr)
            ctx.textual.end_step("error")
        return Error(error_msg)

    success_msg = msg.AICLIHeadless.COMPLETED.format(cli_name=cli_display)
    if ctx.textual:
        ctx.textual.success_text(success_msg)
        ctx.textual.end_step("success")

    return Success(success_msg, metadata={f"{output_key}_exit_code": response.exit_code})


# ── helpers ──────────────────────────────────────────────────────────────────

def _fail(ctx: WorkflowContext, message: str) -> Error:
    if ctx.textual:
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
    return Error(message)
