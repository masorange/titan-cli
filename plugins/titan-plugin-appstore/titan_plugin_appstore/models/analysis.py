"""
Analysis models - Combined metrics for version analysis.

These models combine propagation and stability metrics
for comprehensive version analysis.
"""

from typing import Optional
from pydantic import BaseModel


class StabilityMetrics(BaseModel):
    """Stability metrics for a version."""

    version_string: str
    crash_rate: float = 0.0
    hang_rate: float = 0.0
    terminations: int = 0
    hangs: int = 0

    def format_summary(self) -> str:
        """Format as summary string."""
        return (
            f"Crash: {self.crash_rate:.4f}%, "
            f"Hang: {self.hang_rate:.4f}%"
        )

    def is_stable(self, crash_threshold: float = 0.5) -> bool:
        """Check if version is stable based on crash rate."""
        return self.crash_rate < crash_threshold


class PropagationMetrics(BaseModel):
    """Propagation metrics for a version."""

    version_string: str
    total_units: int = 0
    countries: int = 0
    market_share: float = 0.0  # % of total installations

    def format_summary(self) -> str:
        """Format as summary string."""
        return (
            f"{self.total_units:,} units across "
            f"{self.countries} countries ({self.market_share:.1f}% share)"
        )


class VersionAnalysisView(BaseModel):
    """
    Complete analysis view combining stability and propagation.

    This model provides a unified view of a version's health,
    combining crash/hang metrics with propagation/distribution data.
    """

    # Version identification
    version_id: str
    version_string: str
    app_id: str
    app_name: str

    # Stability metrics
    stability: StabilityMetrics

    # Propagation metrics
    propagation: PropagationMetrics

    # Computed fields
    health_score: float = 0.0  # 0-100 score
    status: str = "unknown"  # healthy, warning, critical

    def compute_health_score(self) -> float:
        """
        Compute overall health score (0-100).

        Formula:
        - Stability weight: 60% (crash_rate inverted)
        - Propagation weight: 40% (market share)

        Returns:
            Health score between 0 and 100
        """
        # Stability component (60%)
        # Lower crash rate = better score
        # Assume crash_rate of 1.0% is critical, 0% is perfect
        stability_score = max(0, 100 - (self.stability.crash_rate * 100))
        stability_component = stability_score * 0.6

        # Propagation component (40%)
        # Higher market share = better score
        propagation_component = self.propagation.market_share * 0.4

        total_score = stability_component + propagation_component

        self.health_score = round(total_score, 2)
        return self.health_score

    def compute_status(self) -> str:
        """
        Compute status based on crash rate and propagation.

        Returns:
            Status: "healthy", "warning", "critical"
        """
        if self.stability.crash_rate > 1.0:
            # More than 1% crash rate is critical
            self.status = "critical"
        elif self.stability.crash_rate > 0.5:
            # 0.5-1% crash rate is warning
            self.status = "warning"
        elif self.propagation.total_units == 0:
            # No propagation yet
            self.status = "unknown"
        else:
            # Low crash rate and some propagation
            self.status = "healthy"

        return self.status

    def format_summary(self) -> str:
        """
        Format complete summary for display.

        Returns:
            Human-readable summary string
        """
        status_emoji = {
            "healthy": "🟢",
            "warning": "🟡",
            "critical": "🔴",
            "unknown": "⚪",
        }

        emoji = status_emoji.get(self.status, "❓")

        return (
            f"{emoji} {self.app_name} v{self.version_string}\n"
            f"   Stability: {self.stability.format_summary()}\n"
            f"   Propagation: {self.propagation.format_summary()}\n"
            f"   Health Score: {self.health_score}/100"
        )

    def get_recommendations(self) -> list[str]:
        """
        Get recommendations based on metrics.

        Returns:
            List of recommendation strings
        """
        recommendations = []

        if self.status == "critical":
            recommendations.append(
                "⚠️ CRITICAL: High crash rate detected. "
                "Consider pulling from App Store or releasing hotfix."
            )

        if self.status == "warning":
            recommendations.append(
                "⚠️ WARNING: Elevated crash rate. Monitor closely."
            )

        if self.propagation.total_units > 0 and self.stability.crash_rate < 0.3:
            recommendations.append(
                "✅ Version is stable and propagating well. "
                "Safe to continue rollout."
            )

        if self.propagation.market_share < 10.0 and self.stability.crash_rate < 0.5:
            recommendations.append(
                "💡 TIP: Version is stable. Consider increasing rollout percentage."
            )

        if self.propagation.market_share > 80.0:
            recommendations.append(
                "📊 INFO: Version has majority market share. "
                "Monitor for any emerging issues."
            )

        return recommendations


class VersionComparisonView(BaseModel):
    """
    Comparison between two versions.

    Used for release decision making.
    """

    current_version: VersionAnalysisView
    previous_version: Optional[VersionAnalysisView] = None

    # Computed deltas
    crash_rate_delta: float = 0.0  # + means worse, - means better
    propagation_delta: float = 0.0  # + means more units

    def compute_deltas(self) -> None:
        """Compute delta metrics."""
        if not self.previous_version:
            return

        self.crash_rate_delta = (
            self.current_version.stability.crash_rate
            - self.previous_version.stability.crash_rate
        )

        self.propagation_delta = (
            self.current_version.propagation.total_units
            - self.previous_version.propagation.total_units
        )

    def is_regression(self) -> bool:
        """Check if current version is worse than previous."""
        if not self.previous_version:
            return False

        # Regression if crash rate increased significantly
        return self.crash_rate_delta > 0.2

    def format_comparison(self) -> str:
        """Format comparison summary."""
        if not self.previous_version:
            return self.current_version.format_summary()

        crash_arrow = "📈" if self.crash_rate_delta > 0 else "📉"
        prop_arrow = "📈" if self.propagation_delta > 0 else "📉"

        return (
            f"Comparison: {self.previous_version.version_string} → {self.current_version.version_string}\n"
            f"   {crash_arrow} Crash Rate: {self.crash_rate_delta:+.4f}%\n"
            f"   {prop_arrow} Propagation: {self.propagation_delta:+,} units\n"
            f"   Regression: {'YES ⚠️' if self.is_regression() else 'NO ✅'}"
        )
