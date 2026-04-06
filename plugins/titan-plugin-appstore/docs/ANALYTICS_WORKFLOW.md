# Version Analytics Workflow

## Overview

This workflow compares **propagation** and **stability metrics** between the latest 2 released versions of your iOS app using App Store Connect Analytics API.

## Metrics Calculated

### 📈 Propagation Metrics

Measures how quickly a version is being adopted by users:

- **Total Sessions**: Total number of app sessions per version
- **Daily Growth Rate**: Percentage growth in sessions day-over-day
- **Active Devices**: Number of unique devices using each version
- **Average Daily Growth**: Mean growth rate across all days

### 🛡️ Stability Metrics

Measures the quality and reliability of each version:

- **Crash Rate**: `(Total Crashes / Total Sessions) × 100`
- **Total Crashes**: Number of crashes reported
- **Retention D1**: Percentage of users who return after 1 day
- **Retention D7**: Percentage of users who return after 7 days

## Prerequisites

### 1. Install Dependencies

```bash
cd plugins/titan-plugin-appstore
pip install -e .
```

This will install:
- `pandas >= 2.0.0` - Data analysis
- `matplotlib >= 3.7.0` - Chart generation

### 2. Configure App Store Connect

Run the workflow once to trigger the setup wizard:

```bash
titan workflow run appstore:version-analytics
```

You'll need:
- **Key ID**: Your App Store Connect API key ID
- **Issuer ID**: Your issuer ID (or leave empty for Individual Keys)
- **Private Key (.p8)**: Path to your private key file

## Usage

### Run the Workflow

```bash
titan workflow run appstore:version-analytics
```

### Workflow Steps

1. **Check Configuration** - Verifies credentials (runs setup if needed)
2. **Select App** - Choose which app to analyze
3. **Fetch Latest Versions** - Retrieves top 2 released versions
4. **Request Analytics Reports** - Creates analytics requests for:
   - `APP_USAGE` (sessions, devices, retention)
   - `CRASHES` (crash counts)
5. **Analyze Metrics** - Calculates propagation/stability metrics
6. **Generate Charts** - Creates 3 PNG charts:
   - Sessions over time (line chart)
   - Daily growth rate (line chart)
   - Stability comparison (bar charts)
7. **Generate HTML Report** - Creates comprehensive report

## Output

### Directory Structure

```
./analytics_reports/
├── propagation_sessions.png
├── propagation_growth.png
├── stability_comparison.png
└── analytics_report_YYYYMMDD_HHMMSS.html
```

### HTML Report Contents

- **Summary Cards**: Quick overview of versions and analysis period
- **Propagation Table**: Side-by-side comparison with winner highlights
- **Stability Table**: Crash rate, retention metrics
- **Embedded Charts**: All charts embedded as base64 (portable)
- **Key Insights**: Auto-generated conclusions

## API Endpoints Used

### 1. GET `/v1/apps/{id}/appStoreVersions`

Retrieves latest 2 versions:

```http
GET /v1/apps/{id}/appStoreVersions
  ?sort=-createdDate
  &limit=2
  &filter[platform]=IOS
  &filter[appStoreState]=READY_FOR_SALE
```

### 2. POST `/v1/analyticsReportRequests`

Creates analytics report request:

```json
{
  "data": {
    "type": "analyticsReportRequests",
    "attributes": {
      "accessType": "ONGOING"
    },
    "relationships": {
      "app": {"data": {"type": "apps", "id": "{app_id}"}}
    },
    "attributes": {
      "filters": [
        {"dimensionKey": "appStoreVersion", "optionKeys": ["{version_id}"]},
        {"dimensionKey": "date", "optionKeys": ["{start_date}...{end_date}"]},
        {"dimensionKey": "category", "optionKeys": ["APP_USAGE"]}
      ]
    }
  }
}
```

### 3. GET `/v1/analyticsReportRequests/{id}`

Polls for report completion (status: `PROCESSING` → `COMPLETED`)

### 4. Download Report Data

Downloads gzipped CSV from URL in response

## Rate Limits & Error Handling

- **Polling**: Maximum 5 minutes with 10-second intervals
- **Rate Limits**: Automatic retry with exponential backoff
- **Timeouts**: 60-second timeout per HTTP request
- **Error Recovery**: Step failures are logged with error codes

## Troubleshooting

### Error: "Found only 1 version(s). Need at least 2 for comparison"

**Solution**: Ensure you have at least 2 versions in `READY_FOR_SALE` state.

### Error: "Missing required libraries: pandas"

**Solution**: Install dependencies:
```bash
pip install pandas matplotlib
```

### Error: "Report generation failed or timed out"

**Causes**:
- App Store Connect servers busy
- No data available for date range
- Invalid version IDs

**Solution**:
- Wait a few minutes and retry
- Check if versions have analytics data (recently released versions may not)

### Error: "Failed to parse report data"

**Cause**: Corrupted or empty report

**Solution**: Retry the workflow. If persists, check App Store Connect API status.

## Date Range Logic

By default, the workflow uses:

```python
start_date = version_1.earliestReleaseDate  # First version's release date
end_date = datetime.now()                   # Today
max_range = 30 days                         # API limit
```

If version release date is unavailable, falls back to:

```python
start_date = datetime.now() - timedelta(days=30)
```

## Example Output

### Propagation Metrics

| Metric              | V1.2.3 | V1.2.2 | Winner |
|---------------------|--------|--------|--------|
| Total Sessions      | 45,230 | 38,912 | V1     |
| Avg Daily Growth    | 3.24%  | 2.87%  | V1     |

### Stability Metrics

| Metric         | V1.2.3  | V1.2.2  | Winner |
|----------------|---------|---------|--------|
| Crash Rate     | 0.0234% | 0.0412% | V1     |
| Total Crashes  | 23      | 41      | -      |
| Retention D1   | 67.8%   | 64.2%   | V1     |
| Retention D7   | 42.1%   | 38.9%   | V1     |

## Advanced Usage

### Custom Date Range

Modify `request_analytics_step.py`:

```python
# Custom 14-day window
start_date = datetime.now() - timedelta(days=14)
end_date = datetime.now()
```

### Additional Metrics

Add more categories in `request_analytics_step.py`:

```python
categories = ["APP_USAGE", "CRASHES", "ENGAGEMENT"]
```

Available categories:
- `APP_USAGE`
- `CRASHES`
- `ENGAGEMENT`
- `PERFORMANCE`
- `FRAMERATE`

### Export to CSV

Add to `analyze_metrics_step.py`:

```python
import pandas as pd

df = pd.DataFrame(prop_v1["daily_metrics"])
df.to_csv("propagation_v1.csv", index=False)
```

## References

- [App Store Connect API Docs](https://developer.apple.com/documentation/appstoreconnectapi)
- [Analytics Reports API](https://developer.apple.com/documentation/appstoreconnectapi/analytics)
- [Titan CLI Workflows](https://github.com/your-org/titan-cli)

---

**Last Updated**: 2026-03-16
**Plugin Version**: 1.0.0
