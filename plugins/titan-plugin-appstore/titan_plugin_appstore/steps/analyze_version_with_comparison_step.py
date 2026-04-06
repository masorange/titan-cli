"""
Analyze Version with Comparison Step - Analyzes current version vs previous.

Automatically fetches the previous version and shows side-by-side comparison.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..clients.appstore_client import AppStoreConnectClient
from ..operations.analysis_operations import AnalysisOperations
from ..credentials import CredentialsManager
from titan_cli.core.result import ClientSuccess, ClientError


def analyze_version_with_comparison_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Analyze version(s) with automatic comparison to previous version.

    For each selected app:
    1. Analyzes the requested version
    2. Finds the previous version (by version string)
    3. Analyzes the previous version
    4. Shows side-by-side comparison with deltas

    Inputs (from ctx.data):
        - selected_apps (list): Apps to analyze
        - app_id: Single app (fallback)
        - version_string: Version to analyze (e.g., "26.12.0")
        - app_name: App name

    Outputs (saved to ctx.data):
        - version_analyses: List of current version analyses
        - previous_version_analyses: List of previous version analyses
        - comparisons: List of comparison data

    Returns:
        Success with comparison data
        Error if analysis fails
    """
    if not ctx.textual:
        return Error("Textual UI context required")

    ctx.textual.begin_step("Analyze Version(s) with Comparison")

    try:
        # Get apps to analyze
        selected_apps = ctx.data.get("selected_apps", [])
        version_string = ctx.data.get("version_string")

        apps_to_analyze = []
        if selected_apps:
            apps_to_analyze = [{"id": app["id"], "name": app["name"]} for app in selected_apps]
        else:
            app_id = ctx.data.get("app_id")
            app_name = ctx.data.get("app_name")
            if app_id:
                apps_to_analyze = [{"id": app_id, "name": app_name}]

        if not apps_to_analyze or not version_string:
            ctx.textual.error_text("Missing required inputs")
            ctx.textual.end_step("error")
            return Error("Missing apps or version_string")

        # Load credentials
        credentials = CredentialsManager.load_credentials()
        if not credentials:
            ctx.textual.error_text("No credentials configured")
            ctx.textual.end_step("error")
            return Error("Run setup wizard first")

        issuer_id = credentials.get("issuer_id")
        key_id = credentials.get("key_id")
        p8_path = credentials.get("private_key_path")
        vendor_number = credentials.get("vendor_number")

        # Initialize client
        client = AppStoreConnectClient(
            key_id=key_id, issuer_id=issuer_id, private_key_path=p8_path
        )

        analysis_ops = AnalysisOperations(client)

        # Results storage
        current_analyses = []
        previous_analyses = []
        comparisons = []

        ctx.textual.text("=" * 80)
        ctx.textual.text(f"ANALYZING {len(apps_to_analyze)} APP(S) - VERSION {version_string} vs PREVIOUS")
        ctx.textual.text("=" * 80)
        ctx.textual.text("")

        for idx, app_info in enumerate(apps_to_analyze, 1):
            app_id = app_info["id"]
            app_name = app_info["name"]

            ctx.textual.text(f"[{idx}/{len(apps_to_analyze)}] {app_name}")
            ctx.textual.text("-" * 80)

            # Step 1: Find previous version
            ctx.textual.text("  Finding previous version...")

            # Get all versions (increased limit to ensure we get all)
            versions_result = client.list_versions(app_id, limit=200)

            previous_version_string = None

            match versions_result:
                case ClientSuccess(data=versions):
                    # Sort by version string (semantic versioning)
                    try:
                        version_strings = sorted(
                            [v.version_string for v in versions],
                            key=lambda x: [int(n) for n in x.split(".")],
                            reverse=True
                        )
                    except (ValueError, AttributeError):
                        # Fallback: sort as strings if semantic version parsing fails
                        version_strings = sorted([v.version_string for v in versions], reverse=True)

                    # Find current version index
                    if version_string in version_strings:
                        current_idx = version_strings.index(version_string)
                        if current_idx + 1 < len(version_strings):
                            previous_version_string = version_strings[current_idx + 1]
                            ctx.textual.success_text(f"  ✓ Previous version: {previous_version_string}")
                        else:
                            ctx.textual.warning_text(f"  ⚠️  No previous version (this is the oldest)")
                    else:
                        # Current version not in list - try to find closest older version
                        ctx.textual.warning_text(f"  ⚠️  Version {version_string} not in first {len(versions)} versions")
                        ctx.textual.text(f"  Looking for closest older version...")

                        # Parse current version
                        try:
                            current_parts = [int(n) for n in version_string.split(".")]

                            # Find first version older than current
                            for vs in version_strings:
                                try:
                                    vs_parts = [int(n) for n in vs.split(".")]
                                    if vs_parts < current_parts:
                                        previous_version_string = vs
                                        ctx.textual.success_text(f"  ✓ Found closest older version: {previous_version_string}")
                                        break
                                except ValueError:
                                    continue

                            if not previous_version_string:
                                ctx.textual.warning_text(f"  ⚠️  No older version found")
                        except ValueError:
                            ctx.textual.error_text(f"  ✗ Cannot parse version {version_string}")

                case ClientError(error_message=err):
                    ctx.textual.error_text(f"  ✗ Failed to list versions: {err}")

            # Step 2: Analyze current version
            ctx.textual.text(f"  Analyzing {version_string}...")

            current_analysis = analysis_ops.analyze_version(
                app_id=app_id,
                version_string=version_string,
                vendor_number=vendor_number,
                app_name=app_name,
            )

            current_data = None
            match current_analysis:
                case ClientSuccess(data=analysis):
                    current_data = analysis
                    current_analyses.append(analysis)
                    ctx.textual.success_text(f"  ✓ Current version analyzed")
                case ClientError(error_message=err):
                    ctx.textual.error_text(f"  ✗ Failed: {err}")

            # Step 3: Analyze previous version (if found)
            previous_data = None
            if previous_version_string:
                ctx.textual.text(f"  Analyzing {previous_version_string}...")

                previous_analysis = analysis_ops.analyze_version(
                    app_id=app_id,
                    version_string=previous_version_string,
                    vendor_number=vendor_number,
                    app_name=app_name,
                )

                match previous_analysis:
                    case ClientSuccess(data=analysis):
                        previous_data = analysis
                        previous_analyses.append(analysis)
                        ctx.textual.success_text(f"  ✓ Previous version analyzed")
                    case ClientError(error_message=err):
                        ctx.textual.warning_text(f"  ⚠️  Previous analysis failed: {err}")

            # Step 4: Display comparison
            ctx.textual.text("")
            _display_comparison(ctx, current_data, previous_data, app_name, idx, len(apps_to_analyze))

            if current_data and previous_data:
                comparisons.append({
                    "app_name": app_name,
                    "current": current_data,
                    "previous": previous_data,
                })

        # Store results
        ctx.data["version_analyses"] = current_analyses
        ctx.data["previous_version_analyses"] = previous_analyses
        ctx.data["comparisons"] = comparisons

        if current_analyses:
            ctx.data["version_analysis"] = current_analyses[0]  # For compatibility
            ctx.data["health_score"] = current_analyses[0].health_score
            ctx.data["status"] = current_analyses[0].status

        ctx.textual.text("=" * 80)
        ctx.textual.success_text(f"✅ Analyzed {len(current_analyses)} app(s) with comparison")
        ctx.textual.text("=" * 80)

        ctx.textual.end_step("success")
        return Success(f"Analyzed {len(current_analyses)} app(s)")

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)


def _display_comparison(ctx, current, previous, app_name, app_num, total_apps):
    """Display side-by-side comparison of current vs previous version."""

    ctx.textual.text("=" * 80)
    ctx.textual.text(f"APP {app_num}/{total_apps}: {app_name}")
    ctx.textual.text("=" * 80)
    ctx.textual.text("")

    if not current:
        ctx.textual.error_text("Current version analysis failed - no comparison available")
        ctx.textual.text("")
        return

    # Header with versions
    if previous:
        ctx.textual.text(f"{'METRIC':<30} {'CURRENT':<20} {'PREVIOUS':<20} {'CHANGE':>10}")
        ctx.textual.text("-" * 80)
        ctx.textual.text(f"{'Version:':<30} {current.version_string:<20} {previous.version_string:<20}")
    else:
        ctx.textual.text(f"{'METRIC':<30} {'CURRENT':<20}")
        ctx.textual.text("-" * 80)
        ctx.textual.text(f"{'Version:':<30} {current.version_string:<20}")

    ctx.textual.text("")

    # Stability Metrics
    ctx.textual.text("📉 STABILITY METRICS")
    ctx.textual.text("-" * 80)

    if previous:
        _display_metric_row(ctx, "Crash Rate:",
                           f"{current.stability.crash_rate:.4f}%",
                           f"{previous.stability.crash_rate:.4f}%",
                           current.stability.crash_rate - previous.stability.crash_rate,
                           inverse=True)  # Lower is better

        _display_metric_row(ctx, "Hang Rate:",
                           f"{current.stability.hang_rate:.4f}%",
                           f"{previous.stability.hang_rate:.4f}%",
                           current.stability.hang_rate - previous.stability.hang_rate,
                           inverse=True)

        _display_metric_row(ctx, "Terminations:",
                           f"{current.stability.terminations:,}",
                           f"{previous.stability.terminations:,}",
                           current.stability.terminations - previous.stability.terminations,
                           inverse=True)

        _display_metric_row(ctx, "Hangs:",
                           f"{current.stability.hangs:,}",
                           f"{previous.stability.hangs:,}",
                           current.stability.hangs - previous.stability.hangs,
                           inverse=True)
    else:
        ctx.textual.text(f"  Crash Rate:    {current.stability.crash_rate:.4f}%")
        ctx.textual.text(f"  Hang Rate:     {current.stability.hang_rate:.4f}%")
        ctx.textual.text(f"  Terminations:  {current.stability.terminations:,}")
        ctx.textual.text(f"  Hangs:         {current.stability.hangs:,}")

    ctx.textual.text("")

    # Propagation Metrics
    ctx.textual.text("📈 PROPAGATION METRICS")
    ctx.textual.text("-" * 80)

    if previous:
        _display_metric_row(ctx, "Total Units:",
                           f"{current.propagation.total_units:,}",
                           f"{previous.propagation.total_units:,}",
                           current.propagation.total_units - previous.propagation.total_units,
                           inverse=False)  # Higher is better

        _display_metric_row(ctx, "Countries:",
                           f"{current.propagation.countries}",
                           f"{previous.propagation.countries}",
                           current.propagation.countries - previous.propagation.countries,
                           inverse=False)

        _display_metric_row(ctx, "Market Share:",
                           f"{current.propagation.market_share:.1f}%",
                           f"{previous.propagation.market_share:.1f}%",
                           current.propagation.market_share - previous.propagation.market_share,
                           inverse=False)
    else:
        ctx.textual.text(f"  Total Units:   {current.propagation.total_units:,}")
        ctx.textual.text(f"  Countries:     {current.propagation.countries}")
        ctx.textual.text(f"  Market Share:  {current.propagation.market_share:.1f}%")

    ctx.textual.text("")

    # Health Assessment
    ctx.textual.text("🏥 HEALTH ASSESSMENT")
    ctx.textual.text("-" * 80)

    status_emoji = {
        "healthy": "🟢",
        "warning": "🟡",
        "critical": "🔴",
        "unknown": "⚪",
    }

    if previous:
        curr_emoji = status_emoji.get(current.status, "❓")
        prev_emoji = status_emoji.get(previous.status, "❓")

        ctx.textual.text(f"  {'Status:':<28} {curr_emoji} {current.status.upper():<13} {prev_emoji} {previous.status.upper():<13}")

        health_delta = current.health_score - previous.health_score
        delta_str = _format_delta(health_delta, False)  # Higher is better

        ctx.textual.text(f"  {'Health Score:':<28} {current.health_score:5.1f}/100{'':<8} {previous.health_score:5.1f}/100{'':<8} {delta_str:>10}")
    else:
        emoji = status_emoji.get(current.status, "❓")
        ctx.textual.text(f"  Status:        {emoji} {current.status.upper()}")
        ctx.textual.text(f"  Health Score:  {current.health_score:.1f}/100")

    ctx.textual.text("")

    # Recommendations (current version only)
    recommendations = current.get_recommendations()
    if recommendations:
        ctx.textual.text("💡 RECOMMENDATIONS")
        ctx.textual.text("-" * 80)
        for rec in recommendations:
            ctx.textual.text(f"  ⚠️  {rec}")
        ctx.textual.text("")

    ctx.textual.text("=" * 80)
    ctx.textual.text("")


def _display_metric_row(ctx, label, current_val, previous_val, delta, inverse=False):
    """Display a single metric row with current, previous, and delta."""
    delta_str = _format_delta(delta, inverse)
    ctx.textual.text(f"  {label:<28} {current_val:<20} {previous_val:<20} {delta_str:>10}")


def _format_delta(delta, inverse=False):
    """
    Format delta with arrow and color indication.

    Args:
        delta: Numeric delta (can be int or float)
        inverse: If True, negative delta is good (e.g., for crash rate)

    Returns:
        Formatted string with arrow
    """
    if delta == 0:
        return "—"

    # Determine if this is a good or bad change
    is_good = (delta < 0 if inverse else delta > 0)

    # Format the number
    if isinstance(delta, float):
        delta_str = f"{abs(delta):.2f}"
    else:
        delta_str = f"{abs(delta):,}"

    # Add arrow
    if delta > 0:
        arrow = "↑" if is_good else "↑"
        return f"↑ +{delta_str}"
    else:
        arrow = "↓" if is_good else "↓"
        return f"↓ -{delta_str}"


__all__ = ["analyze_version_with_comparison_step"]
