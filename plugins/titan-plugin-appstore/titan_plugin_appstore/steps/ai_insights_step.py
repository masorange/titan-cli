"""
AI Insights Step - Generate intelligent analysis using Claude AI.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def ai_insights_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Generate AI-powered insights from metrics comparison.

    Uses Claude to analyze the metrics and provide actionable insights.

    Inputs (from ctx.data):
        - version_1_string, version_2_string
        - stability_metrics_v1, stability_metrics_v2
        - propagation_metrics_v1, propagation_metrics_v2
        - metrics_method: "full" or "partial"

    Outputs (saved to ctx.data):
        - ai_insights: Generated insights text

    Returns:
        Success with insights summary
        Error if AI analysis fails
    """
    if not ctx.textual:
        return Error("Textual UI context is required for this step")

    ctx.textual.begin_step("AI Insights")

    try:
        # Get metrics data
        version_1 = ctx.data.get("version_1_string")
        version_2 = ctx.data.get("version_2_string")
        stab_v1 = ctx.data.get("stability_metrics_v1", {})
        stab_v2 = ctx.data.get("stability_metrics_v2", {})
        prop_v1 = ctx.data.get("propagation_metrics_v1", {})
        prop_v2 = ctx.data.get("propagation_metrics_v2", {})
        metrics_method = ctx.data.get("metrics_method", "partial")

        if not all([version_1, version_2, stab_v1, stab_v2]):
            ctx.textual.error_text("Missing metrics data for AI analysis")
            ctx.textual.end_step("error")
            return Error("Missing metrics data")

        ctx.textual.text("Analyzing metrics with Claude AI...")

        # Prepare data summary for AI
        data_summary = f"""
Comparison: {version_1} vs {version_2}

STABILITY METRICS:
{version_1}:
- Crash Rate: {stab_v1.get('crash_rate', 0):.4f}%
- Hang Rate: {stab_v1.get('hang_rate', 0):.4f}%
- Terminations: {stab_v1.get('terminations', 0):,}
- Hangs: {stab_v1.get('hangs', 0):,}

{version_2}:
- Crash Rate: {stab_v2.get('crash_rate', 0):.4f}%
- Hang Rate: {stab_v2.get('hang_rate', 0):.4f}%
- Terminations: {stab_v2.get('terminations', 0):,}
- Hangs: {stab_v2.get('hangs', 0):,}

PROPAGATION METRICS:
"""

        if metrics_method == "full":
            data_summary += f"""
{version_1}:
- Total Units: {prop_v1.get('total_units', 0):,}
- Countries: {prop_v1.get('total_countries', 0)}

{version_2}:
- Total Units: {prop_v2.get('total_units', 0):,}
- Countries: {prop_v2.get('total_countries', 0)}
"""
        else:
            data_summary += f"""
{version_1}:
- Total Builds: {prop_v1.get('total_builds', 0)}
- Build Activity: {prop_v1.get('estimated_activity', 'unknown')}

{version_2}:
- Total Builds: {prop_v2.get('total_builds', 0)}
- Build Activity: {prop_v2.get('estimated_activity', 'unknown')}

Note: Propagation metrics are estimated (no vendor_number configured for Sales Reports)
"""

        # Try to get AI insights from the Titan AI client
        try:
            from titan_cli.ai.client import get_ai_client

            ai_client = get_ai_client()

            prompt = f"""You are an iOS app stability analyst. Analyze the following metrics comparison and provide:

1. **Key Findings** (2-3 bullet points of most important observations)
2. **Recommendations** (1-2 actionable next steps for the development team)
3. **Risk Assessment** (low/medium/high risk for the newer version)

Data:
{data_summary}

Format your response concisely. Focus on actionable insights."""

            response = ai_client.generate(
                prompt=prompt,
                max_tokens=500,
                temperature=0.3  # Lower temperature for more focused analysis
            )

            insights = response.content

        except ImportError:
            # Fallback to basic insights if AI client not available
            insights = _generate_basic_insights(version_1, version_2, stab_v1, stab_v2, prop_v1, prop_v2, metrics_method)

        # Display insights
        ctx.textual.text("")
        ctx.textual.text("─" * 80)
        ctx.textual.text("🤖 AI INSIGHTS")
        ctx.textual.text("─" * 80)
        ctx.textual.text("")

        for line in insights.split('\n'):
            ctx.textual.text(f"   {line}")

        ctx.textual.text("")
        ctx.textual.text("─" * 80)

        # Save to context
        ctx.data["ai_insights"] = insights

        ctx.textual.end_step("success")

        return Success("AI insights generated")

    except Exception as e:
        error_msg = f"Failed to generate AI insights: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


def _generate_basic_insights(version_1, version_2, stab_v1, stab_v2, prop_v1, prop_v2, metrics_method):
    """Generate basic insights without AI when client is unavailable."""

    cr1 = stab_v1.get("crash_rate", 0)
    cr2 = stab_v2.get("crash_rate", 0)
    hr1 = stab_v1.get("hang_rate", 0)
    hr2 = stab_v2.get("hang_rate", 0)

    crash_diff = abs(cr1 - cr2)
    hang_diff = abs(hr1 - hr2)

    insights = "**Key Findings:**\n\n"

    # Crash rate analysis
    if cr1 < cr2:
        improvement = ((cr2 - cr1) / cr2 * 100) if cr2 > 0 else 0
        insights += f"• {version_1} shows {improvement:.1f}% improvement in crash rate ({crash_diff:.4f}% reduction)\n"
    elif cr1 > cr2:
        regression = ((cr1 - cr2) / cr1 * 100) if cr1 > 0 else 0
        insights += f"• {version_1} has {regression:.1f}% regression in crash rate ({crash_diff:.4f}% increase)\n"

    # Hang rate analysis
    if hang_diff > 0.1:  # Significant difference
        if hr1 < hr2:
            insights += f"• Hang rate improved by {hang_diff:.4f}%\n"
        else:
            insights += f"• Hang rate increased by {hang_diff:.4f}%\n"

    insights += "\n**Recommendations:**\n\n"

    # Risk assessment
    if cr1 > 10:
        insights += "• CRITICAL: Crash rate exceeds 10% - investigate immediately\n"
        risk = "HIGH"
    elif cr1 > 5:
        insights += "• WARNING: Crash rate above 5% - monitor closely\n"
        risk = "MEDIUM"
    elif cr1 > cr2:
        insights += "• Consider investigating crash regression before wider rollout\n"
        risk = "MEDIUM"
    else:
        insights += "• Stability looks good - proceed with confidence\n"
        risk = "LOW"

    insights += f"\n**Risk Assessment:** {risk}"

    return insights


__all__ = ["ai_insights_step"]
