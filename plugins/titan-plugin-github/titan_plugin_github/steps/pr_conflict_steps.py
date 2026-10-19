"""
Resolving the conflicts of one of your own pull requests.

GitHub only says *that* a PR conflicts, never with what, so the files are read
from git itself. The merge, the interactive AI session and the push all come
from `plugin:git/merge-branch`, which this step only prepares.
"""
from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Exit, Success, WorkflowContext, WorkflowResult
from titan_cli.ui.tui.widgets import OptionItem

from ..operations import build_pr_selection_title


def select_conflicted_pr(ctx: WorkflowContext) -> WorkflowResult:
    """
    Choose the PR whose conflicts to resolve, and list the files that clash.

    Inputs (from ctx.data):
        conflict_pr_number (int, optional): PR to work on; asked for when absent
        remote (str, optional): Remote name (default: "origin")

    Outputs (saved to ctx.data):
        selected_pr_number (int): The chosen PR
        selected_pr_title (str): Its title
        selected_pr_head_branch (str): Its branch, the one that gets checked out
        selected_pr_base_branch (str): The branch it targets, which the workflow
            hands to merge-branch as its source_branch
        conflicted_files (list[str]): Paths that conflict, empty when unknown

    Returns:
        Success: PR chosen and ready to merge into
        Exit: Nothing of yours is in conflict, or the user cancelled
        Error: The PR could not be read
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Select PR with Conflicts")

    if not ctx.github:
        ctx.textual.end_step("error")
        return Error("GitHub client not available")

    with ctx.textual.loading("Fetching your open PRs..."):
        result = ctx.github.list_my_prs(state="open")

    match result:
        case ClientSuccess(data=prs):
            pass
        case ClientError(error_message=err):
            ctx.textual.error_text(err)
            ctx.textual.end_step("error")
            return Error(f"Failed to fetch your PRs: {err}")

    requested = ctx.get("conflict_pr_number")
    if requested:
        pr = next((p for p in prs if p.number == int(requested)), None)
        if pr is None:
            ctx.textual.end_step("error")
            return Error(f"PR #{requested} is not one of your open PRs")
    else:
        conflicted = [p for p in prs if p.has_conflicts]
        if not conflicted:
            ctx.textual.success_text("None of your open PRs is in conflict")
            ctx.textual.end_step("success")
            return Exit("No PR of yours is in conflict")

        selected = ctx.textual.ask_option(
            f"Which PR do you want to un-conflict ({len(conflicted)} in conflict)?",
            [OptionItem(value=p.number, title=build_pr_selection_title(p),
                        description=f"{p.head_ref} → {p.base_ref}") for p in conflicted],
        )
        if not selected:
            ctx.textual.warning_text("No PR selected")
            ctx.textual.end_step("skip")
            return Exit("User cancelled PR selection")
        pr = next(p for p in conflicted if p.number == selected)

    ctx.textual.bold_text(f"#{pr.number} {pr.title}")
    ctx.textual.dim_text(f"{pr.head_ref} → {pr.base_ref}")

    conflicted_files = _show_conflicting_files(ctx, pr)

    ctx.textual.end_step("success")
    return Success(
        f"Resolving conflicts of #{pr.number}",
        metadata={
            "selected_pr_number": pr.number,
            "selected_pr_title": pr.title,
            "selected_pr_head_branch": pr.head_ref,
            "selected_pr_base_branch": pr.base_ref,
            "conflicted_files": conflicted_files,
        },
    )


def _show_conflicting_files(ctx: WorkflowContext, pr) -> list:
    """List what would clash, read from git without touching the working tree."""
    if not ctx.git:
        return []

    remote = ctx.get("remote", "origin")
    with ctx.textual.loading("Reading the conflicts..."):
        for branch in (pr.base_ref, pr.head_ref):
            ctx.git.fetch(remote=remote, branch=branch)
        conflicts_result = ctx.git.list_merge_conflicts(f"{remote}/{pr.base_ref}", f"{remote}/{pr.head_ref}")

    match conflicts_result:
        case ClientSuccess(data=files) if files:
            ctx.textual.warning_text(f"{len(files)} file(s) conflict with {pr.base_ref}:")
            for path in files:
                ctx.textual.text(f"  {path}")
            return files
        case ClientSuccess():
            # GitHub can lag behind a branch that was already fixed.
            ctx.textual.success_text(f"Nothing conflicts with {pr.base_ref} any more")
            return []
        case ClientError(error_message=err):
            ctx.textual.dim_text(f"Could not list the conflicts: {err}")
            return []
