"""
Step: select_log_source

Pick which log files to read: the whole rotation set, one file, or a path
typed by hand.
"""

from pathlib import Path
from typing import List

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ui.tui.widgets import OptionItem

from operations import (
    DEFAULT_LOG_DIR,
    chronological_paths,
    discover_log_files,
    format_file_description,
    format_file_label,
)

_ALL = "__all__"
_CUSTOM = "__custom__"


def select_log_source(ctx: WorkflowContext) -> WorkflowResult:
    """
    Choose the log files to analyze.

    Reading the rotation set as a whole is the default: the logger rotates at
    a fixed size, so a single run is regularly split between `titan.log` and
    `titan.log.1`, and reading only the current file shows half of it.

    Outputs:
        log_paths (list[str]): Log file paths, oldest first
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Select Log Files")

    files = discover_log_files(DEFAULT_LOG_DIR)

    if not files:
        ctx.textual.dim_text(f"No titan logs found in {DEFAULT_LOG_DIR}")
        paths = _ask_custom_path(ctx)
        if paths is None:
            ctx.textual.end_step("error")
            return Error("No log file provided")
        return _done(ctx, paths)

    rotated = [info for info in files if not info.is_current]
    total_mb = sum(info.size_mb for info in files)

    options: List[OptionItem] = [
        OptionItem(
            value=_ALL,
            title=f"All log files  ({len(files)} files, {total_mb:.1f} MB)",
            description=(
                "  Sessions split by rotation are stitched back together"
                if rotated
                else "  Only the current log exists right now"
            ),
        )
    ]
    options += [
        OptionItem(
            value=index,
            title=format_file_label(info),
            description=format_file_description(info),
        )
        for index, info in enumerate(files)
    ]
    options.append(
        OptionItem(
            value=_CUSTOM,
            title="Other path…",
            description="  Read a log file from somewhere else",
        )
    )

    choice = ctx.textual.ask_option("Which logs do you want to read?", options)

    if choice is None:
        ctx.textual.end_step("error")
        return Error("No log source selected")

    if choice == _ALL:
        paths = chronological_paths(files)
    elif choice == _CUSTOM:
        custom = _ask_custom_path(ctx)
        if custom is None:
            ctx.textual.end_step("error")
            return Error("No log file provided")
        paths = custom
    else:
        paths = [files[choice].path]

    return _done(ctx, paths)


def _ask_custom_path(ctx: WorkflowContext):
    raw = ctx.textual.ask_text("Enter log file path:", default="")
    if not raw:
        ctx.textual.error_text("No path provided")
        return None

    path = Path(raw.strip()).expanduser()
    if not path.exists():
        ctx.textual.error_text(f"Log file not found: {path}")
        return None
    if not path.is_file():
        ctx.textual.error_text(f"Path is not a file: {path}")
        return None
    return [path]


def _done(ctx: WorkflowContext, paths: List[Path]) -> WorkflowResult:
    for path in paths:
        size_mb = path.stat().st_size / (1024 * 1024)
        ctx.textual.dim_text(f"  {path.name}  ({size_mb:.1f} MB)")

    ctx.textual.success_text(
        f"✓ {len(paths)} log file{'s' if len(paths) != 1 else ''} selected"
    )
    ctx.textual.end_step("success")
    return Success(
        f"{len(paths)} log file(s) selected",
        metadata={"log_paths": [str(path) for path in paths]},
    )
