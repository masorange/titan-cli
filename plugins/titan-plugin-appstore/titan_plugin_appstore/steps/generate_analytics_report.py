"""
Generate Analytics Report Step - Display terminal-based comparison report.
"""

from datetime import datetime
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def generate_analytics_report(ctx: WorkflowContext) -> WorkflowResult:
    """
    Generate comprehensive terminal-based report with all analytics.

    Inputs (from ctx.data):
        - metrics_method: "full" (Performance + Sales) or "partial" (Performance only)
        - propagation_metrics_v1, propagation_metrics_v2
        - stability_metrics_v1, stability_metrics_v2
        - version_1_string, version_2_string

    Returns:
        Success with report summary
        Error if generation fails
    """
    if not ctx.textual:
        return Error("Textual UI context is required for this step")

    ctx.textual.begin_step("Generate Report")

    try:
        # Get data from context
        metrics_method = ctx.data.get("metrics_method") or ctx.data.get("analytics_method", "partial")
        prop_v1 = ctx.data.get("propagation_metrics_v1", {})
        prop_v2 = ctx.data.get("propagation_metrics_v2", {})
        stab_v1 = ctx.data.get("stability_metrics_v1", {})
        stab_v2 = ctx.data.get("stability_metrics_v2", {})
        version_1_string = ctx.data.get("version_1_string")
        version_2_string = ctx.data.get("version_2_string")

        if not all([prop_v1, prop_v2, stab_v1, stab_v2, version_1_string, version_2_string]):
            ctx.textual.error_text("Missing metrics data")
            ctx.textual.end_step("error")
            return Error("Missing metrics data")

        ctx.textual.text("Generating analytics report...")
        ctx.textual.text("")

        # Display header
        ctx.textual.text("=" * 80)
        ctx.textual.text(f"📊 APP STORE ANALYTICS REPORT")
        ctx.textual.text("=" * 80)
        ctx.textual.text("")
        ctx.textual.text(f"🔍 Comparison: {version_1_string} vs {version_2_string}")
        ctx.textual.text(f"📅 Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        ctx.textual.text(f"📡 Data Source: {'Performance API + Sales Reports (FULL)' if metrics_method == 'full' else 'Performance API only (crashes exact)' if metrics_method in ['api', 'partial'] else 'Fallback (estimated)'}")
        ctx.textual.text("")

        # Warning for partial mode
        if metrics_method == "partial":
            ctx.textual.text("⚠️  PARTIAL METRICS MODE")
            ctx.textual.text("   Sales Reports unavailable (no vendor number configured).")
            ctx.textual.text("   Propagation metrics estimated from build activity.")
            ctx.textual.text("   Stability metrics are EXACT from Performance API.")
            ctx.textual.text("")

        # === STABILITY METRICS TABLE ===
        ctx.textual.text("─" * 80)
        ctx.textual.text("🛡️  STABILITY METRICS")
        ctx.textual.text("─" * 80)
        ctx.textual.text("")

        # Get stability data
        cr1 = stab_v1.get("crash_rate", 0)
        cr2 = stab_v2.get("crash_rate", 0)
        hr1 = stab_v1.get("hang_rate", 0)
        hr2 = stab_v2.get("hang_rate", 0)
        t1 = stab_v1.get("terminations", 0)
        t2 = stab_v2.get("terminations", 0)
        h1 = stab_v1.get("hangs", 0)
        h2 = stab_v2.get("hangs", 0)

        # Stability table header - fixed width columns for alignment
        v1_header = f"{version_1_string:<12}"[:12]  # Truncate if too long
        v2_header = f"{version_2_string:<12}"[:12]

        ctx.textual.text("┌──────────────────┬──────────────┬──────────────┬─────────┐")
        ctx.textual.text(f"│ Métrica          │ {v1_header} │ {v2_header} │ Ganador │")
        ctx.textual.text("├──────────────────┼──────────────┼──────────────┼─────────┤")

        # Crash Rate row
        crash_winner = version_1_string[:7] if cr1 < cr2 else version_2_string[:7]
        cr1_mark = "✅" if (version_1_string if cr1 < cr2 else version_2_string) == version_1_string else "  "
        cr2_mark = "✅" if (version_1_string if cr1 < cr2 else version_2_string) == version_2_string else "  "
        ctx.textual.text(f"│ 💥 Crash Rate    │ {cr1:>9.4f}% {cr1_mark} │ {cr2:>9.4f}% {cr2_mark} │ {crash_winner:7} │")

        # Terminations row
        ctx.textual.text(f"│ 📊 Terminations  │ {t1:>12,} │ {t2:>12,} │    -    │")

        # Hang Rate row
        hang_winner = version_1_string[:7] if hr1 < hr2 else version_2_string[:7]
        hr1_mark = "✅" if (version_1_string if hr1 < hr2 else version_2_string) == version_1_string else "  "
        hr2_mark = "✅" if (version_1_string if hr1 < hr2 else version_2_string) == version_2_string else "  "
        ctx.textual.text(f"│ ⏸️  Hang Rate     │ {hr1:>9.4f}% {hr1_mark} │ {hr2:>9.4f}% {hr2_mark} │ {hang_winner:7} │")

        # Hangs row
        ctx.textual.text(f"│ 📊 Hangs         │ {h1:>12,} │ {h2:>12,} │    -    │")

        ctx.textual.text("└──────────────────┴──────────────┴──────────────┴─────────┘")
        ctx.textual.text("")

        # === PROPAGATION METRICS TABLE ===
        ctx.textual.text("─" * 80)
        ctx.textual.text("🚀 PROPAGATION METRICS")
        ctx.textual.text("─" * 80)
        ctx.textual.text("")

        if metrics_method == "full":
            # Full metrics with Sales Reports
            units1 = prop_v1.get("total_units", 0)
            units2 = prop_v2.get("total_units", 0)
            countries1 = prop_v1.get("total_countries", 0)
            countries2 = prop_v2.get("total_countries", 0)

            ctx.textual.text("┌──────────────────┬──────────────┬──────────────┬─────────┐")
            ctx.textual.text(f"│ Métrica          │ {v1_header} │ {v2_header} │ Ganador │")
            ctx.textual.text("├──────────────────┼──────────────┼──────────────┼─────────┤")

            # Total Units row
            units_winner = version_1_string[:7] if units1 > units2 else version_2_string[:7]
            u1_mark = "✅" if (version_1_string if units1 > units2 else version_2_string) == version_1_string else "  "
            u2_mark = "✅" if (version_1_string if units1 > units2 else version_2_string) == version_2_string else "  "
            ctx.textual.text(f"│ 📦 Total Units   │ {units1:>10,} {u1_mark} │ {units2:>10,} {u2_mark} │ {units_winner:7} │")

            # Countries row
            ctx.textual.text(f"│ 🌍 Countries     │ {countries1:>12} │ {countries2:>12} │    -    │")

            ctx.textual.text("└──────────────────┴──────────────┴──────────────┴─────────┘")

        else:
            # Partial metrics (build activity estimation)
            builds1 = prop_v1.get("total_builds", 0)
            builds2 = prop_v2.get("total_builds", 0)
            activity1 = str(prop_v1.get("estimated_activity", "unknown"))[:10]
            activity2 = str(prop_v2.get("estimated_activity", "unknown"))[:10]

            ctx.textual.text("┌──────────────────┬──────────────┬──────────────┬─────────┐")
            ctx.textual.text(f"│ Métrica          │ {v1_header} │ {v2_header} │ Ganador │")
            ctx.textual.text("├──────────────────┼──────────────┼──────────────┼─────────┤")

            # Total Builds row
            builds_winner = version_1_string[:7] if builds1 > builds2 else version_2_string[:7]
            b1_mark = "✅" if (version_1_string if builds1 > builds2 else version_2_string) == version_1_string else "  "
            b2_mark = "✅" if (version_1_string if builds1 > builds2 else version_2_string) == version_2_string else "  "
            ctx.textual.text(f"│ 🔨 Total Builds  │ {builds1:>10} {b1_mark} │ {builds2:>10} {b2_mark} │ {builds_winner:7} │")

            # Build Activity row
            ctx.textual.text(f"│ 📈 Activity      │ {activity1:>12} │ {activity2:>12} │    -    │")

            ctx.textual.text("└──────────────────┴──────────────┴──────────────┴─────────┘")

        ctx.textual.text("")

        # === KEY INSIGHTS ===
        ctx.textual.text("─" * 80)
        ctx.textual.text("💡 KEY INSIGHTS")
        ctx.textual.text("─" * 80)
        ctx.textual.text("")

        # Crash rate insights
        crash_diff = abs(cr1 - cr2)
        crash_improvement = ((cr2 - cr1) / cr2 * 100) if cr2 > 0 else 0

        if cr1 < cr2:
            ctx.textual.text(f"   ✅ {version_1_string} es MÁS ESTABLE")
            ctx.textual.text(f"      Crash rate: {crash_diff:.4f}% menos ({crash_improvement:.1f}% mejora)")
        elif cr1 > cr2:
            ctx.textual.text(f"   ⚠️  {version_1_string} es MENOS ESTABLE")
            ctx.textual.text(f"      Crash rate: {crash_diff:.4f}% más ({abs(crash_improvement):.1f}% peor)")
        else:
            ctx.textual.text(f"   ➖ Ambas versiones tienen mismo crash rate")

        ctx.textual.text("")

        # Hang rate insights
        hang_diff = abs(hr1 - hr2)
        if hr1 < hr2:
            ctx.textual.text(f"   ✅ {version_1_string} tiene MENOS HANGS")
            ctx.textual.text(f"      Hang rate: {hang_diff:.4f}% menos")
        elif hr1 > hr2:
            ctx.textual.text(f"   ⚠️  {version_1_string} tiene MÁS HANGS")
            ctx.textual.text(f"      Hang rate: {hang_diff:.4f}% más")

        ctx.textual.text("")

        # Propagation insights
        if metrics_method == "full":
            units_diff = abs(units1 - units2)
            if units1 > units2:
                ctx.textual.text(f"   📦 {version_1_string} tiene MÁS INSTALACIONES")
                ctx.textual.text(f"      Total units: {units_diff:,} más")
            elif units1 < units2:
                ctx.textual.text(f"   📦 {version_2_string} tiene MÁS INSTALACIONES")
                ctx.textual.text(f"      Total units: {units_diff:,} más")
        else:
            builds_diff = abs(builds1 - builds2)
            if builds1 > builds2:
                ctx.textual.text(f"   🔨 {version_1_string} tiene MÁS ACTIVIDAD DE BUILD")
                ctx.textual.text(f"      Total builds: {builds_diff} más")
            elif builds1 < builds2:
                ctx.textual.text(f"   🔨 {version_2_string} tiene MÁS ACTIVIDAD DE BUILD")
                ctx.textual.text(f"      Total builds: {builds_diff} más")

        ctx.textual.text("")
        ctx.textual.text("=" * 80)
        ctx.textual.text("")

        ctx.textual.end_step("success")

        return Success(f"Report generated: {version_1_string} vs {version_2_string}")

    except Exception as e:
        error_msg = f"Failed to generate report: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)
