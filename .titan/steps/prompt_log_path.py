"""
Step: prompt_log_path

Ask the user for a titan log file path, defaulting to the standard location.
"""

from pathlib import Path
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error

DEFAULT_LOG_PATH = Path.home() / ".local" / "state" / "titan" / "logs" / "titan.log"


def prompt_log_path(ctx: WorkflowContext) -> WorkflowResult:
    """
    Ask user whether to use the default log path or provide a custom one.

    Outputs (saved to ctx.data):
        log_path (str): Absolute path to the log file
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Select Log File")
    ctx.textual.text("")
    ctx.textual.dim_text(f"Default log path: {DEFAULT_LOG_PATH}")
    ctx.textual.text("")

    use_default = ctx.textual.ask_confirm("Use default log path?", default=True)

    if use_default:
        log_path = DEFAULT_LOG_PATH
    else:
        path_str = ctx.textual.ask_text(
            "Enter log file path:",
            default=str(DEFAULT_LOG_PATH),
        )
        if not path_str:
            ctx.textual.error_text("No path provided")
            ctx.textual.end_step("error")
            return Error("No log path provided")
        log_path = Path(path_str.strip()).expanduser()

    if not log_path.exists():
        ctx.textual.error_text(f"Log file not found: {log_path}")
        ctx.textual.end_step("error")
        return Error(f"Log file not found: {log_path}")

    if not log_path.is_file():
        ctx.textual.error_text(f"Path is not a file: {log_path}")
        ctx.textual.end_step("error")
        return Error(f"Not a file: {log_path}")

    size_mb = log_path.stat().st_size / (1024 * 1024)
    ctx.textual.text("")
    ctx.textual.success_text(f"✓ {log_path}")
    ctx.textual.dim_text(f"  Size: {size_mb:.2f} MB")

    ctx.set("log_path", str(log_path))

    ctx.textual.end_step("success")
    return Success(f"Log file selected: {log_path.name}")
