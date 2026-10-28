from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult


def example_step(ctx: WorkflowContext) -> WorkflowResult:
    # Function name == the YAML `step:` value (no `_step` suffix for project steps).
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Example Step")

    client = ctx.get("example_client")
    with ctx.textual.loading("Fetching items..."):
        result = client.fetch_items()

    match result:
        case ClientSuccess(data=items):
            ctx.textual.success_text(f"{len(items)} items")
            ctx.textual.end_step("success")
            # Outputs go in metadata; the executor merges them into ctx.data.
            return Success("Items fetched", metadata={"items": items})
        case ClientError(error_message=err):
            ctx.textual.error_text(err)
            ctx.textual.end_step("error")
            return Error(err)
