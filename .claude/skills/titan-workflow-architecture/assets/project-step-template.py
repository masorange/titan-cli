from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def example_step(ctx: WorkflowContext) -> WorkflowResult:
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Example Step")

    try:
        value = ctx.get("value")
        ctx.textual.end_step("success")
        return Success("Step completed", metadata={"value": value})
    except Exception as exc:
        ctx.textual.end_step("error")
        return Error(str(exc), exception=exc)
