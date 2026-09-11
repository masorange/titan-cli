"""
Step: ai_diagnose_log_session

Ask the configured AI provider to diagnose the analyzed session.
"""

from titan_cli.ai.router.declaration import declare_ai_usage
from titan_cli.ai.router.enums import AIProviderType, AITask
from titan_cli.ai.router.models import AIExecutionError, AIExecutionSuccess
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip

from operations import build_diagnosis_prompt


@declare_ai_usage(
    task=AITask.GENERIC_ASSISTANT,
    # One prompt in, one Markdown answer out: either transport can serve it.
    executes=[AIProviderType.REMOTE, AIProviderType.CLI_HEADLESS],
    preferred=[AIProviderType.REMOTE],
    enforces=True,
)
def ai_diagnose_log_session(ctx: WorkflowContext) -> WorkflowResult:
    """
    Summarize what happened in the session and why it failed.

    The model is given the structured findings — timeline, grouped errors with
    payloads, warnings, slow operations — not the raw log, so the evidence
    stays inside a prompt budget regardless of how long the session ran.

    Inputs:
        log_analysis (SessionAnalysis): From analyze_log_session

    Outputs:
        log_diagnosis (str): The generated Markdown diagnosis
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("AI Diagnosis")

    analysis = ctx.get("log_analysis")
    if not analysis:
        ctx.textual.end_step("error")
        return Error("No analysis in context. Run analyze_log_session first.")

    if not ctx.ai_router:
        ctx.textual.dim_text("AI not configured — skipping diagnosis.")
        ctx.textual.end_step("skip")
        return Skip("AI not configured")

    if not ctx.textual.ask_confirm("Ask AI to diagnose this session?", default=True):
        ctx.textual.dim_text("Diagnosis skipped")
        ctx.textual.end_step("skip")
        return Skip("User skipped the AI diagnosis")

    prompt = build_diagnosis_prompt(analysis)

    with ctx.textual.loading("Diagnosing the session with AI…"):
        result = ctx.ai_router.generate_text(
            prompt,
            policy=ai_diagnose_log_session,
            # 1500 cut a real diagnosis off mid-sentence. The prompt asks for
            # one screen; this is headroom so the limit is never the editor.
            max_tokens=4000,
            temperature=0.2,
            announce=ctx.textual.ai_chip,
        )

    match result:
        case AIExecutionSuccess(data=response):
            pass
        case AIExecutionError(error_code="AI_DISABLED", error_message=message):
            ctx.textual.dim_text(message)
            ctx.textual.end_step("skip")
            return Skip(message)
        case AIExecutionError(error_message=message):
            ctx.textual.error_text(f"AI diagnosis failed: {message}")
            ctx.textual.end_step("error")
            return Error(f"AI diagnosis failed: {message}")

    diagnosis = (response or "").strip()
    if not diagnosis:
        ctx.textual.warning_text("The model returned an empty diagnosis")
        ctx.textual.end_step("skip")
        return Skip("Empty AI diagnosis")

    ctx.textual.text("")
    ctx.textual.markdown(diagnosis)
    ctx.textual.text("")
    ctx.textual.end_step("success")
    return Success("Session diagnosed", metadata={"log_diagnosis": diagnosis})
