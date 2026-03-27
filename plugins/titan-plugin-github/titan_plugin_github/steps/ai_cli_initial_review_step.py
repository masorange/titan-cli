"""
AI CLI Initial Review Step

Runs an initial AI analysis of a PR using a headless CLI (Claude/Gemini).
Builds the prompt from PR data in ctx.data, executes the adapter, parses
the markdown findings and stores them for subsequent steps.

ctx.data reads (configurable via workflow params):
    selected_pr       (UIPullRequest)      — the PR to analyse
    pr_diff           (str)                — full unified diff
    review_threads    (List[UICommentThread]) — existing comment threads

ctx.data writes:
    initial_review_suggestions  (List[UIReviewSuggestion])
    initial_review_markdown     (str)

YAML usage:
    - plugin: github
      step: ai_cli_initial_review
      params:
        pr_key: selected_pr
        diff_key: pr_diff
        threads_key: review_threads
        output_key: initial_review
        cli_preference: auto
        timeout: 120
"""

from rich.markup import escape as escape_markup

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from titan_cli.external_cli.adapters import HEADLESS_ADAPTER_REGISTRY, get_headless_adapter
from titan_cli.external_cli.adapters.base import SupportedCLI
from titan_cli.messages import msg

from ..operations.ai_review_operations import (
    build_initial_review_prompt_headless,
    parse_cli_review_output,
)

_VALID_CLI_PREFERENCES = {"auto"} | set(SupportedCLI)


def ai_cli_initial_review(ctx: WorkflowContext) -> WorkflowResult:
    """
    Run an initial AI analysis of a PR and store findings in ctx.data.

    Reads params from ctx.data (injected by the workflow engine from step params):
        pr_key (str, default "selected_pr")
        diff_key (str, default "pr_diff")
        threads_key (str, default "review_threads")
        output_key (str, default "initial_review")
        cli_preference (str, default "auto")
        timeout (int, default 120)
    """
    ctx.textual.begin_step("AI Initial Review")

    # ── params ──────────────────────────────────────────────────────────────
    pr_key = ctx.data.get("pr_key", "selected_pr")
    diff_key = ctx.data.get("diff_key", "pr_diff")
    threads_key = ctx.data.get("threads_key", "review_threads")
    output_key = ctx.data.get("output_key", "initial_review")
    cli_preference = ctx.data.get("cli_preference", "auto")
    timeout = int(ctx.data.get("timeout", 120))

    # ── validate cli_preference ─────────────────────────────────────────────
    if cli_preference not in _VALID_CLI_PREFERENCES:
        return _fail(ctx, msg.AICLIHeadless.UNKNOWN_CLI.format(
            cli_name=cli_preference,
            valid=", ".join(sorted(_VALID_CLI_PREFERENCES)),
        ))

    # ── read ctx.data ───────────────────────────────────────────────────────
    pr = ctx.data.get(pr_key)
    diff = ctx.data.get(diff_key, "")
    threads = ctx.data.get(threads_key, [])

    if not pr:
        skip_msg = msg.AIInitialReview.NO_PR_IN_CONTEXT.format(key=pr_key)
        ctx.textual.dim_text(skip_msg)
        ctx.textual.end_step("skip")
        return Skip(skip_msg)

    # ── resolve adapter ─────────────────────────────────────────────────────
    adapter = _resolve_adapter(cli_preference)
    if adapter is None:
        if cli_preference == "auto":
            return _fail(ctx, msg.AICLIHeadless.NO_ADAPTER_AVAILABLE)
        return _fail(ctx, msg.AICLIHeadless.CLI_NOT_AVAILABLE.format(cli_name=cli_preference))

    # ── build prompt ────────────────────────────────────────────────────────
    try:
        prompt = build_initial_review_prompt_headless(pr=pr, diff=diff, comments=threads)
    except Exception as e:
        return _fail(ctx, msg.AIInitialReview.PROMPT_BUILD_ERROR.format(e=e))

    # ── DEBUG: Log prompt details (temporary) ────────────────────────────────
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"HEADLESS_CLI_PROMPT_SIZE: {len(prompt)} chars (original diff: {len(diff)} chars, saved: {len(diff) - len(prompt)} chars)")
    logger.info(f"HEADLESS_CLI_PR: {pr.title if pr else 'N/A'} (PR #{pr.number})")
    logger.info(f"HEADLESS_CLI_THREADS: {len(threads)} comment threads")
    logger.info("HEADLESS_CLI_PROMPT_STRUCTURE: 5 sections (intro, guidelines, comments, diff-summary, instructions)")
    logger.info(f"HEADLESS_CLI_PROMPT_FIRST_800_CHARS:\n{prompt[:800]}\n---")
    logger.info(f"HEADLESS_CLI_PROMPT_LAST_800_CHARS:\n{prompt[-800:]}\n---")
    logger.info("HEADLESS_CLI_OPTIMIZATION: Using summarized diff instead of full diff to reduce OOM risk on Node.js-based CLIs")

    # ── execute ─────────────────────────────────────────────────────────────
    cli_display = adapter.cli_name.value.capitalize()
    project_root = ctx.data.get("project_root")

    with ctx.textual.loading(f"Running {cli_display} initial review..."):
        response = adapter.execute(prompt, cwd=project_root, timeout=timeout)

    if not response.succeeded:
        # Log the raw error for debugging (avoid markup issues)
        ctx.data[f"{output_key}_error"] = {
            "exit_code": response.exit_code,
            "stderr": response.stderr,
            "cwd": project_root,
        }

        # Display error safely (escape markup to avoid MarkupError)
        if response.stderr:
            try:
                safe_stderr = escape_markup(response.stderr)
                ctx.textual.dim_text(safe_stderr)
            except Exception:
                ctx.textual.dim_text("(Error output could not be displayed)")

        return _fail(ctx, msg.AIInitialReview.FAILED.format(
            cli_name=cli_display,
            exit_code=response.exit_code,
        ))

    # ── parse output ────────────────────────────────────────────────────────
    markdown_output = response.stdout
    summary, suggestions = parse_cli_review_output(markdown_output)

    # ── store results ───────────────────────────────────────────────────────
    ctx.data[f"{output_key}_suggestions"] = suggestions
    ctx.data[f"{output_key}_markdown"] = markdown_output

    # ── display ─────────────────────────────────────────────────────────────
    # Show summary section
    if summary:
        ctx.textual.text("")
        ctx.textual.markdown(summary)

    # Show findings section
    if suggestions:
        ctx.textual.text("")
        critical_count = sum(1 for s in suggestions if s.severity == "critical")
        improvement_count = sum(1 for s in suggestions if s.severity == "improvement")
        suggestion_count = sum(1 for s in suggestions if s.severity == "suggestion")

        ctx.textual.bold_text("Issues Found:")
        if critical_count:
            ctx.textual.error_text(f"  🔴 {critical_count} critical")
        if improvement_count:
            ctx.textual.warning_text(f"  🟡 {improvement_count} improvement(s)")
        if suggestion_count:
            ctx.textual.dim_text(f"  🔵 {suggestion_count} suggestion(s)")
    else:
        ctx.textual.text("")
        ctx.textual.panel(msg.AIInitialReview.NO_FINDINGS, panel_type="success")

    ctx.textual.end_step("success")
    return Success(
        f"Initial review complete: {len(suggestions)} issue(s) found"
    )


# ── helpers ───────────────────────────────────────────────────────────────────

def _resolve_adapter(cli_preference: str):
    """Return the first suitable headless adapter, or None if unavailable."""
    if cli_preference == "auto":
        for cli_name in HEADLESS_ADAPTER_REGISTRY:
            candidate = get_headless_adapter(cli_name)
            if candidate.is_available():
                return candidate
        return None

    try:
        candidate = get_headless_adapter(cli_preference)
    except ValueError:
        return None

    return candidate if candidate.is_available() else None


def _fail(ctx: WorkflowContext, message: str) -> Error:
    ctx.textual.error_text(message)
    ctx.textual.end_step("error")
    return Error(message)
