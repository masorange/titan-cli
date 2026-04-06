# Version Analysis Guide

Complete guide for analyzing version stability and propagation using the App Store Connect plugin.

## Overview

The version analysis functionality combines **stability metrics** (crashes, hangs) and **propagation metrics** (installations, market share) to provide a comprehensive health assessment of your app versions.

## Features

### 📊 What You Get

**Stability Metrics** (from Performance API):
- Crash rate (%)
- Hang rate (%)
- Total terminations
- Total hangs

**Propagation Metrics** (from Sales Reports API):
- Installation units
- Geographic distribution (countries)
- Market share (% of total installations)

**Health Assessment**:
- Overall health score (0-100)
- Status classification (healthy/warning/critical)
- Actionable recommendations

## Usage

### 1. Using the Workflow (Recommended)

The easiest way to analyze a version:

```bash
titan
# Navigate to: Workflows → App Store → Version Health Check
```

The workflow will guide you through:
1. Configuration check
2. App selection
3. Version selection
4. Automatic analysis with results

### 2. Using the Operation (Programmatic)

For custom scripts or advanced usage:

```python
from titan_plugin_appstore.clients.appstore_client import AppStoreConnectClient
from titan_plugin_appstore.operations.analysis_operations import AnalysisOperations

# Initialize client
client = AppStoreConnectClient(
    key_id="YOUR_KEY_ID",
    issuer_id="YOUR_ISSUER_ID",
    private_key_path="/path/to/key.p8"
)

# Initialize operations
analysis_ops = AnalysisOperations(client)

# Analyze a single version
result = analysis_ops.analyze_version(
    app_id="1234567890",
    version_string="26.13.0",
    vendor_number="80012345",  # Optional: for sales data
    app_name="Mi Yoigo"        # Optional: for sales filtering
)

# Check result
match result:
    case ClientSuccess(data=analysis):
        print(f"Version: {analysis.version_string}")
        print(f"Status: {analysis.status}")
        print(f"Health Score: {analysis.health_score}/100")
        print(f"Crash Rate: {analysis.stability.crash_rate}%")
        print(f"Market Share: {analysis.propagation.market_share}%")

        for rec in analysis.get_recommendations():
            print(f"  • {rec}")

    case ClientError(error_message=err):
        print(f"Error: {err}")
```

### 3. Comparing Versions

Compare two versions side-by-side:

```python
result = analysis_ops.compare_versions(
    app_id="1234567890",
    current_version="26.13.0",
    previous_version="26.12.0",
    vendor_number="80012345",
    app_name="Mi Yoigo"
)

match result:
    case ClientSuccess(data=comparison):
        print(comparison.format_comparison())
        # Output:
        # Comparison: 26.12.0 → 26.13.0
        #    📉 Crash Rate: -0.15%  (improved!)
        #    📈 Propagation: +5,432 units
        #    Regression: NO ✅
```

### 4. Analyzing Latest N Versions

Get analysis for multiple versions:

```python
result = analysis_ops.analyze_latest_versions(
    app_id="1234567890",
    count=3,  # Latest 3 versions
    vendor_number="80012345",
    app_name="Mi Yoigo"
)

match result:
    case ClientSuccess(data=analyses):
        for analysis in analyses:
            print(analysis.format_summary())
```

## Understanding the Metrics

### Stability Metrics

**Crash Rate**:
- Percentage of sessions that ended in a crash
- Lower is better
- Thresholds:
  - `< 0.5%`: Healthy 🟢
  - `0.5-1.0%`: Warning 🟡
  - `> 1.0%`: Critical 🔴

**Hang Rate**:
- Percentage of sessions that experienced hangs
- Lower is better
- Contributes to health score but not status

### Propagation Metrics

**Total Units**:
- Number of installations/downloads
- From Sales Reports API (actual data)
- Higher indicates wider adoption

**Market Share**:
- Percentage of total app installations for this version
- Calculated as: `(version_units / total_units) * 100`
- Important for rollout decisions

**Countries**:
- Number of countries where app is active
- Indicates geographic distribution

### Health Score

The health score (0-100) is calculated as:

```
Health Score = (Stability Component × 0.6) + (Propagation Component × 0.4)

Where:
- Stability Component = max(0, 100 - (crash_rate × 100))
- Propagation Component = market_share
```

**Interpretation**:
- `90-100`: Excellent health
- `70-89`: Good health
- `50-69`: Fair health
- `< 50`: Poor health

### Status Classification

**Healthy 🟢**:
- Crash rate < 0.5%
- Has propagation data

**Warning 🟡**:
- Crash rate 0.5-1.0%
- Monitor closely

**Critical 🔴**:
- Crash rate > 1.0%
- Consider hotfix or rollback

**Unknown ⚪**:
- No propagation data yet
- New version or no sales

## Example Output

```
============================================================
ANALYSIS RESULTS
============================================================

App: Mi Yoigo
Version: 26.13.0

📉 STABILITY METRICS
------------------------------------------------------------
  Crash Rate:    0.2123%
  Hang Rate:     0.0456%
  Terminations:  2,145
  Hangs:         456

📈 PROPAGATION METRICS
------------------------------------------------------------
  Total Units:   45,678
  Countries:     25
  Market Share:  78.3%

🏥 HEALTH ASSESSMENT
------------------------------------------------------------
  Status:        🟢 HEALTHY
  Health Score:  89.2/100

💡 RECOMMENDATIONS
------------------------------------------------------------
  ✅ Version is stable and propagating well. Safe to continue rollout.
  📊 INFO: Version has majority market share. Monitor for any emerging issues.

============================================================
✅ Version is healthy!
```

## Common Scenarios

### Scenario 1: New Version Released

```python
# Analyze new version (no propagation yet)
result = analysis_ops.analyze_version(
    app_id="1234567890",
    version_string="26.14.0"
)

# Expected: status = "unknown" (no sales data yet)
# Action: Monitor crash rate, wait for propagation
```

### Scenario 2: Gradual Rollout

```python
# Compare current rollout vs previous stable
result = analysis_ops.compare_versions(
    app_id="1234567890",
    current_version="26.13.0",
    previous_version="26.12.0",
    vendor_number="80012345",
    app_name="Mi Yoigo"
)

# Check if safe to increase rollout percentage
if not comparison.is_regression():
    print("✅ Safe to increase rollout")
else:
    print("⚠️  Hold rollout, regression detected")
```

### Scenario 3: Incident Response

```python
# Quick health check during incident
result = analysis_ops.analyze_version(
    app_id="1234567890",
    version_string="26.13.0",
    vendor_number="80012345",
    app_name="Mi Yoigo"
)

if analysis.status == "critical":
    print("🚨 CRITICAL: Consider emergency rollback")
    print(f"   Crash rate: {analysis.stability.crash_rate}%")
    print(f"   Affected users: ~{analysis.propagation.total_units}")
```

## Configuration

### Required Credentials

In `.titan/config.toml`:

```toml
[plugins.appstore]
enabled = true

[plugins.appstore.credentials]
key_id = "ABC123XYZ"
issuer_id = "12345678-1234-1234-1234-123456789012"
private_key_path = "/path/to/AuthKey_ABC123XYZ.p8"
vendor_number = "80012345"  # Optional but recommended for full metrics
```

### Vendor Number (Optional but Recommended)

The **vendor number** enables Sales Reports API access, which provides:
- Actual installation/download counts
- Geographic distribution
- Market share calculations

**Without vendor number**:
- Only stability metrics available
- No propagation data
- Status will be "unknown" for new versions

**How to find vendor number**:
1. Go to [App Store Connect](https://appstoreconnect.apple.com)
2. Navigate to: Sales and Trends → Reports → Sales
3. Your vendor number is shown in the report selector

## API Reference

### `AnalysisOperations`

#### `analyze_version()`

```python
def analyze_version(
    app_id: str,
    version_string: str,
    vendor_number: Optional[str] = None,
    app_name: Optional[str] = None,
) -> ClientResult[VersionAnalysisView]:
    """
    Analyze a single version.

    Args:
        app_id: App Store Connect app ID
        version_string: Version to analyze (e.g., "26.13.0")
        vendor_number: Vendor number for sales reports (optional)
        app_name: App name for sales filtering (optional)

    Returns:
        ClientResult[VersionAnalysisView]
    """
```

#### `compare_versions()`

```python
def compare_versions(
    app_id: str,
    current_version: str,
    previous_version: str,
    vendor_number: Optional[str] = None,
    app_name: Optional[str] = None,
) -> ClientResult[VersionComparisonView]:
    """
    Compare two versions.

    Args:
        app_id: App ID
        current_version: Current version string
        previous_version: Previous version string
        vendor_number: Vendor number (optional)
        app_name: App name (optional)

    Returns:
        ClientResult[VersionComparisonView]
    """
```

#### `analyze_latest_versions()`

```python
def analyze_latest_versions(
    app_id: str,
    count: int = 2,
    vendor_number: Optional[str] = None,
    app_name: Optional[str] = None,
) -> ClientResult[List[VersionAnalysisView]]:
    """
    Analyze latest N versions.

    Args:
        app_id: App ID
        count: Number of versions (default: 2)
        vendor_number: Vendor number (optional)
        app_name: App name (optional)

    Returns:
        ClientResult[List[VersionAnalysisView]]
    """
```

### Models

#### `VersionAnalysisView`

```python
class VersionAnalysisView:
    version_id: str
    version_string: str
    app_id: str
    app_name: str
    stability: StabilityMetrics
    propagation: PropagationMetrics
    health_score: float  # 0-100
    status: str  # healthy/warning/critical/unknown

    def compute_health_score() -> float
    def compute_status() -> str
    def format_summary() -> str
    def get_recommendations() -> List[str]
```

#### `StabilityMetrics`

```python
class StabilityMetrics:
    version_string: str
    crash_rate: float
    hang_rate: float
    terminations: int
    hangs: int

    def format_summary() -> str
    def is_stable(crash_threshold: float = 0.5) -> bool
```

#### `PropagationMetrics`

```python
class PropagationMetrics:
    version_string: str
    total_units: int
    countries: int
    market_share: float  # %

    def format_summary() -> str
```

## Troubleshooting

### No Sales Data

**Problem**: Propagation metrics show 0 units

**Solutions**:
1. Check `vendor_number` is configured in `.titan/config.toml`
2. Verify version has been live for at least 24 hours (Apple delay)
3. Check Sales Reports are enabled in App Store Connect

### Performance Metrics Empty

**Problem**: Crash rate shows 0.0% but you know there are crashes

**Solutions**:
1. Wait 24-48 hours after release (Apple processing delay)
2. Verify Performance API is enabled for your account
3. Check version has enough active sessions (Apple minimum threshold)

### Authentication Errors

**Problem**: "Failed to authenticate" errors

**Solutions**:
1. Verify `key_id`, `issuer_id`, and `private_key_path` are correct
2. Check `.p8` file permissions (must be readable)
3. Ensure API key has App Manager role in App Store Connect

## Best Practices

1. **Monitor New Releases**:
   - Analyze immediately after release
   - Check again after 24-48 hours when data is complete

2. **Compare Before Increasing Rollout**:
   - Always compare new vs previous version
   - Look for crash rate regressions
   - Check recommendations before scaling

3. **Set Up Alerts**:
   - Use health score in CI/CD pipelines
   - Alert on `status == "critical"`
   - Track market share trends

4. **Regular Health Checks**:
   - Run analysis weekly for production versions
   - Monitor versions with >50% market share closely
   - Archive data for historical comparison

## Related Documentation

- [Plugin Architecture](./STRUCTURE.md)
- [Analytics Workflow](./ANALYTICS_WORKFLOW.md)
- [Metrics Service API](../titan_plugin_appstore/clients/services/metrics_service.py)

---

**Version Analysis Guide v1.0**
*Last updated: 2026-03-31*
