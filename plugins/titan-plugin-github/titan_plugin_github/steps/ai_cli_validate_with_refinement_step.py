"""
AI CLI Validate With Refinement Step

Iterates over PR comment threads, obtains an AI-generated reply suggestion for
each one, and lets the user Approve / Reject / Refine in a loop.

Each refinement re-invokes the headless CLI with the user's additional context
added to the prompt — without meta-conversation. Maximum iterations are
configurable (default 4) to keep context windows manageable.

ctx.data reads (configurable via workflow params):
    review_threads    (List[UICommentThread]) — threads to iterate
    pr_diff           (str)                   — PR diff for snippet context
    initial_review_findings (List[ReviewFinding], optional)

ctx.data writes:
    code_review_session_result  (CodeReviewSessionResult)

YAML usage:
    - plugin: github
      step: ai_cli_validate_with_refinement
      params:
        threads_key: review_threads
        diff_key: pr_diff
        output_key: code_review_session_result
        cli_preference: auto
        timeout: 60
        max_iterations: 4
"""

import threading
from typing import Optional

from titan_cli.core.models.code_review import (
    CodeReviewSessionResult,
    CommentReviewSession,
    RefinementAction,
    RefinementIteration,
    UserDecision,
)
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from titan_cli.external_cli.adapters import HEADLESS_ADAPTER_REGISTRY, get_headless_adapter
from titan_cli.external_cli.adapters.base import SupportedCLI
from titan_cli.messages import msg

from ..operations.ai_review_operations import (
    build_refinement_prompt,
    parse_reply_suggestion,
)
from ..widgets.comment_refinement_widget import CommentRefinementWidget

_VALID_CLI_PREFERENCES = {"auto"} | set(SupportedCLI)

_DECISION_BADGE: dict[RefinementAction, tuple[str, str]] = {
    RefinementAction.APPROVE: ("✓ Approved", "success"),
    RefinementAction.REJECT: ("✗ Rejected", "error"),
    RefinementAction.REFINE: ("💬 Refining…", "default"),
}


def ai_cli_validate_with_refinement(ctx: WorkflowContext) -> WorkflowResult:
    """
    Iterate over comment threads showing AI suggestions and allowing refinement.

    Reads params from ctx.data (injected by workflow engine from step params):
        threads_key (str, default "review_threads")
        diff_key (str, default "pr_diff")
        output_key (str, default "code_review_session_result")
        cli_preference (str, default "auto")
        timeout (int, default 60)
        max_iterations (int, default 4)
    """
    ctx.textual.begin_step("AI Validate with Refinement")

    # ── params ──────────────────────────────────────────────────────────────
    threads_key = ctx.data.get("threads_key", "review_threads")
    diff_key = ctx.data.get("diff_key", "pr_diff")
    output_key = ctx.data.get("output_key", "code_review_session_result")
    cli_preference = ctx.data.get("cli_preference", "auto")
    timeout = int(ctx.data.get("timeout", 60))
    max_iterations = int(ctx.data.get("max_iterations", 4))

    # ── validate cli_preference ─────────────────────────────────────────────
    if cli_preference not in _VALID_CLI_PREFERENCES:
        return _fail(ctx, msg.AICLIHeadless.UNKNOWN_CLI.format(
            cli_name=cli_preference,
            valid=", ".join(sorted(_VALID_CLI_PREFERENCES)),
        ))

    # ── read ctx.data ───────────────────────────────────────────────────────
    threads = ctx.data.get(threads_key, [])
    diff = ctx.data.get(diff_key, "")

    if not threads:
        ctx.textual.dim_text(msg.AIRefinement.NO_THREADS)
        ctx.textual.end_step("skip")
        return Skip(msg.AIRefinement.NO_THREADS)

    # ── resolve adapter ─────────────────────────────────────────────────────
    adapter = _resolve_adapter(cli_preference)
    if adapter is None:
        if cli_preference == "auto":
            return _fail(ctx, msg.AICLIHeadless.NO_ADAPTER_AVAILABLE)
        return _fail(ctx, msg.AICLIHeadless.CLI_NOT_AVAILABLE.format(cli_name=cli_preference))

    # ── initialise session result ───────────────────────────────────────────
    initial_findings = ctx.data.get("initial_review_findings", [])
    session_result = CodeReviewSessionResult(findings_initial=initial_findings)

    cli_display = adapter.cli_name.value.capitalize()
    project_root = ctx.data.get("project_root")

    # ── main loop ───────────────────────────────────────────────────────────
    for thread_idx, thread in enumerate(threads):
        main_comment = thread.main_comment
        if not main_comment:
            continue

        comment_id = main_comment.id
        ctx.textual.text("")
        ctx.textual.dim_text(
            f"Thread {thread_idx + 1}/{len(threads)} — "
            f"{main_comment.author_login}: {main_comment.body[:60]}…"
        )

        initial_prompt = build_refinement_prompt(
            original_comment=main_comment.body,
            existing_replies=[r.body for r in thread.replies],
            diff_snippet=diff[:8_000] if diff else None,
            user_feedback="Generate an initial reply suggestion for this comment.",
            previous_suggestion=None,
        )

        with ctx.textual.loading(f"Getting suggestion from {cli_display}…"):
            initial_response = adapter.execute(initial_prompt, cwd=project_root, timeout=timeout)

        if not initial_response.succeeded:
            ctx.textual.warning_text(
                msg.AIRefinement.INITIAL_SUGGESTION_FAILED.format(id=comment_id)
            )
            continue

        suggestion = parse_reply_suggestion(initial_response.stdout)
        session = CommentReviewSession(
            comment_id=comment_id,
            original_comment=main_comment.body,
            existing_replies=[r.body for r in thread.replies],
            iterations=[RefinementIteration(iteration_number=1, agent_suggestion=suggestion)],
        )

        decision = _run_refinement_loop(
            ctx=ctx,
            session=session,
            thread=thread,
            thread_idx=thread_idx,
            total_threads=len(threads),
            adapter=adapter,
            diff=diff,
            project_root=project_root,
            timeout=timeout,
            max_iterations=max_iterations,
            cli_display=cli_display,
        )

        session.user_decision = decision
        if decision == UserDecision.APPROVED:
            session.final_suggestion = session.current_suggestion

        session_result.comment_sessions[comment_id] = session

    # ── store and summarise ──────────────────────────────────────────────────
    ctx.data[output_key] = session_result

    approved = len(session_result.approved_sessions)
    total = len(session_result.comment_sessions)
    summary = msg.AIRefinement.COMPLETE.format(
        total=total,
        approved=approved,
        iterations=session_result.total_iterations,
    )
    ctx.textual.success_text(summary)
    ctx.textual.end_step("success")
    return Success(summary)


# ── refinement loop ───────────────────────────────────────────────────────────

def _run_refinement_loop(
    ctx: WorkflowContext,
    session: CommentReviewSession,
    thread,
    thread_idx: int,
    total_threads: int,
    adapter,
    diff: str,
    project_root: Optional[str],
    timeout: int,
    max_iterations: int,
    cli_display: str,
) -> UserDecision:
    """
    Mount CommentRefinementWidget and handle the approve/reject/refine loop.

    Returns the final UserDecision for this thread.
    """
    from titan_cli.ui.tui.widgets import PromptChoice
    from titan_cli.ui.tui.widgets.decision_badge import DecisionBadge

    while True:
        current_iteration = session.iteration_count

        if current_iteration >= max_iterations:
            ctx.textual.warning_text(
                msg.AIRefinement.MAX_ITERATIONS_WARNING.format(max=max_iterations)
            )

        result_container: dict = {}
        result_event = threading.Event()

        def on_decision(action: RefinementAction) -> None:
            result_container["action"] = action
            result_event.set()

        widget = CommentRefinementWidget(
            thread=thread,
            suggestion=session.current_suggestion or "",
            iteration=current_iteration,
            max_iterations=max_iterations,
            thread_label=f"Thread {thread_idx + 1} of {total_threads}",
            on_select=on_decision,
        )

        ctx.textual.text("")
        ctx.textual.mount(widget)
        result_event.wait()

        action: RefinementAction = result_container.get("action", RefinementAction.REJECT)

        def replace_buttons(a=action) -> None:
            try:
                widget.query_one(PromptChoice).remove()
                label, variant = _DECISION_BADGE.get(a, (f"→ {a}", "default"))
                widget.mount(DecisionBadge(label, variant=variant))
            except Exception:
                pass

        ctx.textual.app.call_from_thread(replace_buttons)

        if action == RefinementAction.APPROVE:
            return UserDecision.APPROVED

        if action == RefinementAction.REJECT:
            return UserDecision.REJECTED

        # action == RefinementAction.REFINE
        if current_iteration >= max_iterations:
            ctx.textual.warning_text(msg.AIRefinement.CANNOT_REFINE_FURTHER)
            continue

        feedback = ctx.textual.ask_multiline(
            "Enter feedback for refinement (Ctrl+D to confirm, Esc to cancel):",
        )

        if not feedback or not feedback.strip():
            ctx.textual.dim_text(msg.AIRefinement.NO_FEEDBACK)
            continue

        session.iterations[-1].user_feedback = feedback

        refine_prompt = build_refinement_prompt(
            original_comment=session.original_comment,
            existing_replies=session.existing_replies,
            diff_snippet=diff[:8_000] if diff else None,
            user_feedback=feedback,
            previous_suggestion=session.current_suggestion,
        )

        with ctx.textual.loading(f"Refining with {cli_display}…"):
            response = adapter.execute(refine_prompt, cwd=project_root, timeout=timeout)

        if not response.succeeded:
            ctx.textual.warning_text(
                msg.AIRefinement.REFINEMENT_FAILED.format(code=response.exit_code)
            )
            continue

        new_suggestion = parse_reply_suggestion(response.stdout)
        session.iterations.append(
            RefinementIteration(
                iteration_number=current_iteration + 1,
                agent_suggestion=new_suggestion,
                user_feedback=feedback,
            )
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
