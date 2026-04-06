"""
Analyze Metrics Step - Generate comparison charts from analytics or fallback data.
"""

from pathlib import Path
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..clients.appstore_client import AppStoreConnectClient
from ..credentials import CredentialsManager


def analyze_metrics_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Generate comparison charts from metrics data.

    Inputs (from ctx.data):
        - analytics_method: "api" or "fallback"
        - propagation_metrics_v1, propagation_metrics_v2
        - stability_metrics_v1, stability_metrics_v2
        - version_1_string, version_2_string

    Outputs (saved to ctx.data):
        - chart_paths: Dict with paths to generated charts

    Returns:
        Success with chart paths
        Error if chart generation fails
    """
    if not ctx.textual:
        return Error("Textual UI context is required for this step")

    ctx.textual.begin_step("Generate Charts")

    try:
        # Check dependencies
        try:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
        except ImportError as e:
            ctx.textual.warning_text(f"⚠️  matplotlib not available - skipping charts")
            ctx.textual.text("   Charts will not be generated, but report will still be created")
            ctx.textual.text("")

            # Set empty chart paths so report generation continues
            ctx.data["chart_paths"] = {}

            ctx.textual.end_step("success")
            return Success("Charts skipped (matplotlib not available)")

        # Get data from context
        analytics_method = ctx.data.get("analytics_method", "fallback")
        prop_v1 = ctx.data.get("propagation_metrics_v1", {})
        prop_v2 = ctx.data.get("propagation_metrics_v2", {})
        stab_v1 = ctx.data.get("stability_metrics_v1", {})
        stab_v2 = ctx.data.get("stability_metrics_v2", {})
        version_1_string = ctx.data.get("version_1_string")
        version_2_string = ctx.data.get("version_2_string")

        if not all([prop_v1, prop_v2, stab_v1, stab_v2, version_1_string, version_2_string]):
            ctx.textual.error_text("Missing metrics data")
            ctx.textual.end_step("error")
            return Error("Missing metrics data. Run request_analytics_step first.")

        ctx.textual.text(f"Generating charts ({analytics_method} mode)...")

        # Create output directory
        output_dir = Path.cwd() / "analytics_reports"
        output_dir.mkdir(exist_ok=True)

        chart_paths = {}

        # Chart 1: Propagation Comparison (Bar chart for fallback mode)
        fig, ax = plt.subplots(figsize=(10, 6))

        versions = [version_1_string, version_2_string]

        if analytics_method == "api":
            # Use sessions from API
            sessions_counts = [
                prop_v1.get("total_sessions", 0),
                prop_v2.get("total_sessions", 0)
            ]

            bars = ax.bar(versions, sessions_counts, color=["#3498db", "#e74c3c"], alpha=0.7)
            ax.set_ylabel("Total Sessions", fontsize=12)
            ax.set_title(
                f"Propagation: Total Sessions\n{version_1_string} vs {version_2_string}",
                fontsize=14,
                fontweight="bold"
            )
            ax.grid(True, alpha=0.3, axis="y")

            # Add value labels
            for bar in bars:
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height,
                    f"{int(height):,}",
                    ha="center",
                    va="bottom",
                    fontsize=12,
                    fontweight="bold"
                )

        else:  # fallback
            # Use build counts for propagation
            build_counts = [
                prop_v1.get("total_builds", 0),
                prop_v2.get("total_builds", 0)
            ]

            bars = ax.bar(versions, build_counts, color=["#3498db", "#e74c3c"], alpha=0.7)
            ax.set_ylabel("Total Builds", fontsize=12)
            ax.set_title(
                f"Propagation: Build Activity\n{version_1_string} vs {version_2_string}",
                fontsize=14,
                fontweight="bold"
            )
            ax.grid(True, alpha=0.3, axis="y")

            # Add value labels
            for bar in bars:
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height,
                    f"{int(height)}",
                    ha="center",
                    va="bottom",
                    fontsize=12,
                    fontweight="bold"
                )

        plt.tight_layout()

        chart_path = output_dir / "propagation_comparison.png"
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close()

        chart_paths["propagation_comparison"] = str(chart_path)
        ctx.textual.success_text(f"✓ Saved: propagation_comparison.png")

        # Chart 2: Stability Comparison (Reviews)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        if analytics_method == "api":
            # Crash Rate from API
            crash_rates = [
                stab_v1.get("crash_rate", 0),
                stab_v2.get("crash_rate", 0)
            ]

            bars1 = ax1.bar(versions, crash_rates, color=["#e74c3c", "#c0392b"], alpha=0.7)
            ax1.set_ylabel("Crash Rate (%)", fontsize=12)
            ax1.set_title("Stability: Crash Rate", fontsize=13, fontweight="bold")
            ax1.grid(True, alpha=0.3, axis="y")

            for bar in bars1:
                height = bar.get_height()
                ax1.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height,
                    f"{height:.4f}%",
                    ha="center",
                    va="bottom",
                    fontsize=10,
                )

            # Retention D1
            retentions = [
                stab_v1.get("retention_d1", 0),
                stab_v2.get("retention_d1", 0)
            ]

            bars2 = ax2.bar(versions, retentions, color=["#2ecc71", "#f39c12"], alpha=0.7)
            ax2.set_ylabel("Retention D1 (%)", fontsize=12)
            ax2.set_title("Stability: Day 1 Retention", fontsize=13, fontweight="bold")
            ax2.grid(True, alpha=0.3, axis="y")

            for bar in bars2:
                height = bar.get_height()
                ax2.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height,
                    f"{height:.1f}%",
                    ha="center",
                    va="bottom",
                    fontsize=10,
                )

        else:  # fallback
            # Average Rating
            ratings = [
                stab_v1.get("average_rating", 0),
                stab_v2.get("average_rating", 0)
            ]

            bars1 = ax1.bar(versions, ratings, color=["#2ecc71", "#f39c12"], alpha=0.7)
            ax1.set_ylabel("Average Rating (★)", fontsize=12)
            ax1.set_title("Stability: User Ratings", fontsize=13, fontweight="bold")
            ax1.set_ylim(0, 5)
            ax1.grid(True, alpha=0.3, axis="y")

            for bar in bars1:
                height = bar.get_height()
                ax1.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height,
                    f"{height:.1f}★",
                    ha="center",
                    va="bottom",
                    fontsize=10,
                )

            # Crash Mention Rate
            crash_rates = [
                stab_v1.get("crash_mention_rate", 0),
                stab_v2.get("crash_mention_rate", 0)
            ]

            bars2 = ax2.bar(versions, crash_rates, color=["#e74c3c", "#c0392b"], alpha=0.7)
            ax2.set_ylabel("Crash Mention Rate (%)", fontsize=12)
            ax2.set_title("Stability: Crash Mentions in Reviews", fontsize=13, fontweight="bold")
            ax2.grid(True, alpha=0.3, axis="y")

            for bar in bars2:
                height = bar.get_height()
                ax2.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height,
                    f"{height:.1f}%",
                    ha="center",
                    va="bottom",
                    fontsize=10,
                )

        plt.tight_layout()

        chart_path = output_dir / "stability_comparison.png"
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close()

        chart_paths["stability_comparison"] = str(chart_path)
        ctx.textual.success_text(f"✓ Saved: stability_comparison.png")

        # Chart 3: Summary Dashboard
        fig = plt.figure(figsize=(12, 8))
        gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)

        if analytics_method == "api":
            # Sessions
            ax1 = fig.add_subplot(gs[0, 0])
            sessions = [prop_v1.get("total_sessions", 0), prop_v2.get("total_sessions", 0)]
            ax1.bar(versions, sessions, color=["#3498db", "#e74c3c"], alpha=0.7)
            ax1.set_title("Total Sessions", fontweight="bold")
            ax1.set_ylabel("Sessions")
            ax1.grid(True, alpha=0.3, axis="y")

            # Active Devices
            ax2 = fig.add_subplot(gs[0, 1])
            devices = [prop_v1.get("total_devices", 0), prop_v2.get("total_devices", 0)]
            ax2.bar(versions, devices, color=["#2ecc71", "#f39c12"], alpha=0.7)
            ax2.set_title("Active Devices", fontweight="bold")
            ax2.set_ylabel("Devices")
            ax2.grid(True, alpha=0.3, axis="y")

            # Crash Rate
            ax3 = fig.add_subplot(gs[1, 0])
            crash_rates = [stab_v1.get("crash_rate", 0), stab_v2.get("crash_rate", 0)]
            ax3.bar(versions, crash_rates, color=["#e74c3c", "#c0392b"], alpha=0.7)
            ax3.set_title("Crash Rate", fontweight="bold")
            ax3.set_ylabel("Rate (%)")
            ax3.grid(True, alpha=0.3, axis="y")

            # Retention D1
            ax4 = fig.add_subplot(gs[1, 1])
            retentions = [stab_v1.get("retention_d1", 0), stab_v2.get("retention_d1", 0)]
            ax4.bar(versions, retentions, color=["#9b59b6", "#8e44ad"], alpha=0.7)
            ax4.set_title("Retention D1", fontweight="bold")
            ax4.set_ylabel("Retention (%)")
            ax4.grid(True, alpha=0.3, axis="y")

        else:  # fallback
            # Build activity
            ax1 = fig.add_subplot(gs[0, 0])
            build_counts = [prop_v1.get("total_builds", 0), prop_v2.get("total_builds", 0)]
            ax1.bar(versions, build_counts, color=["#3498db", "#e74c3c"], alpha=0.7)
            ax1.set_title("Build Activity", fontweight="bold")
            ax1.set_ylabel("Total Builds")
            ax1.grid(True, alpha=0.3, axis="y")

            # Average rating
            ax2 = fig.add_subplot(gs[0, 1])
            ratings = [stab_v1.get("average_rating", 0), stab_v2.get("average_rating", 0)]
            ax2.bar(versions, ratings, color=["#2ecc71", "#f39c12"], alpha=0.7)
            ax2.set_title("User Rating", fontweight="bold")
            ax2.set_ylabel("Average Rating (★)")
            ax2.set_ylim(0, 5)
            ax2.grid(True, alpha=0.3, axis="y")

            # Crash mentions
            ax3 = fig.add_subplot(gs[1, 0])
            crash_rates = [stab_v1.get("crash_mention_rate", 0), stab_v2.get("crash_mention_rate", 0)]
            ax3.bar(versions, crash_rates, color=["#e74c3c", "#c0392b"], alpha=0.7)
            ax3.set_title("Crash Mentions", fontweight="bold")
            ax3.set_ylabel("Mention Rate (%)")
            ax3.grid(True, alpha=0.3, axis="y")

            # Review count
            ax4 = fig.add_subplot(gs[1, 1])
            review_counts = [stab_v1.get("total_reviews", 0), stab_v2.get("total_reviews", 0)]
            ax4.bar(versions, review_counts, color=["#9b59b6", "#8e44ad"], alpha=0.7)
            ax4.set_title("Reviews Analyzed", fontweight="bold")
            ax4.set_ylabel("Total Reviews")
            ax4.grid(True, alpha=0.3, axis="y")

        fig.suptitle(
            f"Version Comparison Dashboard\n{version_1_string} vs {version_2_string}",
            fontsize=16,
            fontweight="bold"
        )

        chart_path = output_dir / "dashboard.png"
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close()

        chart_paths["dashboard"] = str(chart_path)
        ctx.textual.success_text(f"✓ Saved: dashboard.png")

        # Store in context
        ctx.data["chart_paths"] = chart_paths

        ctx.textual.success_text(f"Charts saved to {output_dir}")
        ctx.textual.end_step("success")

        return Success(f"Generated {len(chart_paths)} charts in {analytics_method} mode")

    except Exception as e:
        error_msg = f"Failed to generate charts: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)
