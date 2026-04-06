"""
Tests for analysis operations.
"""

import pytest
from unittest.mock import Mock, MagicMock
from titan_cli.core.result import ClientSuccess, ClientError

from titan_plugin_appstore.operations.analysis_operations import AnalysisOperations
from titan_plugin_appstore.models.analysis import (
    VersionAnalysisView,
    StabilityMetrics,
    PropagationMetrics,
)
from titan_plugin_appstore.models.view import VersionView, AppView


@pytest.fixture
def mock_client():
    """Create a mock AppStoreConnectClient."""
    client = Mock()
    client.metrics = Mock()
    return client


@pytest.fixture
def analysis_ops(mock_client):
    """Create AnalysisOperations with mocked client."""
    return AnalysisOperations(mock_client)


class TestAnalyzeVersion:
    """Tests for analyze_version operation."""

    def test_analyze_version_success(self, analysis_ops, mock_client):
        """Test successful version analysis with all metrics."""
        # Mock list_versions
        version = VersionView(
            id="ver123",
            version_string="1.2.3",
            platform="IOS",
            state="READY_FOR_SALE",
            state_display="Ready for Sale",
            release_type_display="Manual",
            platform_display="iOS",
        )
        mock_client.list_versions.return_value = ClientSuccess(
            data=[version], message="Found version"
        )

        # Mock get_app
        app = AppView(
            id="app123",
            name="Test App",
            bundle_id="com.test.app",
            sku="TESTSKU",
            primary_locale="en-US",
        )
        mock_client.get_app.return_value = ClientSuccess(data=app, message="Found app")

        # Mock performance metrics
        perf_data = {
            "productData": [
                {
                    "metricCategories": [
                        {
                            "identifier": "TERMINATION",
                            "metrics": [
                                {
                                    "identifier": "onScreen",
                                    "datasets": [
                                        {
                                            "points": [
                                                {"version": "1.2.3", "value": 0.2},
                                            ]
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                }
            ]
        }
        mock_client.metrics.get_performance_metrics.return_value = ClientSuccess(
            data=perf_data, message="Got metrics"
        )

        crash_metrics = {
            "1.2.3": {
                "crash_rate": 0.2,
                "hang_rate": 0.1,
                "terminations": 20,
                "hangs": 10,
            }
        }
        mock_client.metrics.extract_crash_metrics_by_version.return_value = (
            ClientSuccess(data=crash_metrics, message="Extracted")
        )

        # Mock sales metrics
        from titan_plugin_appstore.clients.services.metrics_service import (
            PropagationMetrics as MetricsPropagation,
        )

        sales_data = MetricsPropagation(
            total_units=1000,
            countries=50,
            by_version={"1.2.3": 800, "1.2.2": 200},
            latest_version="1.2.3",
        )
        mock_client.metrics.get_propagation_from_sales.return_value = ClientSuccess(
            data=sales_data, message="Got sales"
        )

        # Execute
        result = analysis_ops.analyze_version(
            app_id="app123",
            version_string="1.2.3",
            vendor_number="12345",
            app_name="Test App",
        )

        # Verify
        assert isinstance(result, ClientSuccess)
        analysis = result.data

        assert isinstance(analysis, VersionAnalysisView)
        assert analysis.version_string == "1.2.3"
        assert analysis.app_name == "Test App"

        # Check stability
        assert analysis.stability.crash_rate == 0.2
        assert analysis.stability.hang_rate == 0.1
        assert analysis.stability.terminations == 20

        # Check propagation
        assert analysis.propagation.total_units == 800
        assert analysis.propagation.countries == 50
        assert analysis.propagation.market_share == 80.0  # 800/1000

        # Check health score (computed)
        assert analysis.health_score > 0
        assert analysis.status in ["healthy", "warning", "critical", "unknown"]

    def test_analyze_version_no_propagation_data(self, analysis_ops, mock_client):
        """Test analysis when propagation data is not available."""
        # Mock list_versions
        version = VersionView(
            id="ver123",
            version_string="1.2.3",
            platform="IOS",
            state="READY_FOR_SALE",
            state_display="Ready for Sale",
            release_type_display="Manual",
            platform_display="iOS",
        )
        mock_client.list_versions.return_value = ClientSuccess(
            data=[version], message="Found"
        )

        # Mock get_app
        app = AppView(
            id="app123",
            name="Test App",
            bundle_id="com.test.app",
            sku="SKU",
            primary_locale="en-US",
        )
        mock_client.get_app.return_value = ClientSuccess(data=app, message="Found")

        # Mock stability only
        perf_data = {"productData": []}
        mock_client.metrics.get_performance_metrics.return_value = ClientSuccess(
            data=perf_data, message="Got metrics"
        )

        crash_metrics = {
            "1.2.3": {
                "crash_rate": 0.3,
                "hang_rate": 0.05,
                "terminations": 30,
                "hangs": 5,
            }
        }
        mock_client.metrics.extract_crash_metrics_by_version.return_value = (
            ClientSuccess(data=crash_metrics, message="Extracted")
        )

        # Execute WITHOUT vendor_number (no propagation)
        result = analysis_ops.analyze_version(
            app_id="app123", version_string="1.2.3"
        )

        # Verify
        assert isinstance(result, ClientSuccess)
        analysis = result.data

        # Should have stability but empty propagation
        assert analysis.stability.crash_rate == 0.3
        assert analysis.propagation.total_units == 0
        assert analysis.propagation.countries == 0

    def test_analyze_version_not_found(self, analysis_ops, mock_client):
        """Test when version is not found."""
        mock_client.list_versions.return_value = ClientSuccess(
            data=[], message="No versions"
        )

        result = analysis_ops.analyze_version(
            app_id="app123", version_string="9.9.9"
        )

        assert isinstance(result, ClientError)
        assert "not found" in result.error_message.lower()

    def test_analyze_version_stability_failure(self, analysis_ops, mock_client):
        """Test when stability metrics fail to fetch."""
        # Mock list_versions
        version = VersionView(
            id="ver123",
            version_string="1.2.3",
            platform="IOS",
            state="READY_FOR_SALE",
            state_display="Ready for Sale",
            release_type_display="Manual",
            platform_display="iOS",
        )
        mock_client.list_versions.return_value = ClientSuccess(
            data=[version], message="Found"
        )

        # Mock get_app
        app = AppView(
            id="app123",
            name="Test App",
            bundle_id="com.test.app",
            sku="SKU",
            primary_locale="en-US",
        )
        mock_client.get_app.return_value = ClientSuccess(data=app, message="Found")

        # Stability fails
        mock_client.metrics.get_performance_metrics.return_value = ClientError(
            error_message="API error", error_code="API_ERROR"
        )

        # Execute
        result = analysis_ops.analyze_version(
            app_id="app123", version_string="1.2.3"
        )

        # Should still succeed with empty stability
        assert isinstance(result, ClientSuccess)
        analysis = result.data

        assert analysis.stability.crash_rate == 0.0
        assert analysis.stability.hang_rate == 0.0


class TestCompareVersions:
    """Tests for compare_versions operation."""

    def test_compare_versions_success(self, analysis_ops, mock_client):
        """Test successful version comparison."""
        # Mock analyze_version to return two different analyses
        current_analysis = VersionAnalysisView(
            version_id="v2",
            version_string="1.2.0",
            app_id="app123",
            app_name="Test App",
            stability=StabilityMetrics(
                version_string="1.2.0",
                crash_rate=0.2,
                hang_rate=0.05,
            ),
            propagation=PropagationMetrics(
                version_string="1.2.0", total_units=1000, countries=50
            ),
        )

        previous_analysis = VersionAnalysisView(
            version_id="v1",
            version_string="1.1.0",
            app_id="app123",
            app_name="Test App",
            stability=StabilityMetrics(
                version_string="1.1.0",
                crash_rate=0.3,
                hang_rate=0.1,
            ),
            propagation=PropagationMetrics(
                version_string="1.1.0", total_units=500, countries=40
            ),
        )

        # Mock analyze_version calls
        def mock_analyze(app_id, version_string, vendor_number=None, app_name=None):
            if version_string == "1.2.0":
                return ClientSuccess(data=current_analysis, message="Analyzed")
            else:
                return ClientSuccess(data=previous_analysis, message="Analyzed")

        analysis_ops.analyze_version = Mock(side_effect=mock_analyze)

        # Execute
        result = analysis_ops.compare_versions(
            app_id="app123", current_version="1.2.0", previous_version="1.1.0"
        )

        # Verify
        assert isinstance(result, ClientSuccess)
        comparison = result.data

        # Check deltas
        assert comparison.crash_rate_delta == -0.1  # Improved (lower is better)
        assert comparison.propagation_delta == 500  # More units

        # Should not be regression (crash improved)
        assert not comparison.is_regression()


class TestHealthScoreComputation:
    """Tests for health score computation in VersionAnalysisView."""

    def test_compute_health_score_perfect(self):
        """Test health score for perfect version."""
        analysis = VersionAnalysisView(
            version_id="v1",
            version_string="1.0.0",
            app_id="app123",
            app_name="Test",
            stability=StabilityMetrics(
                version_string="1.0.0",
                crash_rate=0.0,  # Perfect
                hang_rate=0.0,
            ),
            propagation=PropagationMetrics(
                version_string="1.0.0",
                total_units=1000,
                countries=50,
                market_share=100.0,  # Perfect
            ),
        )

        score = analysis.compute_health_score()

        # Perfect stability (60%) + perfect propagation (40%) = 100
        assert score == 100.0

    def test_compute_health_score_critical(self):
        """Test health score for critical version."""
        analysis = VersionAnalysisView(
            version_id="v1",
            version_string="1.0.0",
            app_id="app123",
            app_name="Test",
            stability=StabilityMetrics(
                version_string="1.0.0",
                crash_rate=2.0,  # Critical (2%)
                hang_rate=0.5,
            ),
            propagation=PropagationMetrics(
                version_string="1.0.0",
                total_units=100,
                countries=5,
                market_share=10.0,  # Low
            ),
        )

        score = analysis.compute_health_score()

        # Should be low due to high crash rate
        assert score < 50.0

    def test_compute_status_healthy(self):
        """Test status computation for healthy version."""
        analysis = VersionAnalysisView(
            version_id="v1",
            version_string="1.0.0",
            app_id="app123",
            app_name="Test",
            stability=StabilityMetrics(
                version_string="1.0.0",
                crash_rate=0.2,  # Low
            ),
            propagation=PropagationMetrics(
                version_string="1.0.0", total_units=1000
            ),
        )

        status = analysis.compute_status()

        assert status == "healthy"

    def test_compute_status_warning(self):
        """Test status computation for warning version."""
        analysis = VersionAnalysisView(
            version_id="v1",
            version_string="1.0.0",
            app_id="app123",
            app_name="Test",
            stability=StabilityMetrics(
                version_string="1.0.0",
                crash_rate=0.7,  # Warning threshold
            ),
            propagation=PropagationMetrics(
                version_string="1.0.0", total_units=1000
            ),
        )

        status = analysis.compute_status()

        assert status == "warning"

    def test_compute_status_critical(self):
        """Test status computation for critical version."""
        analysis = VersionAnalysisView(
            version_id="v1",
            version_string="1.0.0",
            app_id="app123",
            app_name="Test",
            stability=StabilityMetrics(
                version_string="1.0.0",
                crash_rate=1.5,  # Critical
            ),
            propagation=PropagationMetrics(
                version_string="1.0.0", total_units=1000
            ),
        )

        status = analysis.compute_status()

        assert status == "critical"


class TestRecommendations:
    """Tests for recommendation generation."""

    def test_recommendations_critical(self):
        """Test recommendations for critical version."""
        analysis = VersionAnalysisView(
            version_id="v1",
            version_string="1.0.0",
            app_id="app123",
            app_name="Test",
            stability=StabilityMetrics(
                version_string="1.0.0",
                crash_rate=1.5,
            ),
            propagation=PropagationMetrics(
                version_string="1.0.0", total_units=1000
            ),
        )

        analysis.compute_status()
        recommendations = analysis.get_recommendations()

        assert len(recommendations) > 0
        assert any("CRITICAL" in rec for rec in recommendations)

    def test_recommendations_healthy_low_propagation(self):
        """Test recommendations for healthy but low propagation."""
        analysis = VersionAnalysisView(
            version_id="v1",
            version_string="1.0.0",
            app_id="app123",
            app_name="Test",
            stability=StabilityMetrics(
                version_string="1.0.0",
                crash_rate=0.2,
            ),
            propagation=PropagationMetrics(
                version_string="1.0.0",
                total_units=100,
                market_share=5.0,  # Low
            ),
        )

        analysis.compute_status()
        recommendations = analysis.get_recommendations()

        # Should suggest increasing rollout
        assert any("rollout" in rec.lower() for rec in recommendations)
