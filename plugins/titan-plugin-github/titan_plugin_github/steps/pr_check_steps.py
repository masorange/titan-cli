"""
Fixing the failing checks of one of your own pull requests.

The pane can already say *why* a check failed; this is the other half: the
failing jobs' logs become the opening prompt of an interactive AI session held
on the PR's branch. Cutting a log down to what an AI can read is
`ci_diagnosis_operations`' job, the same code the diagnosis uses.
"""
from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Exit, Success, WorkflowContext, WorkflowResult
from titan_cli.ui.tui.widgets import OptionItem

from ..operations import build_check_fix_prompt, build_pr_selection_title, extract_failure_excerpt


def select_failing_pr(ctx: WorkflowContext) -> WorkflowResult:
    """
    Choose the PR whose checks to fix and build the session's opening prompt.

    Inputs (from ctx.data):
        fix_pr_number (int, optional): PR to work on; asked for when absent
        check_diagnosis (str, optional): What the pane already worked out, passed on to the CLI
        max_jobs (int, optional): How many failed jobs' logs to read (default: 3)

    Outputs (saved to ctx.data):
        selected_pr_number (int): The chosen PR
        selected_pr_title (str): Its title
        selected_pr_head_branch (str): Its branch, the one that gets checked out
        selected_pr_base_branch (str): The branch it targets
        check_fix_context (str): The prompt for the interactive AI session

    Returns:
        Success: PR chosen and the prompt built
        Exit: Nothing of yours is failing, or the user cancelled
        Error: The PR or its logs could not be read
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Select PR with Failing Checks")

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

    requested = ctx.get("fix_pr_number")
    if requested:
        pr = next((p for p in prs if p.number == int(requested)), None)
        if pr is None:
            ctx.textual.end_step("error")
            return Error(f"PR #{requested} is not one of your open PRs")
    else:
        failing = [p for p in prs if p.checks_state == "failing"]
        if not failing:
            ctx.textual.success_text("None of your open PRs has a failing check")
            ctx.textual.end_step("success")
            return Exit("No PR of yours is failing")

        selected = ctx.textual.ask_option(
            f"Which PR do you want to fix ({len(failing)} failing)?",
            [OptionItem(value=p.number, title=build_pr_selection_title(p),
                        description=f"{len(p.failed_checks)} failed check(s) on {p.head_ref}")
             for p in failing],
        )
        if not selected:
            ctx.textual.warning_text("No PR selected")
            ctx.textual.end_step("skip")
            return Exit("User cancelled PR selection")
        pr = next(p for p in failing if p.number == selected)

    ctx.textual.bold_text(f"#{pr.number} {pr.title}")

    if not pr.failed_checks:
        ctx.textual.success_text("Its checks are green now")
        ctx.textual.end_step("success")
        return Exit(f"PR #{pr.number} has no failing check")

    failures = _read_failed_logs(ctx, pr)
    prompt = build_check_fix_prompt(
        pr.number, pr.title, pr.head_ref, failures, diagnosis=str(ctx.get("check_diagnosis") or "")
    )

    ctx.textual.end_step("success")
    return Success(
        f"Fixing the checks of #{pr.number}",
        metadata={
            "selected_pr_number": pr.number,
            "selected_pr_title": pr.title,
            "selected_pr_head_branch": pr.head_ref,
            "selected_pr_base_branch": pr.base_ref,
            "check_fix_context": prompt,
        },
    )


def _read_failed_logs(ctx: WorkflowContext, pr) -> list:
    """The (job name, failure excerpt) of each failed check, as far as its log can be read."""
    max_jobs = int(ctx.get("max_jobs", 3) or 3)
    failures = []
    for check in pr.failed_checks[:max_jobs]:
        ctx.textual.text(f"  ✗ {check.name}")
        if check.job_id is None:
            # External CI: its log lives outside GitHub, so only the name is known.
            failures.append((check.name, "(not a GitHub Actions job: its log is outside GitHub)"))
            continue
        with ctx.textual.loading(f"Reading the log of {check.name}..."):
            log_result = ctx.github.get_actions_job_log(check.job_id)
        match log_result:
            case ClientSuccess(data=log):
                failures.append((check.name, extract_failure_excerpt(log)))
            case ClientError(error_message=err):
                ctx.textual.dim_text(f"    could not read its log: {err}")
                failures.append((check.name, f"(its log could not be read: {err})"))

    left = len(pr.failed_checks) - len(failures)
    if left > 0:
        ctx.textual.dim_text(f"  …and {left} more failed check(s), not read (max_jobs={max_jobs})")
    return failures
