"""
Select CLI Step

Lets the user pick which headless AI CLI (Claude, Gemini, Codex...) subsequent steps
should use. Reusable by any plugin - the choice is stored in ctx.data["cli_preference"].
"""

from titan_cli.core.workflows.models import WorkflowStepModel
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.option_item import OptionItem
from titan_cli.engine.results import Success, WorkflowResult
from titan_cli.external_cli.adapters import get_headless_adapter
from titan_cli.external_cli.configs import CLI_REGISTRY

_CLI_DESCRIPTIONS = {
    "claude": "Anthropic's Claude AI",
    "gemini": "Google's Gemini AI",
    "codex": "OpenAI's Codex",
}


def execute_select_cli_step(step: WorkflowStepModel, ctx: WorkflowContext) -> WorkflowResult:
    """
    Ask the user which AI CLI to use for headless (non-interactive) execution.

    Only CLIs with a registered, currently-available headless adapter are offered.

    Parameters (in step.params):
        question: str - Prompt shown to the user (default: "Which AI CLI do you want to use?")

    Example workflow usage:
        - id: select-cli
          plugin: core
          step: select_cli
    """
    ctx.textual.begin_step("Select AI CLI")

    question = step.params.get("question", "Which AI CLI do you want to use?")

    options = []
    for cli_name in CLI_REGISTRY:
        adapter = get_headless_adapter(cli_name)
        if adapter.is_available():
            options.append(
                OptionItem(
                    value=cli_name,
                    title=CLI_REGISTRY[cli_name].get("display_name", cli_name),
                    description=_CLI_DESCRIPTIONS.get(cli_name, ""),
                )
            )

    if not options:
        ctx.textual.warning_text("No AI CLI available.")
        ctx.textual.end_step("skip")
        return Success("No AI CLI available", metadata={"cli_preference": ""})

    try:
        choice = ctx.textual.ask_option(question, options=options)
    except KeyboardInterrupt:
        ctx.textual.end_step("skip")
        return Success("Cancelled CLI selection", metadata={"cli_preference": ""})

    if not choice:
        ctx.textual.end_step("skip")
        return Success("No CLI selected", metadata={"cli_preference": ""})

    ctx.textual.success_text(f"Using {CLI_REGISTRY[choice].get('display_name', choice)}")
    ctx.textual.end_step("success")
    return Success(f"Selected CLI: {choice}", metadata={"cli_preference": choice})


__all__ = ["execute_select_cli_step"]
