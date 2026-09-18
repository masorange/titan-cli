"""
Step: ai_assess_workflow_run

Ask the AI how well a workflow run did its job.

Deliberately a different question — and a different routing task — from
`ai_diagnose_log_session`, which asks why something broke. Here nothing
necessarily broke: what is wanted is a judgement on coverage and quality,
so the two can be pointed at different providers.
"""

from titan_cli.ai.router.declaration import declare_ai_usage
from titan_cli.ai.router.enums import AIProviderType
from titan_cli.ai.router.models import AIExecutionError, AIExecutionSuccess
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip

from operations import build_assessment_prompt

# A project-local task key, not an AITask member: this is a project step, and
# routing it separately from the failure diagnosis is the point.
WORKFLOW_RUN_ASSESSMENT = "workflow_run_assessment"


@declare_ai_usage(
    task=WORKFLOW_RUN_ASSESSMENT,
    executes=[AIProviderType.REMOTE, AIProviderType.CLI_HEADLESS],
    preferred=[AIProviderType.REMOTE],
    enforces=True,
)
def ai_assess_workflow_run(ctx: WorkflowContext) -> WorkflowResult:
    """
    Judge how well the audited run worked and what is worth improving.

    Inputs:
        workflow_run_profile (WorkflowRunProfile): From audit_workflow_run
        workflow_run_interpretation (Interpretation)
        workflow_run_history (RunHistory)

    Outputs:
        workflow_run_assessment (str): The generated Markdown assessment
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("AI Assessment")

    profile = ctx.get("workflow_run_profile")
    interpretation = ctx.get("workflow_run_interpretation")
    history = ctx.get("workflow_run_history")
    if not profile or not interpretation or history is None:
        ctx.textual.end_step("error")
        return Error("No audit in context. Run audit_workflow_run first.")

    if not ctx.ai_router:
        ctx.textual.dim_text("AI not configured — skipping assessment.")
        ctx.textual.end_step("skip")
        return Skip("AI not configured")

    if not ctx.textual.ask_confirm(
        "Ask AI what is worth improving in this run?", default=True
    ):
        ctx.textual.dim_text("Assessment skipped")
        ctx.textual.end_step("skip")
        return Skip("User skipped the AI assessment")

    prompt = build_assessment_prompt(profile, interpretation, history)

    with ctx.textual.loading("Assessing the run with AI…"):
        result = ctx.ai_router.generate_text(
            prompt,
            policy=ai_assess_workflow_run,
            max_tokens=2000,
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
            ctx.textual.error_text(f"AI assessment failed: {message}")
            ctx.textual.end_step("error")
            return Error(f"AI assessment failed: {message}")

    assessment = (response or "").strip()
    if not assessment:
        ctx.textual.warning_text("The model returned an empty assessment")
        ctx.textual.end_step("skip")
        return Skip("Empty AI assessment")

    ctx.textual.text("")
    ctx.textual.markdown(assessment)
    ctx.textual.text("")
    ctx.textual.end_step("success")
    return Success(
        "Run assessed", metadata={"workflow_run_assessment": assessment}
    )
